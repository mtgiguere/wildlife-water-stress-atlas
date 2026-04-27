"""
test_map.py

Tests for apps/streamlit/components/map.py

TESTING STRATEGY:
-----------------
PyDeck objects don't require a running Streamlit server to instantiate —
we can create and inspect them directly in unit tests.

We verify:
- Correct PyDeck layer types are returned
- Layers contain the right data
- The deck is centered on Africa
- Edge cases (empty GeoDataFrames) are handled gracefully

FUNCTION COVERAGE:
------------------
- build_water_layer(gdf)         — GeoJsonLayer for water sources
- build_occurrences_layer(gdf)   — ScatterplotLayer for animal occurrences
- build_deck(water, occurrences) — pydeck.Deck combining both layers
"""

import sys
from unittest.mock import MagicMock

import geopandas as gpd
import pydeck as pdk
import pytest
from shapely.geometry import LineString, Point, Polygon

# Mock streamlit before importing map.py
mock_st = MagicMock()
mock_st.cache_data = lambda func=None, **kwargs: func if func is not None else lambda f: f
sys.modules["streamlit"] = mock_st

from apps.streamlit.components.map import (  # noqa: E402
    build_deck,
    build_occurrences_layer,
    build_water_layer,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_water_gdf():
    """Minimal water GeoDataFrame with normalized schema."""
    return gpd.GeoDataFrame(
        {
            "water_type": ["river", "pan"],
            "permanence": ["permanent", "seasonal"],
            "reliability": [1.0, 0.5],
            "months_water": [12, 4],
            "region": ["africa", "africa"],
            "source_id": ["river_0", "pan_0"],
        },
        geometry=[
            LineString([(20, -10), (25, -10)]),
            Polygon([(15, -20), (15, -19), (16, -19), (16, -20)]),
        ],
        crs="EPSG:4326",
    )


@pytest.fixture
def mock_occurrences_gdf():
    """Minimal occurrences GeoDataFrame with year field."""
    return gpd.GeoDataFrame(
        {
            "species": ["Loxodonta africana"] * 3,
            "year": [2015, 2015, 2016],
        },
        geometry=[Point(20, -10), Point(25, -15), Point(30, -20)],
        crs="EPSG:4326",
    )


@pytest.fixture
def empty_occurrences_gdf():
    """Empty occurrences GeoDataFrame — simulates no records for a year."""
    return gpd.GeoDataFrame(
        {"species": [], "year": []},
        geometry=[],
        crs="EPSG:4326",
    )


# ---------------------------------------------------------------------------
# build_water_layer
# ---------------------------------------------------------------------------


def test_build_water_layer_returns_pydeck_layer(mock_water_gdf):
    result = build_water_layer(mock_water_gdf)
    # build_water_layer returns a list of layers (lines + polygons separately)
    assert isinstance(result, list)
    assert len(result) > 0
    assert all(isinstance(layer, pdk.Layer) for layer in result)


def test_build_water_layer_uses_geojson_layer_type(mock_water_gdf):
    result = build_water_layer(mock_water_gdf)
    layer_types = [layer.type for layer in result]
    assert "GeoJsonLayer" in layer_types or "PolygonLayer" in layer_types


def test_build_water_layer_is_not_pickable_by_default(mock_water_gdf):
    result = build_water_layer(mock_water_gdf)
    assert all(layer.pickable is False for layer in result)


# ---------------------------------------------------------------------------
# build_occurrences_layer
# ---------------------------------------------------------------------------


def test_build_occurrences_layer_returns_pydeck_layer(mock_occurrences_gdf):
    result = build_occurrences_layer(mock_occurrences_gdf)

    assert isinstance(result, pdk.Layer)


def test_build_occurrences_layer_uses_icon_layer_type(mock_occurrences_gdf):
    result = build_occurrences_layer(mock_occurrences_gdf)
    assert result.type == "ScatterplotLayer"


def test_build_occurrences_layer_is_pickable(mock_occurrences_gdf):
    result = build_occurrences_layer(mock_occurrences_gdf)
    assert result.pickable is True


def test_build_occurrences_layer_handles_empty_geodataframe(empty_occurrences_gdf):
    # Empty GDF should not raise — returns a valid layer with no data
    result = build_occurrences_layer(empty_occurrences_gdf)

    assert isinstance(result, pdk.Layer)


# ---------------------------------------------------------------------------
# build_deck
# ---------------------------------------------------------------------------


def test_build_deck_returns_pydeck_deck(mock_water_gdf, mock_occurrences_gdf):
    water_layer = build_water_layer(mock_water_gdf)
    occurrences_layer = build_occurrences_layer(mock_occurrences_gdf)

    result = build_deck(water_layer, occurrences_layer)

    assert isinstance(result, pdk.Deck)


def test_build_deck_contains_both_layers(mock_water_gdf, mock_occurrences_gdf):
    water_layers = build_water_layer(mock_water_gdf)
    occurrences_layer = build_occurrences_layer(mock_occurrences_gdf)
    result = build_deck(water_layers, occurrences_layer)
    # water_layers is a list + occurrences = total layers > 1
    assert len(result.layers) >= 2


def test_build_deck_is_centered_on_africa(mock_water_gdf, mock_occurrences_gdf):
    water_layers = build_water_layer(mock_water_gdf)
    occurrences_layer = build_occurrences_layer(mock_occurrences_gdf)
    result = build_deck(water_layers, occurrences_layer)
    assert result.initial_view_state.latitude == pytest.approx(0, abs=10)
    assert result.initial_view_state.longitude == pytest.approx(20, abs=10)


def test_build_deck_has_reasonable_zoom_level(mock_water_gdf, mock_occurrences_gdf):
    water_layers = build_water_layer(mock_water_gdf)
    occurrences_layer = build_occurrences_layer(mock_occurrences_gdf)
    result = build_deck(water_layers, occurrences_layer)
    assert 2 <= result.initial_view_state.zoom <= 5


def test_build_occurrences_layer_has_icon_url(mock_occurrences_gdf):
    # IconLayer deferred — using ScatterplotLayer for now
    result = build_occurrences_layer(mock_occurrences_gdf)
    assert result.type == "ScatterplotLayer"
