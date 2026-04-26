"""
water.py

Water source ingestion for the Wildlife Water Stress Atlas.

ARCHITECTURE OVERVIEW:
----------------------
This module provides two interfaces for loading water data:

1. SOURCE CLASS INTERFACE (recommended for pipelines):
   Each water source type is a class that inherits from the WaterSource
   abstract base class. Every source class produces a GeoDataFrame with
   the same normalized schema, regardless of the underlying file format
   or data provider. This makes it trivial to add new source types
   (wetlands, pans, groundwater) without changing anything downstream.

   Use load_all_water(config, bbox, month) to load and combine multiple
   sources in one call.

2. CONVENIENCE FUNCTIONS (simple single-source loading):
   load_rivers() and load_lakes() are thin wrappers for simple single-source
   use cases. combine_water_layers() merges any number of GeoDataFrames.

NORMALIZED SCHEMA:
------------------
Every source class produces these columns:

    geometry     : shapely geometry (Point, LineString, Polygon, etc.)
    source_id    : str   — unique identifier within the source dataset
    water_type   : str   — "river", "lake", "pan", "wetland", "floodplain",
                           "surface_water", etc.
    mechanism    : WaterMechanism enum — how the water gets there
    permanence   : str   — "permanent" | "seasonal" | "ephemeral"
    reliability  : float (0.0–1.0) — how reliably water is present
    months_water : int   (1–12) — typical months per year water is present
    region       : str   — geographic region label (e.g. "africa")

TEMPORAL DIMENSION:
-------------------
All source classes accept a `month` parameter (1–12) for future monthly
water availability modeling. Currently accepted but not yet implemented —
sources return static data regardless of month. JRCGlobalSurfaceWater will
be the first class to use it when the monthly recurrence layer is integrated.

ADDING A NEW SOURCE TYPE:
-------------------------
1. Create a new class inheriting from WaterSource
2. Implement load() — return a GeoDataFrame with the normalized schema
3. Register it in SOURCE_REGISTRY
4. Add tests in test_water_sources.py and/or test_water_sources_raster.py

Nothing else in the pipeline needs to change.
"""

import logging
import warnings
from abc import ABC, abstractmethod
from enum import Enum

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import rasterio.features
from rasterio.crs import CRS
from shapely.geometry import box, shape

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# WaterMechanism Enum
# ---------------------------------------------------------------------------


class WaterMechanism(Enum):
    """
    How water arrives at or exists within a given location.

    Using an Enum rather than plain strings means a typo in a source
    class definition raises an error immediately at definition time,
    not silently at runtime when a filter downstream fails to match.

    PERMANENT_SURFACE : Water present year-round on the surface.
                        Examples: perennial rivers, large lakes.

    SEASONAL_SURFACE  : Water present only part of the year on the surface.
                        Examples: seasonal pans, floodplains after rain,
                        ephemeral rivers in semi-arid regions, JRC GSW
                        pixels with occurrence < 100%.

    GROUNDWATER       : Water below the surface, accessible via springs,
                        seeps, or animal-dug wells.
                        Examples: aquifer zones, springs, boreholes.

    ARTIFICIAL        : Water created or maintained by human activity.
                        Examples: reservoirs, dams, park waterholes,
                        boreholes managed by conservancies.

    DERIVED           : Water inferred or modeled from other data sources
                        rather than directly observed.
                        Examples: NDVI-derived riparian corridors,
                        modeled groundwater potential zones.

    RAINFALL_DERIVED  : Water availability driven by rainfall patterns.
                        Not yet implemented — rainfall is a reliability
                        modifier on existing sources, not a source class.
                        Planned for Phase 2 (Predict) using CHIRPS data.
    """

    PERMANENT_SURFACE = "permanent_surface"
    SEASONAL_SURFACE = "seasonal_surface"
    GROUNDWATER = "groundwater"
    ARTIFICIAL = "artificial"
    DERIVED = "derived"
    RAINFALL_DERIVED = "rainfall_derived"


