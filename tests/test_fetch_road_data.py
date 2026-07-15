"""
test_fetch_road_data.py

Tests for scripts/fetch_road_data.py

TESTING STRATEGY:
-----------------
Geofabrik downloads are mocked via requests.get — no live HTTP calls.
extract_roads_from_zip is tested with real in-memory zip+GPKG fixtures
because the zip/file logic is the hard part and deserves real coverage.
Higher-level functions mock at the fetch_country_roads boundary.

FUNCTION COVERAGE:
------------------
- get_geofabrik_url(country_slug)         — URL construction
- download_gpkg_zip(url)                  — HTTP download
- extract_roads_from_zip(zip_bytes)       — unzip + read lines layer
- fetch_country_roads(country_slug)       — download + extract + filter
- fetch_all_road_data(output_path, ...)   — loop + merge + save
- main()                                  — entry point
"""

import io
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import geopandas as gpd
import pytest
from shapely.geometry import LineString

from wildlife_water_stress_atlas.ingest.threats import OSM_HIGHWAY_MAP

REQUESTS_GET = "scripts.fetch_road_data.requests.get"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_gpkg_zip(tmp_path: Path, highway_values: list[str]) -> bytes:
    """Build zip bytes containing a GPKG matching Geofabrik free format.

    Geofabrik free GPKGs use layer 'gis_osm_roads_free' with an 'fclass'
    column (not 'highway') — same values, different column name.
    """
    gdf = gpd.GeoDataFrame(
        {
            "fclass": highway_values,
            "name": [f"Road {i}" for i in range(len(highway_values))],
        },
        geometry=[LineString([(i, 0), (i + 1, 0)]) for i in range(len(highway_values))],
        crs="EPSG:4326",
    )
    gpkg_path = tmp_path / "country-latest.gpkg"
    gdf.to_file(gpkg_path, layer="gis_osm_roads_free", driver="GPKG")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.write(gpkg_path, "country-latest.gpkg")
    return buf.getvalue()


def make_gpkg_zip_from_gdf(tmp_path: Path, gdf: gpd.GeoDataFrame) -> bytes:
    """Build zip bytes from an arbitrary GDF written as the roads layer.

    Lets tests construct edge-case layers (empty, or missing the fclass/
    highway column) that make_gpkg_zip cannot.
    """
    gpkg_path = tmp_path / "country-latest.gpkg"
    gdf.to_file(gpkg_path, layer="gis_osm_roads_free", driver="GPKG")

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
    if status_code >= 400:
        import requests

        resp.raise_for_status.side_effect = requests.HTTPError(f"{status_code}")
    return resp


# ---------------------------------------------------------------------------
# get_geofabrik_url
# ---------------------------------------------------------------------------


def test_get_geofabrik_url_contains_slug():
    from scripts.fetch_road_data import get_geofabrik_url

    url = get_geofabrik_url("kenya")

    assert "kenya" in url


def test_get_geofabrik_url_points_to_geofabrik():
    from scripts.fetch_road_data import get_geofabrik_url

    url = get_geofabrik_url("kenya")

    assert "download.geofabrik.de" in url


def test_get_geofabrik_url_ends_with_free_gpkg_zip():
    from scripts.fetch_road_data import get_geofabrik_url

    url = get_geofabrik_url("kenya")

    assert url.endswith("-free.gpkg.zip")


def test_get_geofabrik_url_contains_africa():
    from scripts.fetch_road_data import get_geofabrik_url

    url = get_geofabrik_url("kenya")

    assert "africa" in url


# ---------------------------------------------------------------------------
# download_gpkg_zip
# ---------------------------------------------------------------------------


def test_download_gpkg_zip_calls_requests_get(monkeypatch):
    from scripts.fetch_road_data import download_gpkg_zip

    captured = {}

    def mock_get(url, **kwargs):
        captured["url"] = url
        return mock_response(b"fake zip content")

    monkeypatch.setattr(REQUESTS_GET, mock_get)

    download_gpkg_zip("https://example.com/kenya.gpkg.zip")

    assert captured["url"] == "https://example.com/kenya.gpkg.zip"


def test_download_gpkg_zip_returns_bytes(monkeypatch):
    from scripts.fetch_road_data import download_gpkg_zip

    monkeypatch.setattr(REQUESTS_GET, lambda url, **kw: mock_response(b"zip content"))

    result = download_gpkg_zip("https://example.com/kenya.gpkg.zip")

    assert isinstance(result, bytes)
    assert len(result) > 0


