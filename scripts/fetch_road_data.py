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

GEOFABRIK_BASE = "https://download.geofabrik.de/africa"

DEFAULT_OUTPUT_PATH = Path("data/raw/threats/africa_roads.gpkg")

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
_HIGHWAY_COL = "highway"
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


def extract_roads_from_zip(zip_bytes: bytes) -> gpd.GeoDataFrame:
    """
    Extract the lines layer from a Geofabrik GPKG zip.

    Geofabrik GPKGs contain multiple layers (points, lines, multipolygons,
    etc.). The lines layer holds roads, rivers, and other linear features
    with an OSM highway tag where applicable.

    Args:
        zip_bytes: Raw bytes of the downloaded .gpkg.zip file.

    Returns:
        GeoDataFrame with all columns from the lines layer in EPSG:4326,
        or an empty GeoDataFrame if extraction fails.
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
            gdf = gpd.read_file(temp_path, layer=_ROADS_LAYER)
        finally:
            temp_path.unlink(missing_ok=True)

        if gdf.empty:
            return _empty

        # Geofabrik free GPKG uses 'fclass' — rename to 'highway' so the
        # rest of the pipeline (OSM_HIGHWAY_MAP, fetch_country_roads) is transparent
        # to the difference between free and full GPKG formats.
        if _FCLASS_COL in gdf.columns and _HIGHWAY_COL not in gdf.columns:
            gdf = gdf.rename(columns={_FCLASS_COL: _HIGHWAY_COL})

        return gdf.to_crs(epsg=4326)

    except Exception as e:
        print(f"  Warning: could not extract roads from zip: {e}")
        return _empty


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
    _empty = gpd.GeoDataFrame(geometry=gpd.GeoSeries([], crs="EPSG:4326"))

    url = get_geofabrik_url(country_slug)
    try:
        zip_bytes = download_gpkg_zip(url)
    except Exception as e:
        print(f"  Warning: could not download {country_slug}: {e}")
        return _empty

    gdf = extract_roads_from_zip(zip_bytes)

    if gdf.empty or "highway" not in gdf.columns:
        return _empty

    gdf = gdf[gdf["highway"].isin(MAJOR_HIGHWAY_TAGS)].copy()

    if gdf.empty:
        return _empty

    return gdf[["geometry", "highway"]].copy().to_crs(epsg=4326)


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


def main() -> None:
    fetch_all_road_data(
        output_path=DEFAULT_OUTPUT_PATH,
        countries=TARGET_COUNTRIES,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
