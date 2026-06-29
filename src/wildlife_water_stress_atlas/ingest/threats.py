"""
threats.py

Human threat source ingestion for the Wildlife Water Stress Atlas.

ARCHITECTURE:
-------------
Follows the same source-class pattern as ingest/water.py.
Each threat type is a class with a load() method that returns a normalized
GeoDataFrame. load_all_threats() combines multiple sources via a config dict.

NORMALIZED SCHEMA:
------------------
    geometry   : LineString (or Polygon) in EPSG:4326
    source_id  : str — unique identifier per feature
    road_class : str — one of KNOWN_ROAD_CLASSES
    region     : str — geographic region label (default "africa")

ADDING A NEW THREAT SOURCE TYPE:
---------------------------------
1. Create a class with a load() method returning the normalized schema
2. Register it in THREAT_SOURCE_REGISTRY
3. Add tests in test_threats_ingest.py
"""

import warnings

import geopandas as gpd
from shapely.geometry import box

# ---------------------------------------------------------------------------
# OSM highway tag → KNOWN_ROAD_CLASSES mapping
# ---------------------------------------------------------------------------
# Maps OSM `highway` tag values to our threat model's road classes.
# _link variants (on/off ramps) are grouped with their parent class —
# ecologically they present the same barrier as the parent road.
# Unknown OSM values (residential, service, etc.) are absent from this
# map and will be silently dropped during ingestion.

OSM_HIGHWAY_MAP: dict[str, str] = {
    "motorway": "motorway",
    "motorway_link": "motorway",
    "trunk": "trunk",
    "trunk_link": "trunk",
    "primary": "primary",
    "primary_link": "primary",
    "secondary": "secondary",
    "secondary_link": "secondary",
    "tertiary": "tertiary",
    "tertiary_link": "tertiary",
    "track": "track",
    "path": "path",
    "footway": "path",
    "cycleway": "path",
    "bridleway": "path",
}


# ---------------------------------------------------------------------------
# OSMRoads source class
# ---------------------------------------------------------------------------


class OSMRoads:
    """
    Loads road geometries from an OSM-derived GeoPackage or Shapefile.

    Maps the OSM `highway` tag to our KNOWN_ROAD_CLASSES via OSM_HIGHWAY_MAP.
    Unknown highway values are silently dropped — they are not in our threat model.

    Args:
        filepath : Path to the OSM GeoPackage or Shapefile.
        bbox     : Optional (min_lon, min_lat, max_lon, max_lat) in WGS84.
                   Features outside the bbox are dropped after loading.
        region   : Region label stored in the output schema. Default "africa".
    """

    def __init__(
        self,
        filepath: str,
        bbox: tuple | None = None,
        region: str = "africa",
    ):
        self.filepath = filepath
        self.bbox = bbox
        self.region = region

    def load(self) -> gpd.GeoDataFrame:
        """
        Load and normalize OSM road data.

        Returns:
            GeoDataFrame with normalized schema:
            geometry, source_id, road_class, region — all in EPSG:4326.
        """
        raw = gpd.read_file(self.filepath)

        if raw.crs is None:
            raw = raw.set_crs("EPSG:4326")
        elif raw.crs.to_epsg() != 4326:
            raw = raw.to_crs(epsg=4326)

        # Map OSM highway tag to road_class — drop any unknown values
        raw["road_class"] = raw["highway"].map(OSM_HIGHWAY_MAP)
        raw = raw[raw["road_class"].notna()].copy()

        if raw.empty:
            return gpd.GeoDataFrame(
                columns=["geometry", "source_id", "road_class", "region"],
                geometry="geometry",
                crs="EPSG:4326",
            )

        if self.bbox is not None:
            bbox_polygon = box(*self.bbox)
            raw = raw[raw.geometry.intersects(bbox_polygon)].copy()

        result = raw[["geometry", "road_class"]].copy()
        result["source_id"] = [f"road_{i}" for i in range(len(result))]
        result["region"] = self.region

        return gpd.GeoDataFrame(result, geometry="geometry", crs="EPSG:4326")


# ---------------------------------------------------------------------------
# Registry and load_all_threats
# ---------------------------------------------------------------------------

THREAT_SOURCE_REGISTRY: dict[str, type] = {
    "osm_roads": OSMRoads,
}


def load_all_threats(
    config: dict,
    bbox: tuple | None = None,
) -> gpd.GeoDataFrame:
    """
    Load and combine all threat sources defined in a config dict.

    Mirrors load_all_water() from ingest/water.py.

    Args:
        config : Dict with a "sources" key mapping source names to config.
                 Each source entry must have a "path" key.

                 Example:
                 {
                     "sources": {
                         "osm_roads": {"path": "data/raw/threats/roads.gpkg"},
                     }
                 }

        bbox   : Optional (min_lon, min_lat, max_lon, max_lat) in WGS84.
                 WARNING: Omitting bbox on a continental dataset will load
                 everything into memory. Always provide bbox in production.

    Returns:
        Combined GeoDataFrame with the normalized threat schema.

    Raises:
        KeyError: If a source name is not in THREAT_SOURCE_REGISTRY.
    """
    if bbox is None:
        warnings.warn(
            "load_all_threats() called without a bbox. This will load the entire dataset into memory. Provide a bbox=(min_lon, min_lat, max_lon, max_lat) to limit the spatial extent.",
            UserWarning,
            stacklevel=2,
        )

    import pandas as pd

    loaded_layers = []

    for source_name, source_config in config["sources"].items():
        if source_name not in THREAT_SOURCE_REGISTRY:
            raise KeyError(f"Unknown source type '{source_name}'. Available types: {list(THREAT_SOURCE_REGISTRY.keys())}")

        source_class = THREAT_SOURCE_REGISTRY[source_name]
        source = source_class(
            filepath=source_config["path"],
            bbox=bbox,
            region=source_config.get("region", "africa"),
        )
        loaded_layers.append(source.load())

    combined = pd.concat(loaded_layers, ignore_index=True)
    return gpd.GeoDataFrame(combined, crs="EPSG:4326")
