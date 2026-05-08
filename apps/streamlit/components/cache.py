"""
cache.py

Caching layer for the Wildlife Water Stress Atlas Streamlit app.

WHY THIS FILE EXISTS:
---------------------
Loading water sources (GLWD raster vectorization) and GBIF occurrence
data are expensive operations that can take several minutes. This module
provides two cached loader functions that:

1. Check for a pre-built GeoPackage in data/processed/
2. If found — load instantly from disk
3. If not found — run the full pipeline with a Streamlit spinner,
   then save to disk for future runs

Both functions are wrapped with @st.cache_data so Streamlit only
executes them once per session regardless of how many times the
app re-renders.

CACHE FILES:
------------
data/processed/water_africa.gpkg          — vectorized water layer
data/processed/gbif_{species_name}.gpkg — per-species occurrence cache
                                           path determined by SPECIES_CONFIG
Year filtering for the animation slider is done IN MEMORY from the
cached GBIF GeoDataFrame — no API calls after the first load.
"""

from pathlib import Path

import geopandas as gpd
import streamlit as st

from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG
from wildlife_water_stress_atlas.ingest.gbif import fetch_all_occurrences, occurrences_to_gdf
from wildlife_water_stress_atlas.ingest.water import load_all_water

# ---------------------------------------------------------------------------
# Cache file paths
# ---------------------------------------------------------------------------


WATER_CACHE_PATH = Path("data/processed/water_africa.gpkg")
WATER_SIMPLIFIED_CACHE_PATH = Path("data/processed/water_africa_simplified.gpkg")

# Africa bounding box — passed to load_all_water() to prevent
# loading global rasters into memory
AFRICA_BBOX = (-20, -40, 55, 40)

# Water source config — mirrors plot_elephants.py
WATER_CONFIG = {
    "sources": {
        "rivers": {
            "path": "data/raw/water/rivers/ne_10m_rivers_lake_centerlines_scale_rank.shp",
            "region": "africa",
        },
        "glwd": {
            "path": "data/raw/water/glwd/GLWD_v2_0_main_class.tif",
            "region": "africa",
        },
    }
}


# ---------------------------------------------------------------------------
# Water layer cache
# ---------------------------------------------------------------------------


@st.cache_data
def load_water_layer() -> gpd.GeoDataFrame:
    """
    Load the Africa water layer, using disk cache when available.

    First run: runs the full load_all_water() pipeline (several minutes
    for GLWD raster vectorization), saves result to WATER_CACHE_PATH.
    Subsequent runs: loads from GeoPackage instantly.

    Returns:
        GeoDataFrame with normalized water schema in EPSG:4326.
    """
    if WATER_CACHE_PATH.exists():
        return gpd.read_file(WATER_CACHE_PATH)

    with st.spinner("Building water layer cache — this will take a few minutes on first run..."):
        water = load_all_water(WATER_CONFIG, bbox=AFRICA_BBOX)

    WATER_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    water.to_file(WATER_CACHE_PATH, driver="GPKG")

    return water


# ---------------------------------------------------------------------------
# GBIF occurrence cache
# ---------------------------------------------------------------------------


@st.cache_data
def load_gbif_data(
    species: str = "Loxodonta africana",
    year: int | None = None,
    _cache_dir: Path = Path("data/processed"),
) -> gpd.GeoDataFrame:
    """
    Load GBIF occurrence data for any species in SPECIES_CONFIG.

    Cache file path is determined by the species' gbif_cache_file
    field in SPECIES_CONFIG — no hardcoded filenames anywhere.
    Adding a new species to SPECIES_CONFIG is all that's needed —
    this function picks up the new cache path automatically.

    First run: fetches all records from GBIF API, saves to cache.
    Subsequent runs: loads from GeoPackage instantly.

    Year filtering is done IN MEMORY — no API calls after first load.
    This makes the animation slider instant regardless of species.

    Args:
        species    : Scientific name — must be a key in SPECIES_CONFIG.
        year       : Optional year to filter by. None returns all records.
        _cache_dir : Directory for cache files. Underscore prefix tells
                     @st.cache_data not to hash this parameter — allows
                     dependency injection for testing without breaking
                     Streamlit's caching mechanism.

    Returns:
        GeoDataFrame of occurrence points in EPSG:4326.
    """
    if species not in SPECIES_CONFIG:
        raise ValueError(f"Unknown species: {species}. Must be one of {list(SPECIES_CONFIG.keys())}")

    cfg = SPECIES_CONFIG[species]
    # Cache path derived from SPECIES_CONFIG — never hardcoded
    cache_path = _cache_dir / cfg["gbif_cache_file"]

    if cache_path.exists():
        gdf = gpd.read_file(cache_path)
    else:
        common_name = cfg["common_name"]
        with st.spinner(f"Fetching {common_name} ({species}) records from GBIF..."):
            records = fetch_all_occurrences(species)
            gdf = occurrences_to_gdf(records)

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        gdf.to_file(cache_path, driver="GPKG")

    # Filter by year in memory — no API calls needed
    if year is not None:
        gdf = gdf[gdf["year"] == year].copy()

    return gdf


