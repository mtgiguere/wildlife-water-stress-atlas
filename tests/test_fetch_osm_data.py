"""
test_fetch_osm_data.py

Tests for the combined OSM pressure fetch in scripts/fetch_road_data.py:
one download per country, extracting BOTH the roads layer and the places
(settlements) layer from the same Geofabrik GPKG.

TESTING STRATEGY:
-----------------
Downloads are mocked via requests.get — no live HTTP. Fixtures build real
in-memory zip+GPKG files containing both the roads and places layers, so the
one-download-extracts-both behaviour is exercised for real.
"""

import io
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import geopandas as gpd
from shapely.geometry import LineString, Point

REQUESTS_GET = "scripts.fetch_road_data.requests.get"


def make_two_layer_zip(tmp_path: Path, highway_values: list[str], place_values: list[str]) -> bytes:
    """Build zip bytes containing a GPKG with both the roads and places layers,
    matching the Geofabrik free format (layer names + 'fclass' column)."""
    roads = gpd.GeoDataFrame(
        {"fclass": highway_values, "name": [f"Road {i}" for i in range(len(highway_values))]},
        geometry=[LineString([(i, 0), (i + 1, 0)]) for i in range(len(highway_values))],
        crs="EPSG:4326",
    )
    places = gpd.GeoDataFrame(
        {"fclass": place_values, "name": [f"Place {i}" for i in range(len(place_values))]},
        geometry=[Point(i, 0) for i in range(len(place_values))],
        crs="EPSG:4326",
    )
    gpkg_path = tmp_path / "country-latest.gpkg"
    roads.to_file(gpkg_path, layer="gis_osm_roads_free", driver="GPKG")
    places.to_file(gpkg_path, layer="gis_osm_places_free", driver="GPKG")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.write(gpkg_path, "country-latest.gpkg")
    return buf.getvalue()


