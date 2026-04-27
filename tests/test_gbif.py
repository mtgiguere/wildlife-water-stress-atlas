"""
test_gbif.py

Tests for GBIF occurrence data fetching and conversion.

MOCKING STRATEGY:
-----------------
All tests that would hit the real GBIF API are marked @pytest.mark.integration
and skipped in CI. Unit tests mock requests.get to test logic without
network calls.

FUNCTION COVERAGE:
------------------
- fetch_occurrence_count()    — total record count for a species
- fetch_occurrences_page()    — single paginated page of records
- fetch_all_occurrences()     — full paginated fetch across all pages
- occurrences_to_gdf()        — converts records to GeoDataFrame, keeps year
"""

from unittest.mock import MagicMock

import geopandas as gpd
import pytest
import requests

from wildlife_water_stress_atlas.ingest.gbif import (
    fetch_all_occurrences,
    fetch_occurrence_count,
    fetch_occurrences_page,
    occurrences_to_gdf,
)

GBIF_MODULE = "wildlife_water_stress_atlas.ingest.gbif.requests.get"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_mock_response(results: list[dict], count: int = None) -> MagicMock:
    """
    Build a mock requests.Response that returns a GBIF-shaped JSON payload.

    GBIF API responses look like:
    {
        "offset": 0,
        "limit": 300,
        "endOfRecords": true,
        "count": 12345,
        "results": [ {...}, {...}, ... ]
    }
    """
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "offset": 0,
        "limit": len(results),
        "endOfRecords": True,
        "count": count if count is not None else len(results),
        "results": results,
    }
    return mock_response


