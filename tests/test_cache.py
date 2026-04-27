"""
test_cache.py

Tests for apps/streamlit/components/cache.py

TESTING STRATEGY:
-----------------
cache.py uses @st.cache_data which requires a Streamlit context.
We mock streamlit.cache_data as a passthrough decorator so the
functions can be tested without a running Streamlit server.

We also mock the file system so tests don't depend on real data files
in data/processed/ — unit tests must be hermetic.

FUNCTION COVERAGE:
------------------
- load_water_layer()   — loads from gpkg cache or runs pipeline
- load_gbif_data()     — loads from gpkg cache, filters by year
"""

# ---------------------------------------------------------------------------
# Mock st.cache_data as a passthrough decorator before importing cache.py
# This prevents "streamlit context not found" errors in unit tests
# ---------------------------------------------------------------------------
import sys
from unittest.mock import MagicMock, patch

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point, Polygon

mock_st = MagicMock()
mock_st.cache_data = lambda func=None, **kwargs: func if func is not None else lambda f: f
mock_st.spinner = MagicMock()
mock_st.spinner.return_value.__enter__ = MagicMock(return_value=None)
mock_st.spinner.return_value.__exit__ = MagicMock(return_value=False)
sys.modules["streamlit"] = mock_st

from apps.streamlit.components.cache import (  # noqa: E402
    load_gbif_data,
    load_water_layer,
    load_water_layer_simplified,
    simplify_water_for_browser,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_water_gdf():
    """Minimal water GeoDataFrame matching normalized schema."""
    return gpd.GeoDataFrame(
        {
            "water_type": ["river", "pan"],
            "mechanism": ["permanent_surface", "seasonal_surface"],
            "permanence": ["permanent", "seasonal"],
            "reliability": [1.0, 0.5],
            "months_water": [12, 4],
            "region": ["africa", "africa"],
            "source_id": ["river_0", "pan_0"],
        },
        geometry=[
            LineString([(0, 0), (1, 1)]),
            Point(5, 5),
        ],
        crs="EPSG:4326",
    )


@pytest.fixture
def mock_gbif_gdf():
    """Minimal GBIF GeoDataFrame with year field."""
    return gpd.GeoDataFrame(
        {
            "species": ["Loxodonta africana"] * 5,
            "year": [2015, 2015, 2016, 2017, 2018],
        },
        geometry=[Point(i, i) for i in range(5)],
        crs="EPSG:4326",
    )


# ---------------------------------------------------------------------------
# load_water_layer — cache hit
# ---------------------------------------------------------------------------


def test_load_water_layer_loads_from_cache_when_file_exists(mock_water_gdf, tmp_path, monkeypatch):
    # Write mock GDF to a temp gpkg to simulate existing cache
    cache_file = tmp_path / "water_africa.gpkg"
    mock_water_gdf.to_file(cache_file, driver="GPKG")

    monkeypatch.setattr(
        "apps.streamlit.components.cache.WATER_CACHE_PATH",
        cache_file,
    )

    result = load_water_layer()

    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 2
    assert "water_type" in result.columns


def test_load_water_layer_cache_has_correct_crs(mock_water_gdf, tmp_path, monkeypatch):
    cache_file = tmp_path / "water_africa.gpkg"
    mock_water_gdf.to_file(cache_file, driver="GPKG")

    monkeypatch.setattr(
        "apps.streamlit.components.cache.WATER_CACHE_PATH",
        cache_file,
    )

    result = load_water_layer()

    assert result.crs.to_string() == "EPSG:4326"


# ---------------------------------------------------------------------------
# load_water_layer — cache miss
# ---------------------------------------------------------------------------


def test_load_water_layer_calls_pipeline_when_cache_missing(mock_water_gdf, tmp_path, monkeypatch):
    # Point to a non-existent cache file
    cache_file = tmp_path / "water_africa.gpkg"

    monkeypatch.setattr(
        "apps.streamlit.components.cache.WATER_CACHE_PATH",
        cache_file,
    )

    with patch(
        "apps.streamlit.components.cache.load_all_water",
        return_value=mock_water_gdf,
    ) as mock_load:
        result = load_water_layer()

    mock_load.assert_called_once()
    assert isinstance(result, gpd.GeoDataFrame)


def test_load_water_layer_saves_to_cache_after_pipeline_run(mock_water_gdf, tmp_path, monkeypatch):
    cache_file = tmp_path / "water_africa.gpkg"

    monkeypatch.setattr(
        "apps.streamlit.components.cache.WATER_CACHE_PATH",
        cache_file,
    )

    with patch(
        "apps.streamlit.components.cache.load_all_water",
        return_value=mock_water_gdf,
    ):
        load_water_layer()

    # Cache file should now exist
    assert cache_file.exists()


# ---------------------------------------------------------------------------
# load_gbif_data — cache hit
# ---------------------------------------------------------------------------


def test_load_gbif_data_loads_from_cache_when_file_exists(mock_gbif_gdf, tmp_path, monkeypatch):
    cache_file = tmp_path / "gbif_loxodonta_africana.gpkg"
    mock_gbif_gdf.to_file(cache_file, driver="GPKG")

    monkeypatch.setattr(
        "apps.streamlit.components.cache.GBIF_CACHE_PATH",
        cache_file,
    )

    result = load_gbif_data()

    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 5


def test_load_gbif_data_cache_has_correct_crs(mock_gbif_gdf, tmp_path, monkeypatch):
    cache_file = tmp_path / "gbif_loxodonta_africana.gpkg"
    mock_gbif_gdf.to_file(cache_file, driver="GPKG")

    monkeypatch.setattr(
        "apps.streamlit.components.cache.GBIF_CACHE_PATH",
        cache_file,
    )

    result = load_gbif_data()

    assert result.crs.to_string() == "EPSG:4326"


# ---------------------------------------------------------------------------
# load_gbif_data — year filtering (always from cache)
# ---------------------------------------------------------------------------


def test_load_gbif_data_filters_by_year(mock_gbif_gdf, tmp_path, monkeypatch):
    # 2 records in 2015, 1 in 2016, 1 in 2017, 1 in 2018
    cache_file = tmp_path / "gbif_loxodonta_africana.gpkg"
    mock_gbif_gdf.to_file(cache_file, driver="GPKG")

    monkeypatch.setattr(
        "apps.streamlit.components.cache.GBIF_CACHE_PATH",
        cache_file,
    )

    result = load_gbif_data(year=2015)

    assert len(result) == 2
    assert (result["year"] == 2015).all()


def test_load_gbif_data_returns_all_records_when_no_year(mock_gbif_gdf, tmp_path, monkeypatch):
    cache_file = tmp_path / "gbif_loxodonta_africana.gpkg"
    mock_gbif_gdf.to_file(cache_file, driver="GPKG")

    monkeypatch.setattr(
        "apps.streamlit.components.cache.GBIF_CACHE_PATH",
        cache_file,
    )

    result = load_gbif_data()

    assert len(result) == 5


def test_load_gbif_data_returns_empty_when_no_records_for_year(mock_gbif_gdf, tmp_path, monkeypatch):
    cache_file = tmp_path / "gbif_loxodonta_africana.gpkg"
    mock_gbif_gdf.to_file(cache_file, driver="GPKG")

    monkeypatch.setattr(
        "apps.streamlit.components.cache.GBIF_CACHE_PATH",
        cache_file,
    )

    result = load_gbif_data(year=1900)

    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 0


# ---------------------------------------------------------------------------
# load_gbif_data — cache miss
# ---------------------------------------------------------------------------


def test_load_gbif_data_calls_fetch_when_cache_missing(mock_gbif_gdf, tmp_path, monkeypatch):
    cache_file = tmp_path / "gbif_loxodonta_africana.gpkg"

    monkeypatch.setattr(
        "apps.streamlit.components.cache.GBIF_CACHE_PATH",
        cache_file,
    )

    with patch(
        "apps.streamlit.components.cache.fetch_all_occurrences",
        return_value=[{"decimalLatitude": i, "decimalLongitude": i, "year": 2015, "species": "Loxodonta africana"} for i in range(5)],
    ) as mock_fetch:
        result = load_gbif_data()

    mock_fetch.assert_called_once()
    assert isinstance(result, gpd.GeoDataFrame)


def test_load_gbif_data_saves_to_cache_after_fetch(mock_gbif_gdf, tmp_path, monkeypatch):
    cache_file = tmp_path / "gbif_loxodonta_africana.gpkg"

    monkeypatch.setattr(
        "apps.streamlit.components.cache.GBIF_CACHE_PATH",
        cache_file,
    )

    with patch(
        "apps.streamlit.components.cache.fetch_all_occurrences",
        return_value=[{"decimalLatitude": i, "decimalLongitude": i, "year": 2015, "species": "Loxodonta africana"} for i in range(5)],
    ):
        load_gbif_data()

    assert cache_file.exists()


# ---------------------------------------------------------------------------
# Fixtures (add to existing fixtures)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_water_gdf_with_ephemerals():
    """Water GeoDataFrame with mixed permanence and reliability values."""
    return gpd.GeoDataFrame(
        {
            "water_type": ["river", "pan", "wetland", "pan", "floodplain"],
            "mechanism": ["permanent_surface"] * 5,
            "permanence": ["permanent", "ephemeral", "seasonal", "ephemeral", "seasonal"],
            "reliability": [1.0, 0.3, 0.7, 0.2, 0.6],
            "months_water": [12, 2, 8, 1, 6],
            "region": ["africa"] * 5,
            "source_id": [f"feature_{i}" for i in range(5)],
        },
        geometry=[
            LineString([(0, 0), (1, 1)]),
            Point(2, 2),
            Polygon([(3, 3), (3, 4), (4, 4), (4, 3)]),
            Point(5, 5),
            Polygon([(6, 6), (6, 7), (7, 7), (7, 6)]),
        ],
        crs="EPSG:4326",
    )


# ---------------------------------------------------------------------------
# simplify_water_for_browser
# ---------------------------------------------------------------------------


def test_simplify_water_for_browser_returns_geodataframe(
    mock_water_gdf_with_ephemerals,
):
    result = simplify_water_for_browser(mock_water_gdf_with_ephemerals)

    assert isinstance(result, gpd.GeoDataFrame)


def test_simplify_water_for_browser_removes_ephemeral_features(
    mock_water_gdf_with_ephemerals,
):
    result = simplify_water_for_browser(mock_water_gdf_with_ephemerals)

    assert "ephemeral" not in result["permanence"].values


def test_simplify_water_for_browser_removes_low_reliability_features(
    mock_water_gdf_with_ephemerals,
):
    result = simplify_water_for_browser(mock_water_gdf_with_ephemerals)

    assert (result["reliability"] >= 0.5).all()


def test_simplify_water_for_browser_has_fewer_features_than_input(
    mock_water_gdf_with_ephemerals,
):
    result = simplify_water_for_browser(mock_water_gdf_with_ephemerals)

    assert len(result) < len(mock_water_gdf_with_ephemerals)


def test_simplify_water_for_browser_preserves_crs(
    mock_water_gdf_with_ephemerals,
):
    result = simplify_water_for_browser(mock_water_gdf_with_ephemerals)

    assert result.crs.to_string() == "EPSG:4326"


def test_simplify_water_for_browser_preserves_schema(
    mock_water_gdf_with_ephemerals,
):
    result = simplify_water_for_browser(mock_water_gdf_with_ephemerals)

    required_columns = {
        "geometry",
        "source_id",
        "water_type",
        "mechanism",
        "permanence",
        "reliability",
        "months_water",
        "region",
    }
    assert required_columns.issubset(result.columns)


def test_simplify_water_for_browser_no_empty_geometries(
    mock_water_gdf_with_ephemerals,
):
    result = simplify_water_for_browser(mock_water_gdf_with_ephemerals)

    assert not result.geometry.is_empty.any()


def test_simplify_water_for_browser_handles_empty_input():
    empty = gpd.GeoDataFrame(
        {
            "water_type": [],
            "mechanism": [],
            "permanence": [],
            "reliability": [],
            "months_water": [],
            "region": [],
            "source_id": [],
        },
        geometry=[],
        crs="EPSG:4326",
    )

    result = simplify_water_for_browser(empty)

    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 0


# ---------------------------------------------------------------------------
# load_water_layer_simplified — cache hit
# ---------------------------------------------------------------------------


def test_load_water_layer_simplified_loads_from_cache_when_file_exists(mock_water_gdf, tmp_path, monkeypatch):
    cache_file = tmp_path / "water_africa_simplified.gpkg"
    mock_water_gdf.to_file(cache_file, driver="GPKG")

    monkeypatch.setattr(
        "apps.streamlit.components.cache.WATER_SIMPLIFIED_CACHE_PATH",
        cache_file,
    )

    result = load_water_layer_simplified()

    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 2


def test_load_water_layer_simplified_cache_has_correct_crs(mock_water_gdf, tmp_path, monkeypatch):
    cache_file = tmp_path / "water_africa_simplified.gpkg"
    mock_water_gdf.to_file(cache_file, driver="GPKG")

    monkeypatch.setattr(
        "apps.streamlit.components.cache.WATER_SIMPLIFIED_CACHE_PATH",
        cache_file,
    )

    result = load_water_layer_simplified()

    assert result.crs.to_string() == "EPSG:4326"


# ---------------------------------------------------------------------------
# load_water_layer_simplified — cache miss
# ---------------------------------------------------------------------------


def test_load_water_layer_simplified_calls_pipeline_when_cache_missing(mock_water_gdf, tmp_path, monkeypatch):
    cache_file = tmp_path / "water_africa_simplified.gpkg"
    full_cache_file = tmp_path / "water_africa.gpkg"
    mock_water_gdf.to_file(full_cache_file, driver="GPKG")

    monkeypatch.setattr(
        "apps.streamlit.components.cache.WATER_SIMPLIFIED_CACHE_PATH",
        cache_file,
    )
    monkeypatch.setattr(
        "apps.streamlit.components.cache.WATER_CACHE_PATH",
        full_cache_file,
    )

    result = load_water_layer_simplified()

    assert isinstance(result, gpd.GeoDataFrame)


def test_load_water_layer_simplified_saves_to_cache_after_build(mock_water_gdf, tmp_path, monkeypatch):
    cache_file = tmp_path / "water_africa_simplified.gpkg"
    full_cache_file = tmp_path / "water_africa.gpkg"
    mock_water_gdf.to_file(full_cache_file, driver="GPKG")

    monkeypatch.setattr(
        "apps.streamlit.components.cache.WATER_SIMPLIFIED_CACHE_PATH",
        cache_file,
    )
    monkeypatch.setattr(
        "apps.streamlit.components.cache.WATER_CACHE_PATH",
        full_cache_file,
    )

    load_water_layer_simplified()

    assert cache_file.exists()