def simplify_water_for_browser(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Simplify a water GeoDataFrame for browser rendering.

    The full GLWD water layer has 895,059 features at 500m resolution —
    far too large to send to a browser. This function reduces the dataset
    to a browser-renderable size by:

    1. Removing ephemeral features — water present < 2 months/year is
       invisible at continent scale and not meaningful for stress scoring
    2. Removing low-reliability features (reliability < 0.5) — these are
       rarely present and add noise at zoom level 3
    3. Simplifying geometries — 0.05 degree tolerance (~5km) is
       imperceptible at zoom 3 but dramatically reduces vertex count
    4. Dropping empty geometries created by simplification

    The full-resolution layer is preserved in WATER_CACHE_PATH for
    analysis pipelines (scoring, QGIS plugin, etc). This simplified
    version is only for browser visualization.

    Args:
        gdf: Full water GeoDataFrame with normalized schema.

    Returns:
        Simplified GeoDataFrame suitable for browser rendering.
        Empty GeoDataFrame if input is empty.
    """
    if gdf.empty:
        return gdf.copy()

    # Step 1 — keep only permanent water for browser rendering
    # At zoom 3 (full Africa), only permanent features are meaningful
    result = gdf[gdf["permanence"] == "permanent"].copy()

    # Step 2 — keep only high reliability
    result = result[result["reliability"] >= 0.7].copy()

    # Step 3 — aggressive geometry simplification
    # 0.1 degrees ≈ 10km tolerance — still looks good at zoom 3
    result["geometry"] = result.geometry.simplify(0.1)

    # Step 4 — drop empty geometries
    result = result[~result.geometry.is_empty].copy()

    # Step 5 — drop tiny polygons (area < 0.001 sq degrees)
    # These are sub-pixel at zoom 3 — invisible but expensive
    result = result[result.geometry.apply(lambda g: g.length > 0.01 or g.area > 0.001)].copy()

    return result


@st.cache_data
def load_water_layer_simplified() -> gpd.GeoDataFrame:
    """
    Load the simplified water layer for browser rendering.

    Checks for a pre-built simplified cache first. If not found,
    loads the full water layer and simplifies it, saving the result
    for future runs.

    The simplified layer filters out ephemeral and low-reliability
    features and simplifies geometries to reduce browser payload
    from ~1.5GB to a manageable size.

    Returns:
        Simplified GeoDataFrame ready for PyDeck rendering.
    """
    if WATER_SIMPLIFIED_CACHE_PATH.exists():
        return gpd.read_file(WATER_SIMPLIFIED_CACHE_PATH)

    with st.spinner("Building simplified water layer for browser rendering..."):
        # Load full water layer first — from cache if available
        full_water = load_water_layer()
        simplified = simplify_water_for_browser(full_water)

    WATER_SIMPLIFIED_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    simplified.to_file(WATER_SIMPLIFIED_CACHE_PATH, driver="GPKG")

    return simplified


def load_gbif_data_safe(
    species: str = "Loxodonta africana",
    year: int | None = None,
    _cache_dir: Path = Path("data/processed"),
) -> gpd.GeoDataFrame:
    """
    Load GBIF occurrence data for any species, returning an empty
    GeoDataFrame if the cache is missing or the fetch fails.

    Used by the species comparison chart — a missing cache file for
    one species should not crash the whole app. The chart simply
    excludes that species silently until its cache is populated.

    Unknown species still raises ValueError — that is a developer
    error (misconfigured SPECIES_CONFIG), not a missing data file.

    Args:
        species    : Scientific name — must be a key in SPECIES_CONFIG.
        year       : Optional year to filter by. None returns all records.
        _cache_dir : Directory for cache files. See load_gbif_data().

    Returns:
        GeoDataFrame of occurrence points, or empty GeoDataFrame on error.
    """
    if species not in SPECIES_CONFIG:
        raise ValueError(f"Unknown species: {species}. Must be one of {list(SPECIES_CONFIG.keys())}")

    try:
        return load_gbif_data(species=species, year=year, _cache_dir=_cache_dir)
    except Exception:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
