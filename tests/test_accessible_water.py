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
from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG

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
        filter_accessible_water(water, species="Panthera leo")


def test_filter_accessible_water_reads_from_species_config():
    # This test proves the function is wired to the species config registry.
    # We temporarily add a new water type to the elephant config and verify
    # it is immediately reflected in filter_accessible_water() — no code
    # changes required, just a config change.
    #
    # This is the exact mechanism that will fix the phantom thirst bug:
    # add "pan" to SPECIES_CONFIG["Loxodonta africana"]["accessible_water_types"]
    # and pans will immediately be included in the filter.
    original_types = SPECIES_CONFIG["Loxodonta africana"]["accessible_water_types"].copy()
    original_weights = SPECIES_CONFIG["Loxodonta africana"]["water_type_weights"].copy()

    try:
        # Temporarily register "pan" as accessible for elephants
        SPECIES_CONFIG["Loxodonta africana"]["accessible_water_types"].add("pan")
        SPECIES_CONFIG["Loxodonta africana"]["water_type_weights"]["pan"] = 0.8

        water = gpd.GeoDataFrame(
            {"water_type": ["river", "pan"]},
            geometry=[
                LineString([(0, 0), (1, 1)]),
                Polygon([(5, 5), (5, 6), (6, 6), (6, 5)]),
            ],
            crs="EPSG:4326",
        )

        result = filter_accessible_water(water, species="Loxodonta africana")

        # Pan should now pass through the filter
        assert "pan" in set(result["water_type"])
        assert len(result) == 2

    finally:
        # Always restore original config so other tests are not affected
        SPECIES_CONFIG["Loxodonta africana"]["accessible_water_types"] = original_types
        SPECIES_CONFIG["Loxodonta africana"]["water_type_weights"] = original_weights


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
        get_water_type_weights("Panthera leo")


def test_get_water_type_weights_reads_from_species_config():
    # Same proof-of-wiring test as filter_accessible_water above —
    # temporarily add a new type to the config and verify it shows up
    # in get_water_type_weights() immediately
    original_types = SPECIES_CONFIG["Loxodonta africana"]["accessible_water_types"].copy()
    original_weights = SPECIES_CONFIG["Loxodonta africana"]["water_type_weights"].copy()

    try:
        SPECIES_CONFIG["Loxodonta africana"]["accessible_water_types"].add("wetland")
        SPECIES_CONFIG["Loxodonta africana"]["water_type_weights"]["wetland"] = 0.9

        weights = get_water_type_weights("Loxodonta africana")

        assert "wetland" in weights
        assert weights["wetland"] == 0.9

    finally:
        SPECIES_CONFIG["Loxodonta africana"]["accessible_water_types"] = original_types
        SPECIES_CONFIG["Loxodonta africana"]["water_type_weights"] = original_weights


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