def test_download_gpkg_zip_raises_on_http_error(monkeypatch):
    import requests as req

    from scripts.fetch_road_data import download_gpkg_zip

    monkeypatch.setattr(REQUESTS_GET, lambda url, **kw: mock_response(b"", 404))

    with pytest.raises(req.HTTPError):
        download_gpkg_zip("https://example.com/notfound.gpkg.zip")


# ---------------------------------------------------------------------------
# extract_roads_from_zip
# ---------------------------------------------------------------------------


def test_extract_roads_from_zip_returns_geodataframe(tmp_path):
    from scripts.fetch_road_data import extract_roads_from_zip

    zip_bytes = make_gpkg_zip(tmp_path, ["motorway", "primary"])
    result = extract_roads_from_zip(zip_bytes)

    assert isinstance(result, gpd.GeoDataFrame)


def test_extract_roads_from_zip_reads_gis_osm_roads_layer(tmp_path):
    """Geofabrik free GPKGs use layer gis_osm_roads_free, not lines."""
    from scripts.fetch_road_data import extract_roads_from_zip

    zip_bytes = make_gpkg_zip(tmp_path, ["motorway", "primary"])
    result = extract_roads_from_zip(zip_bytes)

    assert len(result) == 2


def test_extract_roads_from_zip_renames_fclass_to_highway(tmp_path):
    """Geofabrik uses fclass instead of highway — must be renamed for the pipeline."""
    from scripts.fetch_road_data import extract_roads_from_zip

    zip_bytes = make_gpkg_zip(tmp_path, ["motorway"])
    result = extract_roads_from_zip(zip_bytes)

    assert "highway" in result.columns
    assert "fclass" not in result.columns


def test_extract_roads_from_zip_has_highway_column(tmp_path):
    from scripts.fetch_road_data import extract_roads_from_zip

    zip_bytes = make_gpkg_zip(tmp_path, ["motorway"])
    result = extract_roads_from_zip(zip_bytes)

    assert "highway" in result.columns


def test_extract_roads_from_zip_output_is_wgs84(tmp_path):
    from scripts.fetch_road_data import extract_roads_from_zip

    zip_bytes = make_gpkg_zip(tmp_path, ["primary"])
    result = extract_roads_from_zip(zip_bytes)

    assert result.crs.to_string() == "EPSG:4326"


def test_extract_roads_from_zip_returns_empty_when_layer_has_no_rows(tmp_path):
    """A roads layer that exists but contains zero features yields an empty GDF."""
    from scripts.fetch_road_data import extract_roads_from_zip

    empty_layer = gpd.GeoDataFrame({"fclass": []}, geometry=gpd.GeoSeries([], crs="EPSG:4326"))
    zip_bytes = make_gpkg_zip_from_gdf(tmp_path, empty_layer)

    result = extract_roads_from_zip(zip_bytes)

    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 0


def test_extract_roads_from_zip_returns_empty_on_corrupt_zip():
    from scripts.fetch_road_data import extract_roads_from_zip

    result = extract_roads_from_zip(b"this is not a zip file")

    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 0


def test_extract_roads_from_zip_returns_empty_when_no_gpkg_in_zip():
    from scripts.fetch_road_data import extract_roads_from_zip

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("README.txt", "no gpkg here")

    result = extract_roads_from_zip(buf.getvalue())

    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 0


# ---------------------------------------------------------------------------
# fetch_country_roads
# ---------------------------------------------------------------------------


def test_fetch_country_roads_returns_geodataframe(tmp_path, monkeypatch):
    from scripts.fetch_road_data import fetch_country_roads

    zip_bytes = make_gpkg_zip(tmp_path, ["motorway", "residential"])
    monkeypatch.setattr(REQUESTS_GET, lambda url, **kw: mock_response(zip_bytes))

    result = fetch_country_roads("kenya")

    assert isinstance(result, gpd.GeoDataFrame)


def test_fetch_country_roads_filters_unknown_highway_types(tmp_path, monkeypatch):
    """residential, service, etc. are not in OSM_HIGHWAY_MAP — drop them."""
    from scripts.fetch_road_data import fetch_country_roads

    zip_bytes = make_gpkg_zip(tmp_path, ["motorway", "residential", "primary"])
    monkeypatch.setattr(REQUESTS_GET, lambda url, **kw: mock_response(zip_bytes))

    result = fetch_country_roads("kenya")

    assert len(result) == 2
    assert set(result["highway"]).issubset(OSM_HIGHWAY_MAP.keys())


