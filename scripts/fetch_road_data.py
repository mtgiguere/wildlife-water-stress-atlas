"""
fetch_road_data.py

Downloads OSM road data for African countries from Geofabrik and saves
a merged GeoPackage for use by OSMRoads and export_road_threats.py.

USAGE:
------
    python scripts/fetch_road_data.py

Downloads .gpkg.zip files from Geofabrik — plain HTTPS, no API key,
no rate limits, designed for bulk download. Extracts the lines layer
from each, filters to KNOWN_ROAD_CLASSES, and merges into one GPKG.

Re-run to refresh the road network snapshot.

NOTE ON HISTORICAL ACCURACY:
-----------------------------
This fetches the current OSM road network snapshot. Road infrastructure
in Africa has changed substantially since 2010 (Chinese BRI investment,
rural paving programs, urban expansion). Occurrence records pre-2015 may
be scored against roads that did not exist at the time of the record.
This is a known limitation — see docs/ for discussion.
"""

import io
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

# Only fetch "major" roads — motorway through tertiary, plus their link ramps.
# Tracks and footpaths are ~90%+ of OSM linear volume in Africa yet contribute
# negligible threat under the current nearest-road model (and a zero-weight
# nearest path can even mask a real road). Excluding them keeps the continental
# dataset to <1GB and the export runnable on one machine. track/path remain
# supported in the threat model (KNOWN_ROAD_CLASSES) — they are simply not
# fetched. Revisit if path-level threat (e.g. amphibians) is ever modeled.
MAJOR_HIGHWAY_TAGS = {
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
    "primary",
    "primary_link",
    "secondary",
    "secondary_link",
    "tertiary",
    "tertiary_link",
}

# OSM `place` classes kept for the settlement pressure layer. Mirrors
# MAJOR_HIGHWAY_TAGS: only real settlements (dropping suburb subdivisions,
# localities, farms, islands, admin regions, etc. — see ingest.threats
# OSM_PLACE_MAP for the downstream normalization). national_capital is kept
# and folded into "city" downstream.
SETTLEMENT_PLACE_TAGS = {
    "city",
    "national_capital",
    "town",
    "village",
    "hamlet",
}

GEOFABRIK_BASE = "https://download.geofabrik.de/africa"

DEFAULT_OUTPUT_PATH = Path("data/raw/threats/africa_roads.gpkg")
DEFAULT_SETTLEMENTS_OUTPUT_PATH = Path("data/raw/threats/africa_settlements.gpkg")

# Countries covering the geographic ranges of all 11 species.
# Slugs match Geofabrik's Africa sub-region URL scheme.
# Failed downloads are skipped gracefully — add or remove slugs as needed.
TARGET_COUNTRIES = [
    "kenya",
    "tanzania",
    "uganda",
    "ethiopia",
    "rwanda",
    "burundi",
    "south-africa",
    "botswana",
    "zimbabwe",
    "zambia",
    "mozambique",
    "namibia",
    "malawi",
    "angola",
    "lesotho",
    "swaziland",
    "congo-democratic-republic",
    "cameroon",
    "central-african-republic",
    "nigeria",
    "ghana",
    "ivory-coast",
    "somalia",
    "south-sudan",
    "sudan",
    "chad",
]

# Geofabrik free GPKGs store roads in this layer with an 'fclass' column
# (not 'highway'). NOTE: the layer is 'gis_osm_roads_free' WITHOUT a numeric
# suffix — the '_1' suffix is the shapefile naming convention; the GPKG drops
# it. Verified against the real Africa sub-region downloads.
_ROADS_LAYER = "gis_osm_roads_free"
_PLACES_LAYER = "gis_osm_places_free"
_HIGHWAY_COL = "highway"
_PLACE_COL = "place"
_FCLASS_COL = "fclass"


def get_geofabrik_url(country_slug: str) -> str:
    """Build the Geofabrik download URL for a country's GeoPackage."""
    return f"{GEOFABRIK_BASE}/{country_slug}-latest-free.gpkg.zip"


def download_gpkg_zip(url: str) -> bytes:
    """
    Download a Geofabrik .gpkg.zip file and return its bytes.

    Streams the download with progress reporting. Raises requests.HTTPError
    on non-2xx responses so callers can handle cleanly.

    Args:
        url: Geofabrik GPKG zip URL.

    Returns:
        Raw zip bytes.

    Raises:
        requests.HTTPError: On HTTP 4xx/5xx responses.
        requests.ConnectionError: On network failure.
    """
    response = requests.get(url, timeout=300, stream=True)
    response.raise_for_status()

    chunks = []
    total = int(response.headers.get("content-length", 0))
    downloaded = 0

    for chunk in response.iter_content(chunk_size=1024 * 1024):
        chunks.append(chunk)
        downloaded += len(chunk)
        if total:
            print(f"\r    {100 * downloaded // total}%", end="", flush=True)

    print()
    return b"".join(chunks)


