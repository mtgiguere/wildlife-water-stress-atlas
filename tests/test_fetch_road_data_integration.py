"""
test_fetch_road_data_integration.py

INTEGRATION test for scripts/fetch_road_data.py — hits the REAL Geofabrik
network endpoint. Marked @pytest.mark.integration, skipped in CI.

WHY THIS EXISTS (see docs/TDD_CONTRACT.md, road-threat addendum, Blind spot A):
------------------------------------------------------------------------------
The unit suite in test_fetch_road_data.py builds its own zip+GPKG fixtures and
names the layer 'gis_osm_roads_free' itself, then reads it back. That proves the
parser is self-consistent — nothing more. It CANNOT catch a wrong assumption
about Geofabrik's *external* format, which is exactly how the historical
'gis_osm_roads_free_1' bug shipped: every real download silently produced zero
roads while every unit test stayed green.

These tests pull one small real country (São Tomé and Príncipe — the smallest
Africa sub-region GPKG that still contains major roads) and assert against what
Geofabrik ACTUALLY ships. They read the real layer names off the downloaded
file rather than re-confirming our own constant, so a drift between our
_ROADS_LAYER assumption and reality fails loudly instead of returning empty.

Run with:
    pytest tests/test_fetch_road_data_integration.py -m integration --no-cov
"""

import io
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd
import pytest

from scripts.fetch_road_data import (
    _ROADS_LAYER,
    MAJOR_HIGHWAY_TAGS,
    download_gpkg_zip,
    extract_roads_from_zip,
    fetch_country_roads,
    get_geofabrik_url,
)

# Smallest Geofabrik Africa sub-region that reliably contains major roads
# (primary/secondary/tertiary + link ramps). ~3.8 MB download.
SLUG = "sao-tome-and-principe"


@pytest.fixture(scope="module")
def real_gpkg_zip() -> bytes:
    """Download the real São Tomé GPKG zip once for the whole module."""
    return download_gpkg_zip(get_geofabrik_url(SLUG))


@pytest.mark.integration
def test_real_geofabrik_gpkg_contains_the_layer_we_read(real_gpkg_zip):
    """The layer name our code reads (_ROADS_LAYER) must actually exist in the
    file Geofabrik ships. This is the direct guard against the historical
    'gis_osm_roads_free_1' assumption — it reads the real layer list off the
    download rather than trusting our own constant."""
    with zipfile.ZipFile(io.BytesIO(real_gpkg_zip)) as zf:
        gpkg_name = next(n for n in zf.namelist() if n.endswith(".gpkg"))
        with tempfile.NamedTemporaryFile(suffix=".gpkg", delete=False) as f:
            f.write(zf.read(gpkg_name))
            temp_path = Path(f.name)

    try:
        real_layers = list(gpd.list_layers(temp_path)["name"])
    finally:
        temp_path.unlink(missing_ok=True)

    assert _ROADS_LAYER in real_layers, f"Our code reads layer {_ROADS_LAYER!r}, but the real Geofabrik GPKG ships layers {real_layers}. The external format has drifted."


@pytest.mark.integration
def test_extract_roads_from_real_download_is_nonempty_wgs84(real_gpkg_zip):
    """extract_roads_from_zip on a REAL download returns roads (not empty),
    renames Geofabrik's 'fclass' to 'highway', and reprojects to WGS84.

    If _ROADS_LAYER were wrong, gpd.read_file would raise inside extract and it
    would return an empty GDF — so a non-empty result also proves the layer
    name is correct against reality."""
    result = extract_roads_from_zip(real_gpkg_zip)

    assert not result.empty, "Real download produced zero roads — layer name or format drift"
    assert "highway" in result.columns
    assert "fclass" not in result.columns
    assert result.crs.to_string() == "EPSG:4326"


@pytest.mark.integration
def test_fetch_country_roads_end_to_end_returns_major_roads():
    """Full pipeline against the real endpoint: download → extract → filter.
    The result must be non-empty and contain only major highway classes."""
    result = fetch_country_roads(SLUG)

    assert not result.empty, "Real fetch returned zero major roads"
    assert set(result.columns) >= {"geometry", "highway"}
    assert result.crs.to_string() == "EPSG:4326"
    assert set(result["highway"]).issubset(MAJOR_HIGHWAY_TAGS), f"Non-major classes leaked through: {set(result['highway']) - MAJOR_HIGHWAY_TAGS}"