def test_fetch_country_roads_returns_empty_when_no_highway_column(tmp_path, monkeypatch):
    """If the extracted layer lacks a highway/fclass column, return empty —
    there is nothing to classify."""
    from scripts.fetch_road_data import fetch_country_roads

    no_highway = gpd.GeoDataFrame(
        {"other": ["x"]},
        geometry=[LineString([(0, 0), (1, 0)])],
        crs="EPSG:4326",
    )
    zip_bytes = make_gpkg_zip_from_gdf(tmp_path, no_highway)
    monkeypatch.setattr(REQUESTS_GET, lambda url, **kw: mock_response(zip_bytes))

    result = fetch_country_roads("kenya")

    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 0


def test_fetch_country_roads_returns_empty_when_all_classes_unknown(tmp_path, monkeypatch):
    """A country whose roads are all residential/service (not in OSM_HIGHWAY_MAP)
    yields an empty result after filtering."""
    from scripts.fetch_road_data import fetch_country_roads

    zip_bytes = make_gpkg_zip(tmp_path, ["residential", "service", "living_street"])
    monkeypatch.setattr(REQUESTS_GET, lambda url, **kw: mock_response(zip_bytes))

    result = fetch_country_roads("kenya")

    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 0


def test_fetch_country_roads_keeps_only_major_roads(tmp_path, monkeypatch):
    """Only motorway..tertiary are fetched. Tracks and footpaths — the bulk of
    OSM volume and negligible threat under the current model — are excluded."""
    from scripts.fetch_road_data import fetch_country_roads

    zip_bytes = make_gpkg_zip(tmp_path, ["motorway", "primary", "tertiary", "track", "path", "footway"])
    monkeypatch.setattr(REQUESTS_GET, lambda url, **kw: mock_response(zip_bytes))

    result = fetch_country_roads("kenya")

    assert set(result["highway"]) == {"motorway", "primary", "tertiary"}


def test_fetch_country_roads_keeps_major_link_variants(tmp_path, monkeypatch):
    """Link ramps of major roads (primary_link, etc.) are kept — they are the
    same threat as their parent road."""
    from scripts.fetch_road_data import fetch_country_roads

    zip_bytes = make_gpkg_zip(tmp_path, ["primary_link", "trunk_link", "path"])
    monkeypatch.setattr(REQUESTS_GET, lambda url, **kw: mock_response(zip_bytes))

    result = fetch_country_roads("kenya")

    assert set(result["highway"]) == {"primary_link", "trunk_link"}


def test_fetch_country_roads_returns_empty_on_download_failure(monkeypatch):
    """Network failure must not crash the pipeline — return empty GDF."""
    from scripts.fetch_road_data import fetch_country_roads

    def failing_get(url, **kw):
        raise ConnectionError("network unreachable")

    monkeypatch.setattr(REQUESTS_GET, failing_get)

    result = fetch_country_roads("kenya")

    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 0


def test_fetch_country_roads_returns_empty_on_404(monkeypatch):
    """HTTP 404 (wrong slug) must not crash — return empty GDF."""
    from scripts.fetch_road_data import fetch_country_roads

    monkeypatch.setattr(REQUESTS_GET, lambda url, **kw: mock_response(b"", 404))

    result = fetch_country_roads("nonexistent-country")

    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 0


def test_fetch_country_roads_output_is_wgs84(tmp_path, monkeypatch):
    from scripts.fetch_road_data import fetch_country_roads

    zip_bytes = make_gpkg_zip(tmp_path, ["primary"])
    monkeypatch.setattr(REQUESTS_GET, lambda url, **kw: mock_response(zip_bytes))

    result = fetch_country_roads("kenya")

    assert result.crs.to_string() == "EPSG:4326"


# ---------------------------------------------------------------------------
# fetch_all_road_data
# ---------------------------------------------------------------------------


def test_fetch_all_road_data_fetches_each_country(tmp_path):
    from scripts.fetch_road_data import fetch_all_road_data

    call_count = {"n": 0}

    def mock_fetch(slug):
        call_count["n"] += 1
        return gpd.GeoDataFrame(
            {"highway": ["primary"]},
            geometry=[LineString([(0, 0), (1, 0)])],
            crs="EPSG:4326",
        )

    with patch("scripts.fetch_road_data.fetch_country_roads", side_effect=mock_fetch):
        fetch_all_road_data(
            output_path=tmp_path / "roads.gpkg",
            countries=["kenya", "tanzania", "south-africa"],
        )

    assert call_count["n"] == 3