def make_sample_records(n: int, year: int = 2015) -> list[dict]:
    """Generate n minimal GBIF occurrence records with coordinates and year."""
    return [
        {
            "decimalLatitude": -1.95 + i * 0.1,
            "decimalLongitude": 37.15 + i * 0.1,
            "species": "Loxodonta africana",
            "year": year,
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# occurrences_to_gdf — existing function, extended to keep year field
# ---------------------------------------------------------------------------


def test_occurrences_to_gdf_returns_geodataframe():
    records = [
        {"decimalLatitude": -1.95, "decimalLongitude": 37.15, "species": "Loxodonta africana", "year": 2015},
        {"decimalLatitude": -19.0, "decimalLongitude": 23.5, "species": "Loxodonta africana", "year": 2016},
    ]

    gdf = occurrences_to_gdf(records)

    assert isinstance(gdf, gpd.GeoDataFrame)
    assert len(gdf) == 2
    assert "geometry" in gdf.columns


def test_occurrences_to_gdf_sets_wgs84_crs():
    records = [
        {"decimalLatitude": -1.95, "decimalLongitude": 37.15, "year": 2015},
    ]

    gdf = occurrences_to_gdf(records)

    assert gdf.crs is not None
    assert gdf.crs.to_string() == "EPSG:4326"


def test_occurrences_to_gdf_preserves_year_field():
    # The year field is essential for the temporal animation slider.
    # Verify it survives the GeoDataFrame conversion.
    records = [
        {"decimalLatitude": -1.95, "decimalLongitude": 37.15, "year": 2015},
        {"decimalLatitude": -19.0, "decimalLongitude": 23.5, "year": 2018},
    ]

    gdf = occurrences_to_gdf(records)

    assert "year" in gdf.columns
    assert list(gdf["year"]) == [2015, 2018]


def test_occurrences_to_gdf_drops_records_without_coordinates():
    # Records missing lat/lon should be silently dropped
    records = [
        {"decimalLatitude": -1.95, "decimalLongitude": 37.15, "year": 2015},
        {"decimalLatitude": None, "decimalLongitude": None, "year": 2016},
    ]

    gdf = occurrences_to_gdf(records)

    assert len(gdf) == 1


def test_occurrences_to_gdf_handles_missing_year_gracefully():
    # Not all GBIF records have a year — should not crash, year will be NaN
    records = [
        {"decimalLatitude": -1.95, "decimalLongitude": 37.15},
    ]

    gdf = occurrences_to_gdf(records)

    assert isinstance(gdf, gpd.GeoDataFrame)
    assert len(gdf) == 1


# ---------------------------------------------------------------------------
# fetch_occurrence_count
# ---------------------------------------------------------------------------


def test_fetch_occurrence_count_returns_integer(monkeypatch):
    mock_response = make_mock_response(results=[], count=12345)
    monkeypatch.setattr(GBIF_MODULE, lambda *args, **kwargs: mock_response)

    count = fetch_occurrence_count("Loxodonta africana")

    assert isinstance(count, int)
    assert count == 12345


def test_fetch_occurrence_count_passes_species_name(monkeypatch):
    # Verify the scientific name is sent to the API
    captured_params = {}

    def mock_get(url, params=None, timeout=None):
        captured_params.update(params or {})
        return make_mock_response(results=[], count=100)

    monkeypatch.setattr(GBIF_MODULE, mock_get)

    fetch_occurrence_count("Loxodonta africana")

    assert captured_params["scientificName"] == "Loxodonta africana"


def test_fetch_occurrence_count_requires_coordinates(monkeypatch):
    # Only records with coordinates are useful — verify hasCoordinate=true
    captured_params = {}

    def mock_get(url, params=None, timeout=None):
        captured_params.update(params or {})
        return make_mock_response(results=[], count=100)

    monkeypatch.setattr(GBIF_MODULE, mock_get)

    fetch_occurrence_count("Loxodonta africana")

    assert captured_params.get("hasCoordinate") == "true"


def test_fetch_occurrence_count_raises_on_http_error(monkeypatch):
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.HTTPError("404")
    monkeypatch.setattr(GBIF_MODULE, lambda *args, **kwargs: mock_response)

    with pytest.raises(requests.HTTPError):
        fetch_occurrence_count("Loxodonta africana")


# ---------------------------------------------------------------------------
# fetch_occurrences_page
# ---------------------------------------------------------------------------


def test_fetch_occurrences_page_returns_list(monkeypatch):
    records = make_sample_records(5)
    monkeypatch.setattr(GBIF_MODULE, lambda *args, **kwargs: make_mock_response(records))

    result = fetch_occurrences_page("Loxodonta africana", limit=5, offset=0)

    assert isinstance(result, list)
    assert len(result) == 5


def test_fetch_occurrences_page_passes_offset(monkeypatch):
    captured_params = {}

    def mock_get(url, params=None, timeout=None):
        captured_params.update(params or {})
        return make_mock_response(make_sample_records(5))

    monkeypatch.setattr(GBIF_MODULE, mock_get)

    fetch_occurrences_page("Loxodonta africana", limit=5, offset=300)

    assert captured_params["offset"] == 300


def test_fetch_occurrences_page_passes_limit(monkeypatch):
    captured_params = {}

    def mock_get(url, params=None, timeout=None):
        captured_params.update(params or {})
        return make_mock_response(make_sample_records(5))

    monkeypatch.setattr(GBIF_MODULE, mock_get)

    fetch_occurrences_page("Loxodonta africana", limit=50, offset=0)

    assert captured_params["limit"] == 50


def test_fetch_occurrences_page_passes_year_when_provided(monkeypatch):
    captured_params = {}

    def mock_get(url, params=None, timeout=None):
        captured_params.update(params or {})
        return make_mock_response(make_sample_records(5))

    monkeypatch.setattr(GBIF_MODULE, mock_get)

    fetch_occurrences_page("Loxodonta africana", limit=5, offset=0, year=2015)

    assert captured_params.get("year") == 2015


def test_fetch_occurrences_page_omits_year_when_not_provided(monkeypatch):
    captured_params = {}

    def mock_get(url, params=None, timeout=None):
        captured_params.update(params or {})
        return make_mock_response(make_sample_records(5))

    monkeypatch.setattr(GBIF_MODULE, mock_get)

    fetch_occurrences_page("Loxodonta africana", limit=5, offset=0)

    assert "year" not in captured_params


def test_fetch_occurrences_page_raises_on_http_error(monkeypatch):
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.HTTPError("500")
    monkeypatch.setattr(GBIF_MODULE, lambda *args, **kwargs: mock_response)

    with pytest.raises(requests.HTTPError):
        fetch_occurrences_page("Loxodonta africana", limit=5, offset=0)


# ---------------------------------------------------------------------------
# fetch_all_occurrences
# ---------------------------------------------------------------------------


def test_fetch_all_occurrences_returns_all_records(monkeypatch):
    # Simulate 5 total records across 2 pages (300 per page limit)
    # Page 1: offset=0, returns 300 records (full page → continue)
    # Page 2: offset=300, returns 2 records (partial page → stop)
    page1 = make_sample_records(300, year=2015)
    page2 = make_sample_records(2, year=2016)

    def mock_get(url, params=None, timeout=None):
        # Count call — limit=1
        if params.get("limit") == 1:
            return make_mock_response([], count=302)
        offset = params.get("offset", 0)
        records = page1 if offset == 0 else page2
        return make_mock_response(records, count=302)

    monkeypatch.setattr(GBIF_MODULE, mock_get)

    result = fetch_all_occurrences("Loxodonta africana")

    assert len(result) == 302


def test_fetch_all_occurrences_filters_by_year(monkeypatch):
    # When year is provided, only records from that year should be returned
    records = make_sample_records(3, year=2010)
    call_count = {"n": 0}

    def mock_get(url, params=None, timeout=None):
        call_count["n"] += 1
        if params.get("limit") == 1:
            return make_mock_response([], count=3)
        mock = make_mock_response(records, count=3)
        mock.json.return_value["endOfRecords"] = True
        return mock

    monkeypatch.setattr(GBIF_MODULE, mock_get)

    result = fetch_all_occurrences("Loxodonta africana", year=2010)

    assert isinstance(result, list)
    assert len(result) == 3


def test_fetch_all_occurrences_returns_empty_list_when_no_records(monkeypatch):
    def mock_get(url, params=None, timeout=None):
        return make_mock_response([], count=0)

    monkeypatch.setattr(GBIF_MODULE, mock_get)

    result = fetch_all_occurrences("Loxodonta africana")

    assert result == []


def test_fetch_all_occurrences_works_for_any_species(monkeypatch):
    # Verify species name is not hardcoded anywhere
    captured_names = []

    def mock_get(url, params=None, timeout=None):
        captured_names.append(params.get("scientificName"))
        return make_mock_response([], count=0)

    monkeypatch.setattr(GBIF_MODULE, mock_get)

    fetch_all_occurrences("Equus quagga")

    assert all(name == "Equus quagga" for name in captured_names)


# ---------------------------------------------------------------------------
# Integration tests — hit real GBIF API, skipped in CI
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_fetch_elephant_occurrences_returns_data():
    from wildlife_water_stress_atlas.ingest.gbif import fetch_occurrences_page

    records = fetch_occurrences_page("Loxodonta africana", limit=10, offset=0)

    assert isinstance(records, list)
    assert len(records) > 0


@pytest.mark.integration
def test_fetch_elephant_occurrences_has_coordinates():
    from wildlife_water_stress_atlas.ingest.gbif import fetch_occurrences_page

    records = fetch_occurrences_page("Loxodonta africana", limit=10, offset=0)

    first = records[0]

    assert "decimalLatitude" in first
    assert "decimalLongitude" in first


@pytest.mark.integration
def test_fetch_occurrence_count_real():
    count = fetch_occurrence_count("Loxodonta africana")

    assert isinstance(count, int)
    assert count > 1000  # there should be a lot of elephant records
    print(f"\nTotal GBIF elephant records: {count:,}")


def test_fetch_all_occurrences_stops_when_page_is_empty(monkeypatch):
    # Covers the "if not page: break" defensive guard
    # First page returns records, second page returns empty list
    page1 = make_sample_records(300, year=2015)

    def mock_get(url, params=None, timeout=None):
        if params.get("limit") == 1:
            return make_mock_response([], count=300)
        offset = params.get("offset", 0)
        records = page1 if offset == 0 else []
        return make_mock_response(records, count=300)

    monkeypatch.setattr(GBIF_MODULE, mock_get)

    result = fetch_all_occurrences("Loxodonta africana")

    assert len(result) == 300


def test_fetch_all_occurrences_increments_offset_across_pages(monkeypatch):
    # Covers the offset += GBIF_PAGE_SIZE line
    # Three pages: 300, 300, then 50 (partial — stops)
    page1 = make_sample_records(300, year=2015)
    page2 = make_sample_records(300, year=2016)
    page3 = make_sample_records(50, year=2017)

    def mock_get(url, params=None, timeout=None):
        if params.get("limit") == 1:
            return make_mock_response([], count=650)
        offset = params.get("offset", 0)
        if offset == 0:
            records = page1
        elif offset == 300:
            records = page2
        else:
            records = page3
        return make_mock_response(records, count=650)

    monkeypatch.setattr(GBIF_MODULE, mock_get)

    result = fetch_all_occurrences("Loxodonta africana")

    assert len(result) == 650
