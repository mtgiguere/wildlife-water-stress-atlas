"""
test_sidebar.py

Tests for apps/streamlit/components/sidebar.py

TESTING STRATEGY:
-----------------
Streamlit rendering functions (st.slider, st.metric, st.write) cannot
be unit tested without a running Streamlit server — those are covered
by Playwright E2E tests.

What we CAN unit test are the pure data functions that compute values
displayed in the sidebar. These have no Streamlit dependency and are
fully testable in isolation.

FUNCTION COVERAGE:
------------------
- get_year_range(gdf)   — min and max year from GeoDataFrame
- get_record_count(gdf) — total number of records
- get_year_counts(gdf)  — dict of year → record count, sorted
"""

import sys
from unittest.mock import MagicMock

import geopandas as gpd
import pytest
from shapely.geometry import Point

# Mock streamlit before importing sidebar.py
mock_st = MagicMock()
mock_st.cache_data = lambda func=None, **kwargs: func if func is not None else lambda f: f
sys.modules["streamlit"] = mock_st

from apps.streamlit.components.sidebar import (  # noqa: E402
    get_record_count,
    get_year_counts,
    get_year_range,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_occurrences_gdf():
    """GeoDataFrame with known year distribution."""
    return gpd.GeoDataFrame(
        {
            "species": ["Loxodonta africana"] * 7,
            "year": [2015, 2015, 2016, 2017, 2017, 2017, 2018],
        },
        geometry=[Point(i, i) for i in range(7)],
        crs="EPSG:4326",
    )


@pytest.fixture
def mock_occurrences_with_missing_years():
    """GeoDataFrame where some records have no year."""
    return gpd.GeoDataFrame(
        {
            "species": ["Loxodonta africana"] * 5,
            "year": [2015, None, 2016, None, 2017],
        },
        geometry=[Point(i, i) for i in range(5)],
        crs="EPSG:4326",
    )


@pytest.fixture
def empty_gdf():
    """Empty GeoDataFrame."""
    return gpd.GeoDataFrame(
        {"species": [], "year": []},
        geometry=[],
        crs="EPSG:4326",
    )


# ---------------------------------------------------------------------------
# get_year_range
# ---------------------------------------------------------------------------


def test_get_year_range_returns_min_and_max_year(mock_occurrences_gdf):
    min_year, max_year = get_year_range(mock_occurrences_gdf)

    assert min_year == 2015
    assert max_year == 2018


def test_get_year_range_returns_integers(mock_occurrences_gdf):
    min_year, max_year = get_year_range(mock_occurrences_gdf)

    assert isinstance(min_year, int)
    assert isinstance(max_year, int)


def test_get_year_range_ignores_missing_years(mock_occurrences_with_missing_years):
    # None/NaN year values should not affect the range
    min_year, max_year = get_year_range(mock_occurrences_with_missing_years)

    assert min_year == 2015
    assert max_year == 2017


def test_get_year_range_single_year():
    gdf = gpd.GeoDataFrame(
        {"species": ["Loxodonta africana"] * 3, "year": [2015, 2015, 2015]},
        geometry=[Point(i, i) for i in range(3)],
        crs="EPSG:4326",
    )

    min_year, max_year = get_year_range(gdf)

    assert min_year == 2015
    assert max_year == 2015


# ---------------------------------------------------------------------------
# get_record_count
# ---------------------------------------------------------------------------


def test_get_record_count_returns_correct_count(mock_occurrences_gdf):
    count = get_record_count(mock_occurrences_gdf)

    assert count == 7


def test_get_record_count_returns_zero_for_empty_gdf(empty_gdf):
    count = get_record_count(empty_gdf)

    assert count == 0


def test_get_record_count_returns_integer(mock_occurrences_gdf):
    count = get_record_count(mock_occurrences_gdf)

    assert isinstance(count, int)


# ---------------------------------------------------------------------------
# get_year_counts
# ---------------------------------------------------------------------------


def test_get_year_counts_returns_dict(mock_occurrences_gdf):
    result = get_year_counts(mock_occurrences_gdf)

    assert isinstance(result, dict)


def test_get_year_counts_correct_values(mock_occurrences_gdf):
    # 2015: 2, 2016: 1, 2017: 3, 2018: 1
    result = get_year_counts(mock_occurrences_gdf)

    assert result[2015] == 2
    assert result[2016] == 1
    assert result[2017] == 3
    assert result[2018] == 1


def test_get_year_counts_is_sorted_by_year(mock_occurrences_gdf):
    result = get_year_counts(mock_occurrences_gdf)

    years = list(result.keys())
    assert years == sorted(years)


def test_get_year_counts_ignores_missing_years(mock_occurrences_with_missing_years):
    # Records with None year should not appear in counts
    result = get_year_counts(mock_occurrences_with_missing_years)

    assert None not in result
    assert len(result) == 3  # only 2015, 2016, 2017


def test_get_year_counts_returns_empty_dict_for_empty_gdf(empty_gdf):
    result = get_year_counts(empty_gdf)

    assert result == {}