def test_fetch_all_road_data_writes_output_file(tmp_path):
    from scripts.fetch_road_data import fetch_all_road_data

    mock_gdf = gpd.GeoDataFrame(
        {"highway": ["motorway"]},
        geometry=[LineString([(0, 0), (1, 0)])],
        crs="EPSG:4326",
    )
    output_path = tmp_path / "roads.gpkg"

    with patch("scripts.fetch_road_data.fetch_country_roads", return_value=mock_gdf):
        fetch_all_road_data(output_path=output_path, countries=["kenya"])

    assert output_path.exists()


def test_fetch_all_road_data_creates_output_directory(tmp_path):
    from scripts.fetch_road_data import fetch_all_road_data

    mock_gdf = gpd.GeoDataFrame(
        {"highway": ["primary"]},
        geometry=[LineString([(0, 0), (1, 0)])],
        crs="EPSG:4326",
    )
    output_path = tmp_path / "deep" / "nested" / "roads.gpkg"

    with patch("scripts.fetch_road_data.fetch_country_roads", return_value=mock_gdf):
        fetch_all_road_data(output_path=output_path, countries=["kenya"])

    assert output_path.exists()


def test_fetch_all_road_data_merges_all_countries(tmp_path):
    from scripts.fetch_road_data import fetch_all_road_data

    def make_gdf(slug):
        return gpd.GeoDataFrame(
            {"highway": ["primary", "motorway"]},
            geometry=[LineString([(0, 0), (1, 0)]), LineString([(1, 0), (2, 0)])],
            crs="EPSG:4326",
        )

    output_path = tmp_path / "roads.gpkg"
    with patch("scripts.fetch_road_data.fetch_country_roads", side_effect=make_gdf):
        fetch_all_road_data(output_path=output_path, countries=["kenya", "tanzania"])

    result = gpd.read_file(output_path)
    assert len(result) == 4  # 2 roads × 2 countries


def test_fetch_all_road_data_skips_failed_countries(tmp_path):
    """A country that fails to download must not abort the run."""
    from scripts.fetch_road_data import fetch_all_road_data

    good_gdf = gpd.GeoDataFrame(
        {"highway": ["primary"]},
        geometry=[LineString([(0, 0), (1, 0)])],
        crs="EPSG:4326",
    )
    empty_gdf = gpd.GeoDataFrame(geometry=gpd.GeoSeries([], crs="EPSG:4326"))

    def flaky(slug):
        return empty_gdf if slug == "bad-country" else good_gdf

    output_path = tmp_path / "roads.gpkg"
    with patch("scripts.fetch_road_data.fetch_country_roads", side_effect=flaky):
        fetch_all_road_data(
            output_path=output_path,
            countries=["kenya", "bad-country", "tanzania"],
        )

    result = gpd.read_file(output_path)
    assert len(result) == 2  # only kenya + tanzania


def test_fetch_all_road_data_defaults_to_target_countries(tmp_path):
    """When countries is omitted, the full TARGET_COUNTRIES list is fetched."""
    from scripts.fetch_road_data import TARGET_COUNTRIES, fetch_all_road_data

    fetched = []

    def mock_fetch(slug):
        fetched.append(slug)
        return gpd.GeoDataFrame(geometry=gpd.GeoSeries([], crs="EPSG:4326"))

    with patch("scripts.fetch_road_data.fetch_country_roads", side_effect=mock_fetch):
        fetch_all_road_data(output_path=tmp_path / "roads.gpkg")

    assert fetched == TARGET_COUNTRIES


def test_fetch_all_road_data_does_nothing_when_all_countries_fail(tmp_path):
    from scripts.fetch_road_data import fetch_all_road_data

    empty = gpd.GeoDataFrame(geometry=gpd.GeoSeries([], crs="EPSG:4326"))
    output_path = tmp_path / "roads.gpkg"

    with patch("scripts.fetch_road_data.fetch_country_roads", return_value=empty):
        fetch_all_road_data(output_path=output_path, countries=["bad-1", "bad-2"])

    assert not output_path.exists()


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


# NOTE: main() now drives the combined single-download fetch (fetch_all_osm_data,
# writing both roads and settlements). Its contract is tested in
# test_fetch_osm_data.py. fetch_all_road_data remains as a roads-only building
# block and is covered by the tests above.