# ---------------------------------------------------------------------------
# WaterSource — Abstract Base Class
# ---------------------------------------------------------------------------


class WaterSource(ABC):
    """
    Abstract base class for all water source types.

    Every concrete water source class must implement load(), which returns
    a GeoDataFrame conforming to the normalized schema. This contract is
    what allows load_all_water() to combine any mix of source types without
    knowing anything about their internal structure.

    Args:
        filepath : Path to the source data file.
        bbox     : Optional bounding box (min_lon, min_lat, max_lon, max_lat)
                   in WGS84 degrees. If provided, only features intersecting
                   the bbox are returned. Raster subclasses use this as a
                   read window for memory efficiency rather than post-load
                   filtering.
        region   : Human-readable region label stored in the output schema.
                   Useful for filtering and debugging downstream.
        month    : Optional month (1–12) for temporal filtering. Accepted
                   by all source classes but only implemented by those with
                   monthly data layers (e.g. JRCGlobalSurfaceWater in future).
    """

    def __init__(
        self,
        filepath: str,
        bbox: tuple | None = None,
        region: str = "unknown",
        month: int | None = None,
    ):
        self.filepath = filepath
        self.bbox = bbox
        self.region = region
        self.month = month

    @abstractmethod
    def load(self) -> gpd.GeoDataFrame:
        """
        Load the source data and return a normalized GeoDataFrame.

        All subclasses must implement this method. The returned GeoDataFrame
        must contain every column in the normalized schema:
            geometry, source_id, water_type, mechanism, permanence,
            reliability, months_water, region
        """
        ...

    def _clip_to_bbox(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        Clip a GeoDataFrame to self.bbox if one was provided.

        Used by vector source classes (shapefiles). Raster source classes
        handle bbox as a read window in rasterio instead — see
        _bbox_to_window() in raster subclasses.

        Args:
            gdf: GeoDataFrame in EPSG:4326 to clip.

        Returns:
            Filtered GeoDataFrame. If no bbox was set, returns gdf unchanged.
        """
        if self.bbox is None:
            return gdf

        # box() creates a rectangular Polygon from (min_lon, min_lat, max_lon, max_lat)
        bbox_polygon = box(*self.bbox)
        return gdf[gdf.geometry.intersects(bbox_polygon)].copy()

    def _normalize(
        self,
        gdf: gpd.GeoDataFrame,
        water_type: str,
        mechanism: WaterMechanism,
        permanence: str,
        reliability: float,
        months_water: int,
    ) -> gpd.GeoDataFrame:
        """
        Apply the normalized schema to a raw loaded GeoDataFrame.

        Strips all source-specific columns and replaces them with the
        standard schema columns. This is what allows all source types to
        be combined by load_all_water() without column conflicts.

        Args:
            gdf          : Raw GeoDataFrame with at minimum a geometry column.
            water_type   : String label for this source type (e.g. "river").
            mechanism    : WaterMechanism enum value for this source type.
            permanence   : "permanent", "seasonal", or "ephemeral".
            reliability  : Float 0.0–1.0. How reliably water is present.
            months_water : Typical months per year water is present (1–12).

        Returns:
            GeoDataFrame with only the normalized schema columns.
        """
        result = gdf[["geometry"]].copy()

        result["source_id"] = [f"{water_type}_{i}" for i in range(len(result))]
        result["water_type"] = water_type
        result["mechanism"] = mechanism
        result["permanence"] = permanence
        result["reliability"] = reliability
        result["months_water"] = months_water
        result["region"] = self.region

        return result


# ---------------------------------------------------------------------------
# Vector Source Classes — Shapefile-based
# ---------------------------------------------------------------------------


class ShapefileRivers(WaterSource):
    """
    Loads river geometries from a shapefile (e.g. Natural Earth rivers).

    Rivers from Natural Earth are perennial — they flow year-round —
    so mechanism is PERMANENT_SURFACE, reliability is 1.0, and
    months_water is 12.

    As better river datasets are added (e.g. HydroRIVERS with stream
    order metadata), this class can be extended to set lower reliability
    values for smaller or intermittent streams.
    """

    def load(self) -> gpd.GeoDataFrame:
        """Load rivers shapefile and return normalized GeoDataFrame."""
        gdf = gpd.read_file(self.filepath)

        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")
        else:
            gdf = gdf.to_crs("EPSG:4326")

        gdf = self._clip_to_bbox(gdf)

        return self._normalize(
            gdf,
            water_type="river",
            mechanism=WaterMechanism.PERMANENT_SURFACE,
            permanence="permanent",
            reliability=1.0,
            months_water=12,
        )


class ShapefileLakes(WaterSource):
    """
    Loads lake geometries from a shapefile (e.g. Natural Earth lakes).

    Natural Earth lakes are permanent water bodies, so the same
    reasoning as ShapefileRivers applies — reliability 1.0, 12 months.

    Seasonal lakes and pans will be separate source classes when those
    datasets are added, because their reliability and months_water values
    are fundamentally different and should not be conflated with permanent
    lakes.
    """

    def load(self) -> gpd.GeoDataFrame:
        """Load lakes shapefile and return normalized GeoDataFrame."""
        gdf = gpd.read_file(self.filepath)

        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")
        else:
            gdf = gdf.to_crs("EPSG:4326")

        gdf = self._clip_to_bbox(gdf)

        return self._normalize(
            gdf,
            water_type="lake",
            mechanism=WaterMechanism.PERMANENT_SURFACE,
            permanence="permanent",
            reliability=1.0,
            months_water=12,
        )


# ---------------------------------------------------------------------------
# Raster Source Classes
# ---------------------------------------------------------------------------


class GLWDWetlands(WaterSource):
    """
    Loads wetland, pan, and floodplain geometries from the Global Lakes
    and Wetlands Database v2 (GLWD v2) GeoTIFF.

    GLWD v2 has 33 classes. We vectorize the classes relevant to wildlife
    water access into polygons using rasterio.features.shapes().

    CLASS MAP (GLWD v2):
    --------------------
    2  = Saline lake         → saline_lake     (permanent, reliability 0.4)
    6  = Other permanent     → permanent_water  (permanent, reliability 0.9)
    8  = Lacustrine forested → wetland          (seasonal,  reliability 0.7)
    9  = Lacustrine non-for  → wetland          (seasonal,  reliability 0.6)
    10 = Riverine reg. flood forested   → floodplain (seasonal, 0.8)
    11 = Riverine reg. flood non-for    → floodplain (seasonal, 0.8)
    12 = Riverine seas. flood forested  → floodplain (seasonal, 0.7)
    13 = Riverine seas. flood non-for   → floodplain (seasonal, 0.7)
    16 = Palustrine reg. flood forested → wetland    (seasonal, 0.7)
    17 = Palustrine reg. flood non-for  → wetland    (seasonal, 0.7)
    18 = Palustrine seas. sat. forested → wetland    (seasonal, 0.5)
    19 = Palustrine seas. sat. non-for  → wetland    (seasonal, 0.5)
    21 = Ephemeral non-forested         → pan        (ephemeral, 0.3)
    32 = Salt pan, saline/brackish      → pan        (seasonal,  0.5)

    EXCLUDED FROM DEFAULTS:
    -----------------------
    Class 1 (Freshwater lake) — Natural Earth lakes already cover this
    Class 4 (Large river)     — Natural Earth rivers as lines are
                                geometrically better for distance calc

    PHANTOM THIRST FIX:
    -------------------
    Etosha Pan = class 2 (saline lake) + class 32 (salt pan) around edges
    Makgadikgadi/Sua Pan = class 32 (salt pan, saline/brackish wetland)
    These were completely invisible in the old v1 class mapping {4, 7, 9}.

    Args:
        water_classes : Set of GLWD class integers to include.
                        None → use DEFAULT_WATER_CLASSES
                        Empty set → raises ValueError immediately
    """

    CLASS_MAP: dict[int, dict] = {
        2: {
            "water_type": "saline_lake",
            "mechanism": WaterMechanism.PERMANENT_SURFACE,
            "permanence": "permanent",
            "reliability": 0.4,
            "months_water": 12,
        },
        6: {
            "water_type": "permanent_water",
            "mechanism": WaterMechanism.PERMANENT_SURFACE,
            "permanence": "permanent",
            "reliability": 0.9,
            "months_water": 12,
        },
        8: {
            "water_type": "wetland",
            "mechanism": WaterMechanism.SEASONAL_SURFACE,
            "permanence": "seasonal",
            "reliability": 0.7,
            "months_water": 8,
        },
        9: {
            "water_type": "wetland",
            "mechanism": WaterMechanism.SEASONAL_SURFACE,
            "permanence": "seasonal",
            "reliability": 0.6,
            "months_water": 6,
        },
        10: {
            "water_type": "floodplain",
            "mechanism": WaterMechanism.SEASONAL_SURFACE,
            "permanence": "seasonal",
            "reliability": 0.8,
            "months_water": 8,
        },
        11: {
            "water_type": "floodplain",
            "mechanism": WaterMechanism.SEASONAL_SURFACE,
            "permanence": "seasonal",
            "reliability": 0.8,
            "months_water": 8,
        },
        12: {
            "water_type": "floodplain",
            "mechanism": WaterMechanism.SEASONAL_SURFACE,
            "permanence": "seasonal",
            "reliability": 0.7,
            "months_water": 6,
        },
        13: {
            "water_type": "floodplain",
            "mechanism": WaterMechanism.SEASONAL_SURFACE,
            "permanence": "seasonal",
            "reliability": 0.7,
            "months_water": 6,
        },
        16: {
            "water_type": "wetland",
            "mechanism": WaterMechanism.SEASONAL_SURFACE,
            "permanence": "seasonal",
            "reliability": 0.7,
            "months_water": 8,
        },
        17: {
            "water_type": "wetland",
            "mechanism": WaterMechanism.SEASONAL_SURFACE,
            "permanence": "seasonal",
            "reliability": 0.7,
            "months_water": 8,
        },
        18: {
            "water_type": "wetland",
            "mechanism": WaterMechanism.SEASONAL_SURFACE,
            "permanence": "seasonal",
            "reliability": 0.5,
            "months_water": 4,
        },
        19: {
            "water_type": "wetland",
            "mechanism": WaterMechanism.SEASONAL_SURFACE,
            "permanence": "seasonal",
            "reliability": 0.5,
            "months_water": 4,
        },
        21: {
            "water_type": "pan",
            "mechanism": WaterMechanism.SEASONAL_SURFACE,
            "permanence": "ephemeral",
            "reliability": 0.3,
            "months_water": 2,
        },
        32: {
            "water_type": "pan",
            "mechanism": WaterMechanism.SEASONAL_SURFACE,
            "permanence": "seasonal",
            "reliability": 0.5,
            "months_water": 4,
        },
    }

    # Classes 1 (freshwater lake) and 4 (large river) intentionally excluded
    # — covered by Natural Earth sources which have better geometry types
    DEFAULT_WATER_CLASSES = {2, 6, 8, 9, 10, 11, 12, 13, 16, 17, 18, 19, 21, 32}

    def __init__(
        self,
        filepath: str,
        bbox: tuple | None = None,
        region: str = "unknown",
        month: int | None = None,
        water_classes: set[int] | None = None,
    ):
        super().__init__(filepath, bbox, region, month)

        if water_classes is not None and len(water_classes) == 0:
            raise ValueError("water_classes must not be empty. Pass None to use the defaults.")

        self.water_classes = water_classes if water_classes is not None else self.DEFAULT_WATER_CLASSES

        if month is not None:
            logger.debug("GLWDWetlands: month=%d provided but monthly filtering is not yet implemented for GLWD. Returning static data.", month)

    def load(self) -> gpd.GeoDataFrame:
        """
        Load GLWD raster, vectorize requested wetland classes, and return
        a normalized GeoDataFrame.

        Uses a rasterio read window when bbox is provided — only the pixels
        within the bbox are loaded into memory. This is critical for the
        global GLWD raster which would otherwise exhaust RAM on a laptop.
        """
        all_features = []

        with rasterio.open(self.filepath) as src:
            if self.bbox is not None:
                # Convert bbox to a pixel-coordinate window —
                # only reads the rows/cols that intersect the bbox
                window = src.window(*self.bbox)
                data = src.read(1, window=window)
                transform = src.window_transform(window)
            else:
                data = src.read(1)
                transform = src.meta["transform"]

            crs = src.meta["crs"]

            for glwd_class in self.water_classes:
                if glwd_class not in self.CLASS_MAP:
                    logger.debug("GLWDWetlands: class %d not in CLASS_MAP, skipping.", glwd_class)
                    continue

                class_meta = self.CLASS_MAP[glwd_class]
                mask = (data == glwd_class).astype(np.uint8)

                for geom_dict, value in rasterio.features.shapes(mask, transform=transform):
                    if value != 1:
                        continue

                    all_features.append(
                        {
                            "geometry": shape(geom_dict),
                            "water_type": class_meta["water_type"],
                            "mechanism": class_meta["mechanism"],
                            "permanence": class_meta["permanence"],
                            "reliability": class_meta["reliability"],
                            "months_water": class_meta["months_water"],
                        }
                    )

        if not all_features:
            return gpd.GeoDataFrame(
                columns=["geometry", "source_id", "water_type", "mechanism", "permanence", "reliability", "months_water", "region"],
                crs="EPSG:4326",
            )

        gdf = gpd.GeoDataFrame(all_features, crs=CRS.to_epsg(crs) if crs else "EPSG:4326")

        if gdf.crs is None or gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs("EPSG:4326")
        else:
            gdf = gdf.set_crs("EPSG:4326")

        gdf = self._clip_to_bbox(gdf)

        gdf["source_id"] = [f"{row['water_type']}_{i}" for i, row in enumerate(all_features[: len(gdf)])]
        gdf["region"] = self.region

        return gdf[["geometry", "source_id", "water_type", "mechanism", "permanence", "reliability", "months_water", "region"]]


class JRCGlobalSurfaceWater(WaterSource):
    """
    Loads surface water geometries from the JRC Global Surface Water dataset.

    JRC GSW is a raster dataset derived from Landsat imagery (1984–2021)
    where each pixel has an "occurrence" value 0–100 representing the
    percentage of time water was observed at that location. A value of 80
    means water was present in 80% of all observations.

    We vectorize pixels at or above a minimum occurrence threshold into
    polygons. The threshold controls the trade-off between:
    - Low threshold (e.g. 10): includes ephemeral water, more coverage,
      more false positives in desert regions
    - High threshold (e.g. 75): permanent water only, less coverage,
      fewer false positives

    Default min_occurrence=10 is deliberately inclusive — we'd rather
    show elephants near occasional water than miss it entirely. The
    reliability score (occurrence / 100) tells the scoring model how
    dependable each pixel is.

    TEMPORAL NOTE:
    --------------
    JRC GSW has a monthly recurrence layer we plan to use in Phase 2.
    The month parameter is accepted now but not yet implemented — when
    it is, reliability will become month-specific rather than a static
    occurrence average.

    Args:
        min_occurrence : Minimum occurrence percentage (0–100) to include.
                         Default 10 — include pixels with water present
                         at least 10% of the time.
    """

    def __init__(
        self,
        filepath: str,
        bbox: tuple | None = None,
        region: str = "unknown",
        month: int | None = None,
        min_occurrence: int = 10,
    ):
        super().__init__(filepath, bbox, region, month)
        self.min_occurrence = min_occurrence

        if month is not None:
            # Monthly recurrence layer integration is planned for Phase 2.
            # When implemented, reliability will be derived from the monthly
            # layer rather than the static occurrence average.
            logger.debug("JRCGlobalSurfaceWater: month=%d provided but monthly filtering is not yet implemented. Returning static occurrence data.", month)

    def load(self) -> gpd.GeoDataFrame:
        """
        Load JRC GSW raster, vectorize pixels at or above min_occurrence,
        and return a normalized GeoDataFrame.

        Each resulting polygon gets:
        - reliability = occurrence_value / 100
        - months_water = derived from reliability (reliability * 12, rounded)
          This is a proxy until the JRC seasonality layer is integrated.
        """
        all_features = []

        with rasterio.open(self.filepath) as src:
            data = src.read(1)  # band 1 — occurrence values 0–100
            transform = src.meta["transform"]
            crs = src.meta["crs"]

            # Create a boolean mask of pixels at or above the threshold
            mask = (data >= self.min_occurrence).astype(np.uint8)

            # Vectorize — each contiguous region of qualifying pixels becomes
            # one polygon. We also need the original occurrence values to set
            # reliability per feature, so we pass data as the source array.
            for geom_dict, value in rasterio.features.shapes(data, mask=mask, transform=transform):
                occurrence = float(value)
                reliability = occurrence / 100.0

                # Proxy for months_water until seasonality layer is available:
                # if water is present 50% of the time → ~6 months
                # Clamp between 1 and 12
                months_water = max(1, min(12, round(reliability * 12)))

                all_features.append(
                    {
                        "geometry": shape(geom_dict),
                        "water_type": "surface_water",
                        "mechanism": WaterMechanism.SEASONAL_SURFACE,
                        "permanence": "seasonal",
                        "reliability": reliability,
                        "months_water": months_water,
                    }
                )

        if not all_features:
            return gpd.GeoDataFrame(
                columns=["geometry", "source_id", "water_type", "mechanism", "permanence", "reliability", "months_water", "region"],
                crs="EPSG:4326",
            )

        gdf = gpd.GeoDataFrame(all_features, crs=CRS.to_epsg(crs) if crs else "EPSG:4326")

        if gdf.crs is None or gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs("EPSG:4326")
        else:
            gdf = gdf.set_crs("EPSG:4326")

        gdf = self._clip_to_bbox(gdf)

        gdf["source_id"] = [f"surface_water_{i}" for i in range(len(gdf))]
        gdf["region"] = self.region

        return gdf[["geometry", "source_id", "water_type", "mechanism", "permanence", "reliability", "months_water", "region"]]


# ---------------------------------------------------------------------------
# Source Registry
# ---------------------------------------------------------------------------

# Maps config dict keys to the concrete source class that handles them.
# Add new source classes here when they're implemented.
SOURCE_REGISTRY: dict[str, type[WaterSource]] = {
    "rivers": ShapefileRivers,
    "lakes": ShapefileLakes,
    "glwd": GLWDWetlands,
    "jrc_gsw": JRCGlobalSurfaceWater,
}


# ---------------------------------------------------------------------------
# load_all_water — Registry Function
# ---------------------------------------------------------------------------


def load_all_water(
    config: dict,
    bbox: tuple | None = None,
    month: int | None = None,
) -> gpd.GeoDataFrame:
    """
    Load and combine all water sources defined in a config dict.

    This is the recommended entry point for the pipeline. It reads the
    "sources" key from config, instantiates the appropriate source class
    for each entry, loads and normalizes each one, then combines them
    into a single GeoDataFrame ready for the analytics layer.

    Args:
        config : Dict with a "sources" key mapping source names to their
                 configuration. Each source entry must have a "path" key.

                 Example:
                 {
                     "sources": {
                         "rivers":  {"path": "data/raw/water/rivers/...shp"},
                         "lakes":   {"path": "data/raw/water/lakes/...shp"},
                         "glwd":    {"path": "data/raw/water/glwd/...tif"},
                         "jrc_gsw": {"path": "data/raw/water/jrc/...tif",
                                     "min_occurrence": 10},
                     }
                 }

        bbox   : Optional bounding box (min_lon, min_lat, max_lon, max_lat)
                 in WGS84 degrees. Passed to each source class.
                 WARNING: Omitting bbox on large global datasets will load
                 everything into memory. Always provide bbox in production.

        month  : Optional month (1–12) for temporal filtering. Passed to
                 each source class. Currently accepted but only implemented
                 by source classes that have monthly data layers.

    Returns:
        Combined GeoDataFrame with the normalized schema.

    Raises:
        KeyError: If a source name in config is not in SOURCE_REGISTRY.
    """
    if bbox is None:
        warnings.warn(
            "load_all_water() called without a bbox. This will load the entire dataset into memory. Provide a bbox=(min_lon, min_lat, max_lon, max_lat) to limit the spatial extent.",
            UserWarning,
            stacklevel=2,
        )

    loaded_layers = []

    for source_name, source_config in config["sources"].items():
        if source_name not in SOURCE_REGISTRY:
            raise KeyError(f"Unknown source type '{source_name}'. Available types: {list(SOURCE_REGISTRY.keys())}")

        source_class = SOURCE_REGISTRY[source_name]

        # Build kwargs — start with the common parameters every source accepts
        kwargs = {
            "filepath": source_config["path"],
            "bbox": bbox,
            "region": source_config.get("region", "unknown"),
            "month": month,
        }

        # Pass through source-specific parameters if provided in config.
        # This allows jrc_gsw to accept min_occurrence, glwd to accept
        # water_classes, etc. without load_all_water() needing to know
        # about source-specific parameters explicitly.
        if "min_occurrence" in source_config:
            kwargs["min_occurrence"] = source_config["min_occurrence"]
        if "water_classes" in source_config:
            kwargs["water_classes"] = source_config["water_classes"]

        source = source_class(**kwargs)
        loaded_layers.append(source.load())

    combined = pd.concat(loaded_layers, ignore_index=True)
    return gpd.GeoDataFrame(combined, crs="EPSG:4326")


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------
# For loading a single source type directly without the registry machinery.
# For pipelines that need multiple source types combined, use load_all_water().


def load_rivers(filepath: str) -> gpd.GeoDataFrame:
    """
    Load a rivers shapefile and return a WGS84 GeoDataFrame.

    Convenience wrapper around ShapefileRivers for simple single-source
    use cases. Does NOT include the normalized schema — preserves original
    shapefile columns. Use load_all_water() if you need the normalized schema.
    """
    gdf = gpd.read_file(filepath)

    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    else:
        gdf = gdf.to_crs("EPSG:4326")

    return gdf


def load_lakes(filepath: str) -> gpd.GeoDataFrame:
    """
    Load a lakes shapefile and return a WGS84 GeoDataFrame.

    Same reasoning as load_rivers() — convenience wrapper for simple
    single-source use cases without the normalized schema.
    """
    gdf = gpd.read_file(filepath)

    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    else:
        gdf = gdf.to_crs("EPSG:4326")

    return gdf


def combine_water_layers(*layers: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Combine multiple water GeoDataFrames into a single GeoDataFrame.

    All input layers must be in EPSG:4326. Columns present in some layers
    but not others will be filled with NaN.
    """
    combined = pd.concat(layers, ignore_index=True)
    return gpd.GeoDataFrame(combined, crs="EPSG:4326")