def _read_layer_from_zip(zip_bytes: bytes, layer: str) -> gpd.GeoDataFrame:
    """
    Read one named layer from a Geofabrik GPKG zip.

    Geofabrik GPKGs contain multiple layers (gis_osm_roads_free,
    gis_osm_places_free, etc.). This unzips to a temp file and reads the
    requested layer in its native CRS.

    Args:
        zip_bytes : Raw bytes of the downloaded .gpkg.zip file.
        layer     : GPKG layer name to read.

    Returns:
        GeoDataFrame with all columns from the layer (native CRS), or an empty
        EPSG:4326 GeoDataFrame if the zip is malformed or the layer is empty.
    """
    _empty = gpd.GeoDataFrame(geometry=gpd.GeoSeries([], crs="EPSG:4326"))

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            gpkg_names = [n for n in zf.namelist() if n.endswith(".gpkg")]
            if not gpkg_names:
                return _empty

            with tempfile.NamedTemporaryFile(suffix=".gpkg", delete=False) as f:
                f.write(zf.read(gpkg_names[0]))
                temp_path = Path(f.name)

        try:
            gdf = gpd.read_file(temp_path, layer=layer)
        finally:
            temp_path.unlink(missing_ok=True)

        return _empty if gdf.empty else gdf

    except Exception as e:
        print(f"  Warning: could not extract layer '{layer}' from zip: {e}")
        return _empty


def extract_roads_from_zip(zip_bytes: bytes) -> gpd.GeoDataFrame:
    """
    Extract the roads layer from a Geofabrik GPKG zip.

    Reads the gis_osm_roads_free layer and renames its 'fclass' column to
    'highway' so the rest of the pipeline (OSM_HIGHWAY_MAP, fetch_country_roads)
    is transparent to the free vs full GPKG format difference.

    Args:
        zip_bytes: Raw bytes of the downloaded .gpkg.zip file.

    Returns:
        GeoDataFrame with all road columns in EPSG:4326, or an empty
        GeoDataFrame if extraction fails.
    """
    gdf = _read_layer_from_zip(zip_bytes, _ROADS_LAYER)
    if gdf.empty:
        return gdf

    if _FCLASS_COL in gdf.columns and _HIGHWAY_COL not in gdf.columns:
        gdf = gdf.rename(columns={_FCLASS_COL: _HIGHWAY_COL})

    return gdf.to_crs(epsg=4326)


def extract_settlements_from_zip(zip_bytes: bytes) -> gpd.GeoDataFrame:
    """
    Extract the places (settlements) layer from a Geofabrik GPKG zip.

    Reads the gis_osm_places_free layer and renames its 'fclass' column to
    'place' so downstream ingestion (OSM_PLACE_MAP) sees a consistent schema.

    Args:
        zip_bytes: Raw bytes of the downloaded .gpkg.zip file.

    Returns:
        GeoDataFrame with all place columns in EPSG:4326, or an empty
        GeoDataFrame if extraction fails.
    """
    gdf = _read_layer_from_zip(zip_bytes, _PLACES_LAYER)
    if gdf.empty:
        return gdf

    if _FCLASS_COL in gdf.columns and _PLACE_COL not in gdf.columns:
        gdf = gdf.rename(columns={_FCLASS_COL: _PLACE_COL})

    return gdf.to_crs(epsg=4326)


def _empty_gdf() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(geometry=gpd.GeoSeries([], crs="EPSG:4326"))