def mock_response(content: bytes, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    resp.headers = {"content-length": str(len(content))}
    resp.iter_content = lambda chunk_size: iter([content])
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# extract_settlements_from_zip
# ---------------------------------------------------------------------------


def test_extract_settlements_reads_places_layer(tmp_path):
    from scripts.fetch_road_data import extract_settlements_from_zip

    zip_bytes = make_two_layer_zip(tmp_path, ["motorway"], ["city", "town"])
    result = extract_settlements_from_zip(zip_bytes)

    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 2


def test_extract_settlements_renames_fclass_to_place(tmp_path):
    from scripts.fetch_road_data import extract_settlements_from_zip

    zip_bytes = make_two_layer_zip(tmp_path, ["motorway"], ["city"])
    result = extract_settlements_from_zip(zip_bytes)

    assert "place" in result.columns
    assert "fclass" not in result.columns


def test_extract_settlements_output_is_wgs84(tmp_path):
    from scripts.fetch_road_data import extract_settlements_from_zip

    zip_bytes = make_two_layer_zip(tmp_path, ["motorway"], ["city"])
    result = extract_settlements_from_zip(zip_bytes)

    assert result.crs.to_string() == "EPSG:4326"


def test_extract_settlements_empty_on_corrupt_zip():
    from scripts.fetch_road_data import extract_settlements_from_zip

    result = extract_settlements_from_zip(b"not a zip")
    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 0


# ---------------------------------------------------------------------------
# fetch_country_osm — ONE download, BOTH layers
# ---------------------------------------------------------------------------


def test_fetch_country_osm_downloads_only_once(tmp_path, monkeypatch):
    """The whole point of the combined fetch: a single download yields both layers."""
    from scripts.fetch_road_data import fetch_country_osm

    zip_bytes = make_two_layer_zip(tmp_path, ["motorway", "primary"], ["city", "village"])
    calls = {"n": 0}

    def counting_get(url, **kw):
        calls["n"] += 1
        return mock_response(zip_bytes)

    monkeypatch.setattr(REQUESTS_GET, counting_get)

    result = fetch_country_osm("kenya")

    assert calls["n"] == 1, f"expected exactly one download, got {calls['n']}"
    assert set(result.keys()) == {"roads", "settlements"}


def test_fetch_country_osm_returns_both_nonempty(tmp_path, monkeypatch):
    from scripts.fetch_road_data import fetch_country_osm

    zip_bytes = make_two_layer_zip(tmp_path, ["motorway", "primary"], ["city", "village"])
    monkeypatch.setattr(REQUESTS_GET, lambda url, **kw: mock_response(zip_bytes))

    result = fetch_country_osm("kenya")

    assert not result["roads"].empty
    assert not result["settlements"].empty


def test_fetch_country_osm_filters_major_roads(tmp_path, monkeypatch):
    from scripts.fetch_road_data import MAJOR_HIGHWAY_TAGS, fetch_country_osm

    zip_bytes = make_two_layer_zip(tmp_path, ["motorway", "residential", "primary"], ["city"])
    monkeypatch.setattr(REQUESTS_GET, lambda url, **kw: mock_response(zip_bytes))

    result = fetch_country_osm("kenya")

    assert set(result["roads"]["highway"]).issubset(MAJOR_HIGHWAY_TAGS)
    assert len(result["roads"]) == 2


def test_fetch_country_osm_filters_settlement_place_tags(tmp_path, monkeypatch):
    """Only real settlement classes are kept; suburb/locality/farm are dropped."""
    from scripts.fetch_road_data import SETTLEMENT_PLACE_TAGS, fetch_country_osm

    zip_bytes = make_two_layer_zip(tmp_path, ["motorway"], ["city", "suburb", "locality", "town", "farm"])
    monkeypatch.setattr(REQUESTS_GET, lambda url, **kw: mock_response(zip_bytes))

    result = fetch_country_osm("kenya")

    assert set(result["settlements"]["place"]).issubset(SETTLEMENT_PLACE_TAGS)
    assert len(result["settlements"]) == 2  # city + town


# ---------------------------------------------------------------------------
# fetch_all_osm_data — writes BOTH output files from ONE pass
# ---------------------------------------------------------------------------


def test_fetch_all_osm_data_writes_both_files(tmp_path):
    from scripts.fetch_road_data import fetch_all_osm_data

    roads = gpd.GeoDataFrame({"highway": ["motorway"]}, geometry=[LineString([(0, 0), (1, 0)])], crs="EPSG:4326")
    settlements = gpd.GeoDataFrame({"place": ["city"]}, geometry=[Point(0, 0)], crs="EPSG:4326")
    roads_out = tmp_path / "africa_roads.gpkg"
    settlements_out = tmp_path / "africa_settlements.gpkg"

    with patch("scripts.fetch_road_data.fetch_country_osm", return_value={"roads": roads, "settlements": settlements}):
        fetch_all_osm_data(roads_output_path=roads_out, settlements_output_path=settlements_out, countries=["kenya"])

    assert roads_out.exists()
    assert settlements_out.exists()


def test_fetch_all_osm_data_downloads_each_country_once(tmp_path):
    from scripts.fetch_road_data import fetch_all_osm_data

    roads = gpd.GeoDataFrame({"highway": ["motorway"]}, geometry=[LineString([(0, 0), (1, 0)])], crs="EPSG:4326")
    settlements = gpd.GeoDataFrame({"place": ["city"]}, geometry=[Point(0, 0)], crs="EPSG:4326")
    seen = []

    def mock_fetch(slug):
        seen.append(slug)
        return {"roads": roads, "settlements": settlements}

    with patch("scripts.fetch_road_data.fetch_country_osm", side_effect=mock_fetch):
        fetch_all_osm_data(
            roads_output_path=tmp_path / "r.gpkg",
            settlements_output_path=tmp_path / "s.gpkg",
            countries=["kenya", "tanzania", "uganda"],
        )

    assert seen == ["kenya", "tanzania", "uganda"]


def test_fetch_all_osm_data_skips_failed_countries(tmp_path):
    from scripts.fetch_road_data import fetch_all_osm_data

    roads = gpd.GeoDataFrame({"highway": ["primary"]}, geometry=[LineString([(0, 0), (1, 0)])], crs="EPSG:4326")
    settlements = gpd.GeoDataFrame({"place": ["town"]}, geometry=[Point(0, 0)], crs="EPSG:4326")
    empty_roads = gpd.GeoDataFrame(geometry=gpd.GeoSeries([], crs="EPSG:4326"))
    empty_settlements = gpd.GeoDataFrame(geometry=gpd.GeoSeries([], crs="EPSG:4326"))

    def flaky(slug):
        if slug == "bad-country":
            return {"roads": empty_roads, "settlements": empty_settlements}
        return {"roads": roads, "settlements": settlements}

    roads_out = tmp_path / "r.gpkg"
    settlements_out = tmp_path / "s.gpkg"
    with patch("scripts.fetch_road_data.fetch_country_osm", side_effect=flaky):
        fetch_all_osm_data(
            roads_output_path=roads_out,
            settlements_output_path=settlements_out,
            countries=["kenya", "bad-country", "tanzania"],
        )

    assert len(gpd.read_file(roads_out)) == 2
    assert len(gpd.read_file(settlements_out)) == 2


# ---------------------------------------------------------------------------
# main — wired to the combined fetch
# ---------------------------------------------------------------------------


def test_main_calls_combined_fetch_with_default_paths():
    from scripts.fetch_road_data import (
        DEFAULT_OUTPUT_PATH,
        DEFAULT_SETTLEMENTS_OUTPUT_PATH,
        main,
    )

    with patch("scripts.fetch_road_data.fetch_all_osm_data") as mock_fetch:
        main()
        mock_fetch.assert_called_once()
        assert mock_fetch.call_args.kwargs["roads_output_path"] == DEFAULT_OUTPUT_PATH
        assert mock_fetch.call_args.kwargs["settlements_output_path"] == DEFAULT_SETTLEMENTS_OUTPUT_PATH


def test_main_uses_target_countries_by_default():
    from scripts.fetch_road_data import TARGET_COUNTRIES, main

    with patch("scripts.fetch_road_data.fetch_all_osm_data") as mock_fetch:
        main()
        assert mock_fetch.call_args.kwargs["countries"] == TARGET_COUNTRIES
