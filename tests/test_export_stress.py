"""
test_export_stress.py

Phase C2: compute_species_stress composes the overlap layer (distance from each
occurrence to each stressor's features) + the generic engine to produce, per
occurrence, a per-stressor score breakdown AND the cumulative aggregate.

This is the engine's first real consumer over geospatial data. The golden guard
cross-checks it against the LEGACY per-stressor pipelines over the same fixtures:
the generic road/settlement/water columns must match road_threat_score /
settlement_threat_score / water_stress_score exactly.
"""

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point

from scripts.export_road_threats import compute_road_threats
from scripts.export_settlement_threats import compute_settlement_threats
from scripts.export_stress import compute_species_stress
from wildlife_water_stress_atlas.analytics.overlap import add_distance_to_water
from wildlife_water_stress_atlas.analytics.scoring import water_stress_score

_FROG = "Hyperolius marmoratus"


@pytest.fixture
def occurrences():
    return gpd.GeoDataFrame(
        {"species": [_FROG, _FROG, _FROG], "year": [2019, 2020, 2021]},
        geometry=[Point(0.05, 0), Point(0.5, 0.2), Point(1.0, 1.0)],
        crs="EPSG:4326",
    )


@pytest.fixture
def water():
    return gpd.GeoDataFrame({"type": ["river"]}, geometry=[LineString([(0, -1), (0, 1)])], crs="EPSG:4326")


@pytest.fixture
def roads():
    return gpd.GeoDataFrame(
        {"road_class": ["motorway", "primary"], "source_id": ["r0", "r1"], "region": ["africa", "africa"]},
        geometry=[LineString([(0.1, -1), (0.1, 1)]), LineString([(0.6, -1), (0.6, 1)])],
        crs="EPSG:4326",
    )


@pytest.fixture
def settlements():
    return gpd.GeoDataFrame(
        {"settlement_class": ["city", "town"], "source_id": ["s0", "s1"], "region": ["africa", "africa"]},
        geometry=[Point(0.2, 0), Point(0.8, 0.5)],
        crs="EPSG:4326",
    )


def _stress(occ, water, roads, settlements):
    return compute_species_stress(occ, water=water, roads=roads, settlements=settlements, species=_FROG)


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------


def test_produces_per_stressor_and_aggregate_columns(occurrences, water, roads, settlements):
    result = _stress(occurrences, water, roads, settlements)
    for col in ("stress_water", "stress_roads", "stress_settlements", "stress_aggregate"):
        assert col in result.columns
    assert len(result) == len(occurrences)


def test_aggregate_in_unit_interval(occurrences, water, roads, settlements):
    result = _stress(occurrences, water, roads, settlements)
    assert result["stress_aggregate"].between(0.0, 1.0).all()


# ---------------------------------------------------------------------------
# GOLDEN — generic columns reproduce the legacy per-stressor pipelines
# ---------------------------------------------------------------------------


def test_roads_column_matches_legacy_road_threats(occurrences, water, roads, settlements):
    generic = _stress(occurrences, water, roads, settlements)
    legacy = compute_road_threats(occurrences, roads, _FROG)
    assert list(generic["stress_roads"].round(9)) == list(legacy["road_threat_score"].round(9))


def test_settlements_column_matches_legacy_settlement_threats(occurrences, water, roads, settlements):
    generic = _stress(occurrences, water, roads, settlements)
    legacy = compute_settlement_threats(occurrences, settlements, _FROG)
    assert list(generic["stress_settlements"].round(9)) == list(legacy["settlement_threat_score"].round(9))


def test_water_column_matches_legacy_water_stress(occurrences, water, roads, settlements):
    generic = _stress(occurrences, water, roads, settlements)
    legacy = add_distance_to_water(occurrences, water)
    expected = [water_stress_score(d, _FROG) for d in legacy["distance_to_water"]]
    assert list(generic["stress_water"].round(9)) == [round(e, 9) for e in expected]


def test_aggregate_is_noisy_or_of_the_three(occurrences, water, roads, settlements):
    result = _stress(occurrences, water, roads, settlements)
    for _, row in result.iterrows():
        expected = 1 - (1 - row["stress_water"]) * (1 - row["stress_roads"]) * (1 - row["stress_settlements"])
        assert row["stress_aggregate"] == pytest.approx(expected)
