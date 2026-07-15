"""
test_settlement_overlap.py

Tests for add_distance_to_settlement in
src/wildlife_water_stress_atlas/analytics/overlap.py

Mirrors add_distance_to_road: for each occurrence, find the nearest settlement
(via sjoin_nearest) and record its distance (meters) and settlement_class.
"""

import geopandas as gpd
from shapely.geometry import Point

from wildlife_water_stress_atlas.analytics.overlap import add_distance_to_settlement


def _settlements(rows):
    """rows: list of (settlement_class, x, y)."""
    return gpd.GeoDataFrame(
        {"settlement_class": [r[0] for r in rows]},
        geometry=[Point(r[1], r[2]) for r in rows],
        crs="EPSG:4326",
    )


def test_add_distance_to_settlement_adds_columns():
    occurrences = gpd.GeoDataFrame(
        {"species": ["Panthera leo"]},
        geometry=[Point(1, 1)],
        crs="EPSG:4326",
    )
    settlements = _settlements([("city", 0, 0)])

    result = add_distance_to_settlement(occurrences, settlements)

    assert "distance_to_settlement_m" in result.columns
    assert "settlement_class" in result.columns
    assert len(result) == 1


def test_add_distance_to_settlement_picks_nearest_class():
    """The recorded settlement_class must be that of the NEAREST settlement."""
    occurrences = gpd.GeoDataFrame(
        {"species": ["Panthera leo"]},
        geometry=[Point(0.1, 0.0)],  # very close to the village at (0,0)
        crs="EPSG:4326",
    )
    settlements = _settlements(
        [
            ("village", 0.0, 0.0),  # nearest
            ("city", 5.0, 0.0),  # far
        ]
    )

    result = add_distance_to_settlement(occurrences, settlements)

    assert result.iloc[0]["settlement_class"] == "village"


def test_add_distance_to_settlement_distance_is_in_meters():
    """~1 degree separation should read as tens of thousands of meters, not ~1 (degrees)."""
    occurrences = gpd.GeoDataFrame(
        {"species": ["Panthera leo"]},
        geometry=[Point(1, 0)],
        crs="EPSG:4326",
    )
    settlements = _settlements([("city", 0, 0)])

    result = add_distance_to_settlement(occurrences, settlements)

    distance = result.iloc[0]["distance_to_settlement_m"]
    assert distance > 10_000, f"Distance {distance}m looks like degrees, not meters"
    assert distance < 200_000, f"Distance {distance}m is implausibly large for a 1-degree separation"


def test_add_distance_to_settlement_preserves_row_count_with_equidistant():
    """Equidistant settlements must not multiply the occurrence rows."""
    occurrences = gpd.GeoDataFrame(
        {"species": ["Panthera leo"]},
        geometry=[Point(0, 0)],
        crs="EPSG:4326",
    )
    # Two settlements exactly equidistant from the occurrence
    settlements = _settlements([("city", 1, 0), ("city", -1, 0)])

    result = add_distance_to_settlement(occurrences, settlements)

    assert len(result) == 1


def test_add_distance_to_settlement_empty_occurrences_returns_empty():
    occurrences = gpd.GeoDataFrame(
        {"species": []},
        geometry=[],
        crs="EPSG:4326",
    )
    settlements = _settlements([("city", 0, 0)])

    result = add_distance_to_settlement(occurrences, settlements)

    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 0


def test_add_distance_to_settlement_output_is_wgs84():
    occurrences = gpd.GeoDataFrame(
        {"species": ["Panthera leo"]},
        geometry=[Point(1, 1)],
        crs="EPSG:4326",
    )
    settlements = _settlements([("city", 0, 0)])

    result = add_distance_to_settlement(occurrences, settlements)

    assert result.crs.to_string() == "EPSG:4326"