def _filter_major_roads(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Keep only major road classes (MAJOR_HIGHWAY_TAGS); return geometry + highway."""
    if gdf.empty or _HIGHWAY_COL not in gdf.columns:
        return _empty_gdf()
    gdf = gdf[gdf[_HIGHWAY_COL].isin(MAJOR_HIGHWAY_TAGS)].copy()
    if gdf.empty:
        return _empty_gdf()
    return gdf[["geometry", _HIGHWAY_COL]].copy().to_crs(epsg=4326)


def _filter_settlements(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Keep only real settlement classes (SETTLEMENT_PLACE_TAGS); return geometry + place."""
    if gdf.empty or _PLACE_COL not in gdf.columns:
        return _empty_gdf()
    gdf = gdf[gdf[_PLACE_COL].isin(SETTLEMENT_PLACE_TAGS)].copy()
    if gdf.empty:
        return _empty_gdf()
    return gdf[["geometry", _PLACE_COL]].copy().to_crs(epsg=4326)


def fetch_country_roads(country_slug: str) -> gpd.GeoDataFrame:
    """
    Download, extract, and filter roads for one country.

    Downloads the Geofabrik GPKG, reads the roads layer, and returns only
    the major road segments whose highway tag is in MAJOR_HIGHWAY_TAGS
    (dropping residential, service, track, path, footway, etc.).

    Args:
        country_slug: Geofabrik Africa sub-region slug (e.g. "kenya").

    Returns:
        GeoDataFrame with geometry and highway columns in EPSG:4326,
        or an empty GeoDataFrame if the download or extraction fails.
    """
    url = get_geofabrik_url(country_slug)
    try:
        zip_bytes = download_gpkg_zip(url)
    except Exception as e:
        print(f"  Warning: could not download {country_slug}: {e}")
        return _empty_gdf()

    return _filter_major_roads(extract_roads_from_zip(zip_bytes))


def fetch_country_osm(country_slug: str) -> dict:
    """
    Download one country's Geofabrik GPKG ONCE and extract both pressure layers.

    Roads and settlements live in the same GPKG, so a single download yields
    both — avoiding a second continental fetch just for settlements.

    Args:
        country_slug: Geofabrik Africa sub-region slug (e.g. "kenya").

    Returns:
        {"roads": <major roads GDF>, "settlements": <settlements GDF>}, each in
        EPSG:4326, each empty if download/extraction fails or nothing matched.
    """
    url = get_geofabrik_url(country_slug)
    try:
        zip_bytes = download_gpkg_zip(url)
    except Exception as e:
        print(f"  Warning: could not download {country_slug}: {e}")
        return {"roads": _empty_gdf(), "settlements": _empty_gdf()}

    return {
        "roads": _filter_major_roads(extract_roads_from_zip(zip_bytes)),
        "settlements": _filter_settlements(extract_settlements_from_zip(zip_bytes)),
    }


def fetch_all_road_data(
    output_path: Path = DEFAULT_OUTPUT_PATH,
    countries: list | None = None,
) -> None:
    """
    Download and merge road data for all target countries.

    Countries that fail to download (wrong slug, network error, HTTP error)
    are skipped with a warning — the run continues regardless so no human
    intervention is needed.

    Args:
        output_path : Path to write the merged GeoPackage.
        countries   : List of Geofabrik country slugs. Defaults to TARGET_COUNTRIES.
    """
    if countries is None:
        countries = TARGET_COUNTRIES

    layers = []

    for slug in countries:
        print(f"  {slug}...", end=" ", flush=True)
        gdf = fetch_country_roads(slug)
        if not gdf.empty:
            layers.append(gdf)
            print(f"-> {len(gdf):,} segments")
        else:
            print("-> empty or failed")

    if not layers:
        print("  No road data retrieved - check country slugs and network.")
        return

    merged = pd.concat(layers, ignore_index=True)
    result = gpd.GeoDataFrame(merged, geometry="geometry", crs="EPSG:4326")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_file(output_path, driver="GPKG")
    print(f"  -> {output_path} ({len(result):,} road segments total)")


def _write_merged(layers: list, output_path: Path, label: str) -> None:
    """Concatenate per-country layers and write one merged GeoPackage."""
    if not layers:
        print(f"  No {label} retrieved - check country slugs and network.")
        return

    merged = pd.concat(layers, ignore_index=True)
    result = gpd.GeoDataFrame(merged, geometry="geometry", crs="EPSG:4326")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_file(output_path, driver="GPKG")
    print(f"  -> {output_path} ({len(result):,} {label} total)")


def fetch_all_osm_data(
    roads_output_path: Path = DEFAULT_OUTPUT_PATH,
    settlements_output_path: Path = DEFAULT_SETTLEMENTS_OUTPUT_PATH,
    countries: list | None = None,
) -> None:
    """
    Download every target country ONCE and write both pressure layers.

    Each country's GPKG is fetched a single time; roads and settlements are
    extracted from the same download and merged into two output GeoPackages.
    Countries that fail to download are skipped with a warning — the run
    continues so no human intervention is needed.

    Args:
        roads_output_path       : Path for the merged roads GeoPackage.
        settlements_output_path : Path for the merged settlements GeoPackage.
        countries               : Geofabrik slugs. Defaults to TARGET_COUNTRIES.
    """
    if countries is None:
        countries = TARGET_COUNTRIES

    road_layers = []
    settlement_layers = []

    for slug in countries:
        print(f"  {slug}...", end=" ", flush=True)
        result = fetch_country_osm(slug)
        roads = result["roads"]
        settlements = result["settlements"]
        if not roads.empty:
            road_layers.append(roads)
        if not settlements.empty:
            settlement_layers.append(settlements)
        print(f"-> {len(roads):,} roads, {len(settlements):,} settlements")

    _write_merged(road_layers, roads_output_path, "road segments")
    _write_merged(settlement_layers, settlements_output_path, "settlements")


def main() -> None:
    fetch_all_osm_data(
        roads_output_path=DEFAULT_OUTPUT_PATH,
        settlements_output_path=DEFAULT_SETTLEMENTS_OUTPUT_PATH,
        countries=TARGET_COUNTRIES,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
