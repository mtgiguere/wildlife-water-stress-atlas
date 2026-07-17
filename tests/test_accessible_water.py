"""
test_accessible_water.py

Tests for water_access.py — species-specific water filtering and weighting.

These tests verify that:
- filter_accessible_water() and get_water_type_weights() read from the
  central species config registry (config/species.py) rather than
  maintaining their own hardcoded dicts.
- The public API (function signatures and return types) is unchanged so
  nothing downstream breaks.
- Adding a new water type to the species config is immediately reflected
  in both functions — this is the key proof that the phantom thirst fix
  will work once pans and wetlands are registered for elephants.
"""

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Polygon

from wildlife_water_stress_atlas.analytics.water_access import (
    filter_accessible_water,
    get_water_type_weights,
)
from wildlife_water_stress_atlas.config.species import get_stressor_params

# ---------------------------------------------------------------------------
# filter_accessible_water
# ---------------------------------------------------------------------------


def test_filter_accessible_water_returns_only_accessible_types():
    # Elephants can now access rivers, lakes, pans, wetlands, floodplains,
    # and surface_water — an unknown type like "bog" should be filtered out
    water = gpd.GeoDataFrame(
        {"water_type": ["river", "lake", "pan", "bog"]},
        geometry=[
            LineString([(0, 0), (1, 1)]),
            Polygon([(0, 0), (0, 1), (1, 1), (1, 0)]),
            Polygon([(5, 5), (5, 6), (6, 6), (6, 5)]),
            Polygon([(8, 8), (8, 9), (9, 9), (9, 8)]),
        ],
        crs="EPSG:4326",
    )

    result = filter_accessible_water(water, species="Loxodonta africana")

    assert set(result["water_type"]) == {"river", "lake", "pan"}
    assert len(result) == 3


def test_filter_accessible_water_returns_empty_when_no_match():
    # Only truly unknown types should produce an empty result now
    water = gpd.GeoDataFrame(
        {"water_type": ["bog", "creek"]},
        geometry=[
            Polygon([(0, 0), (0, 1), (1, 1), (1, 0)]),
            Polygon([(5, 5), (5, 6), (6, 6), (6, 5)]),
        ],
        crs="EPSG:4326",
    )

    result = filter_accessible_water(water, species="Loxodonta africana")

    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 0


def test_filter_accessible_water_raises_for_unknown_species():
    water = gpd.GeoDataFrame(
        {"water_type": ["river"]},
        geometry=[LineString([(0, 0), (1, 1)])],
        crs="EPSG:4326",
    )

    with pytest.raises(KeyError):
        filter_accessible_water(water, species="Unicornus fantasticus")


def test_filter_accessible_water_reads_from_species_config():
    # Proves the function is wired to the species config registry (the stressors
    # list). We temporarily register a new water type on the elephant's water
    # stressor and verify it is immediately reflected in filter_accessible_water()
    # — no code changes, just a config change.
    water_params = get_stressor_params("Loxodonta africana", "water")
    original_types = list(water_params["accessible_types"])
    original_weights = dict(water_params["type_weights"])

    try:
        # Temporarily register a novel type as accessible for elephants
        water_params["accessible_types"].append("test_pool")
        water_params["type_weights"]["test_pool"] = 0.8

        water = gpd.GeoDataFrame(
            {"water_type": ["river", "test_pool"]},
            geometry=[
                LineString([(0, 0), (1, 1)]),
                Polygon([(5, 5), (5, 6), (6, 6), (6, 5)]),
            ],
            crs="EPSG:4326",
        )

        result = filter_accessible_water(water, species="Loxodonta africana")

        # The novel type should now pass through the filter
        assert "test_pool" in set(result["water_type"])
        assert len(result) == 2

    finally:
        # Always restore original config so other tests are not affected
        water_params["accessible_types"][:] = original_types
        water_params["type_weights"].clear()
        water_params["type_weights"].update(original_weights)


# ---------------------------------------------------------------------------
# get_water_type_weights
# ---------------------------------------------------------------------------


def test_get_water_type_weights_returns_correct_weights_for_elephants():
    weights = get_water_type_weights("Loxodonta africana")

    assert weights["river"] == 1.0
    assert weights["lake"] == 1.0
    assert weights["pan"] == 0.4
    assert weights["wetland"] == 0.7
    assert weights["floodplain"] == 0.7
    assert weights["surface_water"] == 0.6
    assert weights["saline_lake"] == 0.4
    assert weights["permanent_water"] == 0.8


def test_get_water_type_weights_raises_for_unknown_species():
    with pytest.raises(KeyError):
        get_water_type_weights("Unicornus fantasticus")


def test_get_water_type_weights_reads_from_species_config():
    # Same proof-of-wiring test as filter_accessible_water above — temporarily
    # add a new type to the water stressor and verify it shows up in
    # get_water_type_weights() immediately.
    water_params = get_stressor_params("Loxodonta africana", "water")
    original_types = list(water_params["accessible_types"])
    original_weights = dict(water_params["type_weights"])

    try:
        water_params["accessible_types"].append("test_pool")
        water_params["type_weights"]["test_pool"] = 0.9

        weights = get_water_type_weights("Loxodonta africana")

        assert "test_pool" in weights
        assert weights["test_pool"] == 0.9

    finally:
        water_params["accessible_types"][:] = original_types
        water_params["type_weights"].clear()
        water_params["type_weights"].update(original_weights)


def test_filter_accessible_water_result_is_a_copy():
    # Verifies the function returns a copy, not a view of the original.
    # Modifying the result should not affect the input water GeoDataFrame.
    water = gpd.GeoDataFrame(
        {"water_type": ["river", "lake"]},
        geometry=[
            LineString([(0, 0), (1, 1)]),
            Polygon([(0, 0), (0, 1), (1, 1), (1, 0)]),
        ],
        crs="EPSG:4326",
    )

    result = filter_accessible_water(water, species="Loxodonta africana")
    result["water_type"] = "modified"

    # Original should be untouched
    assert list(water["water_type"]) == ["river", "lake"]
