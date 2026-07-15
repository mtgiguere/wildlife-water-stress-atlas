"""
test_stress_engine.py

Tests for the generic scoring engine (docs/ARCHITECTURE.md §5–§6, BACKLOG B4).

The engine is QUERY-shaped: score_species_stress(species, measurements) scores
ONE species at ONE location from the measurements the data layer hands it —
per-stressor Scores + a noisy-OR aggregate. (A batch driver loops it over
locations to bake tiles; the same function runs on-demand later — §10.)

THE GOLDEN GUARD: the generic engine reproduces today's EXACT scores for all 11
species — road_threat_score, settlement_threat_score, water_stress_score — so
the whole extensible refactor provably preserves behavior.
"""

import pytest

from wildlife_water_stress_atlas.analytics.scoring import water_stress_score
from wildlife_water_stress_atlas.analytics.stress_engine import (
    STRESSOR_TYPES,
    StressResult,
    score_species_stress,
    species_stressors,
)
from wildlife_water_stress_atlas.analytics.stressors import FeatureProximity, Score
from wildlife_water_stress_atlas.analytics.threat_scoring import road_threat_score, settlement_threat_score
from wildlife_water_stress_atlas.config.species import (
    KNOWN_ROAD_CLASSES,
    KNOWN_SETTLEMENT_CLASSES,
    SPECIES_CONFIG,
)

_ALL_SPECIES = sorted(SPECIES_CONFIG.keys())
_DISTANCES = [0, 100, 1_000, 5_000, 50_000, 300_000]


# ---------------------------------------------------------------------------
# Registry + config builder
# ---------------------------------------------------------------------------


def test_stressor_types_registry_covers_the_three_current_stressors():
    assert {"water", "roads", "settlements"} <= set(STRESSOR_TYPES)


@pytest.mark.parametrize("species", _ALL_SPECIES)
def test_species_stressors_builds_the_three_configs(species):
    ids = {c.stressor_id for c in species_stressors(species)}
    assert ids == {"water", "roads", "settlements"}


# ---------------------------------------------------------------------------
# THE GOLDEN GUARD — generic engine reproduces legacy scores, all 11 species
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("species", _ALL_SPECIES)
@pytest.mark.parametrize("road_class", sorted(KNOWN_ROAD_CLASSES))
def test_engine_reproduces_road_threat_score(species, road_class):
    for d in _DISTANCES:
        result = score_species_stress(species, {"roads": FeatureProximity(d, road_class)})
        assert result.breakdown["roads"].value == pytest.approx(road_threat_score(d, road_class, species)), f"{species} roads/{road_class}@{d}m"


@pytest.mark.parametrize("species", _ALL_SPECIES)
@pytest.mark.parametrize("settlement_class", sorted(KNOWN_SETTLEMENT_CLASSES))
def test_engine_reproduces_settlement_threat_score(species, settlement_class):
    for d in _DISTANCES:
        result = score_species_stress(species, {"settlements": FeatureProximity(d, settlement_class)})
        assert result.breakdown["settlements"].value == pytest.approx(settlement_threat_score(d, settlement_class, species)), f"{species} settlements/{settlement_class}@{d}m"


@pytest.mark.parametrize("species", _ALL_SPECIES)
def test_engine_reproduces_water_stress_score(species):
    for d in _DISTANCES:
        result = score_species_stress(species, {"water": FeatureProximity(d, None)})
        assert result.breakdown["water"].value == pytest.approx(water_stress_score(d, species)), f"{species} water@{d}m"


# ---------------------------------------------------------------------------
# Aggregate + breakdown + coverage behavior
# ---------------------------------------------------------------------------


def test_result_has_aggregate_and_full_breakdown():
    result = score_species_stress(
        "Hyperolius marmoratus",
        {"roads": FeatureProximity(100, "motorway"), "settlements": FeatureProximity(100, "city"), "water": FeatureProximity(500, None)},
    )
    assert isinstance(result, StressResult)
    assert set(result.breakdown) == {"water", "roads", "settlements"}
    assert result.aggregate.covered is True


def test_missing_measurement_makes_that_stressor_uncovered_not_zero():
    # Only roads measured; water & settlements have no data at this location.
    result = score_species_stress("Panthera leo", {"roads": FeatureProximity(0, "motorway")})
    assert result.breakdown["water"] == Score(None, False)
    assert result.breakdown["settlements"] == Score(None, False)
    assert result.breakdown["roads"].covered is True


def test_aggregate_is_noisy_or_of_covered_breakdown():
    result = score_species_stress(
        "Hyperolius marmoratus",
        {"roads": FeatureProximity(0, "motorway"), "settlements": FeatureProximity(0, "city")},
    )
    r = result.breakdown["roads"].value
    s = result.breakdown["settlements"].value
    expected = 1 - (1 - r) * (1 - s)  # water uncovered -> excluded
    assert result.aggregate.value == pytest.approx(expected)


def test_all_measurements_absent_gives_uncovered_aggregate():
    result = score_species_stress("Panthera leo", {})
    assert result.aggregate == Score(None, False)
