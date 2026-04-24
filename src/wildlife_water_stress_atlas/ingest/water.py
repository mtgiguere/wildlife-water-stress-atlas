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
    SEASONAL_SURFACE  = "seasonal_surface"
    GROUNDWATER       = "groundwater"
    ARTIFICIAL        = "artificial"
    DERIVED           = "derived"
    RAINFALL_DERIVED  = "rainfall_derived"


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

        result["source_id"]    = [f"{water_type}_{i}" for i in range(len(result))]
        result["water_type"]   = water_type
        result["mechanism"]    = mechanism
        result["permanence"]   = permanence
        result["reliability"]  = reliability
        result["months_water"] = months_water
        result["region"]       = self.region

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
            water_type   = "river",
            mechanism    = WaterMechanism.PERMANENT_SURFACE,
            permanence   = "permanent",
            reliability  = 1.0,
            months_water = 12,
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
            water_type   = "lake",
            mechanism    = WaterMechanism.PERMANENT_SURFACE,
            permanence   = "permanent",
            reliability  = 1.0,
            months_water = 12,
        )


# ---------------------------------------------------------------------------
# Raster Source Classes
# ---------------------------------------------------------------------------

class GLWDWetlands(WaterSource):
    """
    Loads wetland, pan, and floodplain geometries from the Global Lakes
    and Wetlands Database v2 (GLWD v2) GeoTIFF.

    GLWD v2 is a raster dataset where each pixel has a class value (1–12)
    describing the wetland type. We vectorize the pixels we care about into
    polygons using rasterio.features.shapes(), which traces the outlines of
    adjacent same-value pixels into geometries.

    CLASSES WE USE:
    ---------------
    Class 4 — Floodplains       : Seasonal inundation along river systems
    Class 7 — Pans / Playas     : Etosha, Makgadikgadi, Sua — critical for
                                  elephants but invisible in the current data
    Class 9 — Wetlands          : Intermittent wetlands, seasonally flooded

    These three classes are what fix the phantom thirst bug — elephants near
    Etosha Pan appear high-stress because class 7 pans don't exist in the
    current shapefile-only data.

    RELIABILITY VALUES:
    -------------------
    These are heuristic placeholders, honest about being estimates:
    - Floodplains (4): reliability=0.7, months_water=6
    - Pans (7):        reliability=0.6, months_water=4
    - Wetlands (9):    reliability=0.5, months_water=3

    Args:
        water_classes : Set of GLWD class integers to include.
                        None → use defaults {4, 7, 9}
                        Empty set → raises ValueError immediately
    """

    # Maps GLWD class integer → normalized schema values for that class.
    # This is the single place to update if reliability estimates are revised.
    CLASS_MAP: dict[int, dict] = {
        4: {
            "water_type":   "floodplain",
            "permanence":   "seasonal",
            "reliability":  0.7,
            "months_water": 6,
        },
        7: {
            "water_type":   "pan",
            "permanence":   "seasonal",
            "reliability":  0.6,
            "months_water": 4,
        },
        9: {
            "water_type":   "wetland",
            "permanence":   "seasonal",
            "reliability":  0.5,
            "months_water": 3,
        },
    }

    DEFAULT_WATER_CLASSES = {4, 7, 9}

    def __init__(
        self,
        filepath: str,
        bbox: tuple | None = None,
        region: str = "unknown",
        month: int | None = None,
        water_classes: set[int] | None = None,
    ):
        super().__init__(filepath, bbox, region, month)

        # Validate water_classes before storing — fail loudly at construction
        # time rather than silently at load() time
        if water_classes is not None and len(water_classes) == 0:
            raise ValueError(
                "water_classes must not be empty. "
                "Pass None to use the defaults {4, 7, 9}."
            )

        # None means "use the defaults" — we resolve it here so the rest of
        # the class can always treat self.water_classes as a plain set
        self.water_classes = water_classes if water_classes is not None else self.DEFAULT_WATER_CLASSES

        if month is not None:
            # Month-aware loading is planned for Phase 2 but not yet
            # implemented for GLWD (which lacks monthly resolution).
            # We log rather than raise so pipelines don't break.
            logger.debug(
                "GLWDWetlands: month=%d provided but monthly filtering is not "
                "yet implemented for GLWD. Returning static data.", month
            )

    def load(self) -> gpd.GeoDataFrame:
        """
        Load GLWD raster, vectorize requested wetland classes, and return
        a normalized GeoDataFrame.

        VECTORIZATION PROCESS:
        ----------------------
        1. Open the GeoTIFF with rasterio
        2. Read band 1 as a 2D numpy array of class values
        3. For each requested class, mask the array to that class value
        4. Use rasterio.features.shapes() to trace pixel outlines into polygons
        5. Attach schema values for that class
        6. Combine all classes into one GeoDataFrame
        """
        all_features = []

        with rasterio.open(self.filepath) as src:
            data      = src.read(1)       # band 1 — class values
            transform = src.meta["transform"]
            crs       = src.meta["crs"]

            for glwd_class in self.water_classes:
                # Skip classes not in our mapping — unknown values are ignored
                # gracefully rather than raising, so future GLWD versions with
                # new class values don't break the pipeline
                if glwd_class not in self.CLASS_MAP:
                    logger.debug(
                        "GLWDWetlands: class %d not in CLASS_MAP, skipping.", glwd_class
                    )
                    continue

                class_meta = self.CLASS_MAP[glwd_class]

                # Create a boolean mask: True where pixel == this class
                mask = (data == glwd_class).astype(np.uint8)

                # rasterio.features.shapes() traces the outlines of contiguous
                # regions in the mask and yields (geometry_dict, value) tuples.
                # We only want regions where value == 1 (i.e. our class pixels).
                for geom_dict, value in rasterio.features.shapes(mask, transform=transform):
                    if value != 1:
                        continue

                    all_features.append({
                        "geometry":    shape(geom_dict),
                        "water_type":  class_meta["water_type"],
                        "permanence":  class_meta["permanence"],
                        "reliability": class_meta["reliability"],
                        "months_water": class_meta["months_water"],
                    })

        if not all_features:
            # Return an empty GeoDataFrame with the correct schema
            return gpd.GeoDataFrame(
                columns=["geometry", "source_id", "water_type", "mechanism",
                         "permanence", "reliability", "months_water", "region"],
                crs="EPSG:4326",
            )

        gdf = gpd.GeoDataFrame(all_features, crs=CRS.to_epsg(crs) if crs else "EPSG:4326")

        # Reproject to WGS84 if needed — GLWD v2 is distributed in WGS84
        # but we enforce it explicitly for safety
        if gdf.crs is None or gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs("EPSG:4326")
        else:
            gdf = gdf.set_crs("EPSG:4326")

        # Apply bbox clipping if provided
        gdf = self._clip_to_bbox(gdf)

        # Add the remaining normalized schema columns
        gdf["source_id"] = [f"{row['water_type']}_{i}" for i, row in enumerate(all_features[:len(gdf)])]
        gdf["mechanism"] = WaterMechanism.SEASONAL_SURFACE
        gdf["region"]    = self.region

        return gdf[["geometry", "source_id", "water_type", "mechanism",
                    "permanence", "reliability", "months_water", "region"]]


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
            logger.debug(
                "JRCGlobalSurfaceWater: month=%d provided but monthly filtering "
                "is not yet implemented. Returning static occurrence data.", month
            )

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
            data      = src.read(1)        # band 1 — occurrence values 0–100
            transform = src.meta["transform"]
            crs       = src.meta["crs"]

            # Create a boolean mask of pixels at or above the threshold
            mask = (data >= self.min_occurrence).astype(np.uint8)

            # Vectorize — each contiguous region of qualifying pixels becomes
            # one polygon. We also need the original occurrence values to set
            # reliability per feature, so we pass data as the source array.
            for geom_dict, value in rasterio.features.shapes(data, mask=mask, transform=transform):
                occurrence  = float(value)
                reliability = occurrence / 100.0

                # Proxy for months_water until seasonality layer is available:
                # if water is present 50% of the time → ~6 months
                # Clamp between 1 and 12
                months_water = max(1, min(12, round(reliability * 12)))

                all_features.append({
                    "geometry":    shape(geom_dict),
                    "water_type":  "surface_water",
                    "mechanism":   WaterMechanism.SEASONAL_SURFACE,
                    "permanence":  "seasonal",
                    "reliability": reliability,
                    "months_water": months_water,
                })

        if not all_features:
            return gpd.GeoDataFrame(
                columns=["geometry", "source_id", "water_type", "mechanism",
                         "permanence", "reliability", "months_water", "region"],
                crs="EPSG:4326",
            )

        gdf = gpd.GeoDataFrame(all_features, crs=CRS.to_epsg(crs) if crs else "EPSG:4326")

        if gdf.crs is None or gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs("EPSG:4326")
        else:
            gdf = gdf.set_crs("EPSG:4326")

        gdf = self._clip_to_bbox(gdf)

        gdf["source_id"] = [f"surface_water_{i}" for i in range(len(gdf))]
        gdf["region"]    = self.region

        return gdf[["geometry", "source_id", "water_type", "mechanism",
                    "permanence", "reliability", "months_water", "region"]]


# ---------------------------------------------------------------------------
# Source Registry
# ---------------------------------------------------------------------------

# Maps config dict keys to the concrete source class that handles them.
# Add new source classes here when they're implemented.
SOURCE_REGISTRY: dict[str, type[WaterSource]] = {
    "rivers":  ShapefileRivers,
    "lakes":   ShapefileLakes,
    "glwd":    GLWDWetlands,
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
            "load_all_water() called without a bbox. This will load the entire "
            "dataset into memory. Provide a bbox=(min_lon, min_lat, max_lon, max_lat) "
            "to limit the spatial extent.",
            UserWarning,
            stacklevel=2,
        )

    loaded_layers = []

    for source_name, source_config in config["sources"].items():
        if source_name not in SOURCE_REGISTRY:
            raise KeyError(
                f"Unknown source type '{source_name}'. "
                f"Available types: {list(SOURCE_REGISTRY.keys())}"
            )

        source_class = SOURCE_REGISTRY[source_name]

        # Build kwargs — start with the common parameters every source accepts
        kwargs = {
            "filepath": source_config["path"],
            "bbox":     bbox,
            "region":   source_config.get("region", "unknown"),
            "month":    month,
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