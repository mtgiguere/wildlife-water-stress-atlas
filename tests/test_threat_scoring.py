"""
test_threat_scoring.py

Tests for src/wildlife_water_stress_atlas/analytics/threat_scoring.py

FUNCTION COVERAGE:
------------------
- road_threat_score(distance_m, road_class, species)
    Returns a 0.0–1.0 threat score based on proximity to a road,
    road class severity, and species-specific road sensitivity.

SCORING CONTRACT:
-----------------
    score = road_sensitivity * road_class_weight * (1 - distance_m / road_threshold_m)
    clamped to [0.0, 1.0], 0.0 when distance >= road_threshold_m

    Where:
        road_sensitivity    — per-species [0.0, 1.0]; 0.0 means roads are irrelevant
        road_class_weight   — per-species per-class [0.0, 1.0]
        road_threshold_m    — per-species distance beyond which roads have no effect
"""

import pytest

from wildlife_water_stress_atlas.analytics.threat_scoring import road_threat_score
from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG

_FROG = "Hyperolius marmoratus"
_ELEPHANT = "Loxodonta africana"
_FLAMINGO = "Phoenicopterus roseus"

_FROG_THRESHOLD = SPECIES_CONFIG[_FROG]["road_threshold_m"]
_FROG_SENSITIVITY = SPECIES_CONFIG[_FROG]["road_sensitivity"]
_FROG_MOTORWAY_WEIGHT = SPECIES_CONFIG[_FROG]["road_class_weights"]["motorway"]
_FROG_PATH_WEIGHT = SPECIES_CONFIG[_FROG]["road_class_weights"]["path"]

_ELEPHANT_THRESHOLD = SPECIES_CONFIG[_ELEPHANT]["road_threshold_m"]
_ELEPHANT_SENSITIVITY = SPECIES_CONFIG[_ELEPHANT]["road_sensitivity"]
_ELEPHANT_MOTORWAY_WEIGHT = SPECIES_CONFIG[_ELEPHANT]["road_class_weights"]["motorway"]


# ---------------------------------------------------------------------------
# Boundary conditions
# ---------------------------------------------------------------------------


def test_road_threat_score_at_zero_distance_is_sensitivity_times_class_weight():
    """At distance 0, proximity factor = 1.0, so score = sensitivity * class_weight."""
    expected = _FROG_SENSITIVITY * _FROG_MOTORWAY_WEIGHT
    assert road_threat_score(0, "motorway", _FROG) == pytest.approx(expected)


def test_road_threat_score_at_exact_threshold_is_zero():
    """At exactly the threshold distance, proximity = 0.0, so score = 0.0."""
    assert road_threat_score(_FROG_THRESHOLD, "motorway", _FROG) == 0.0


def test_road_threat_score_beyond_threshold_is_zero():
    """Any distance beyond the threshold returns 0.0 — roads have no effect."""
    assert road_threat_score(_FROG_THRESHOLD * 2, "motorway", _FROG) == 0.0


def test_road_threat_score_well_beyond_threshold_does_not_go_negative():
    """Score must never be negative — clamped to 0.0 floor."""
    assert road_threat_score(_FROG_THRESHOLD * 100, "motorway", _FROG) >= 0.0


# ---------------------------------------------------------------------------
# Linear decay
# ---------------------------------------------------------------------------


def test_road_threat_score_linear_decay_at_half_threshold():
    """At half the threshold, proximity = 0.5, so score = sensitivity * weight * 0.5."""
    expected = _FROG_SENSITIVITY * _FROG_MOTORWAY_WEIGHT * 0.5
    assert road_threat_score(_FROG_THRESHOLD / 2, "motorway", _FROG) == pytest.approx(expected)


def test_road_threat_score_decreases_with_distance():
    """Score at 100m must be greater than score at 200m (monotonically decreasing)."""
    score_near = road_threat_score(100, "motorway", _FROG)
    score_far = road_threat_score(200, "motorway", _FROG)
    assert score_near > score_far


# ---------------------------------------------------------------------------
# Road class scaling
# ---------------------------------------------------------------------------


def test_road_threat_score_scales_by_road_class():
    """Motorway score must exceed secondary road score for a road-sensitive species."""
    motorway = road_threat_score(100, "motorway", _FROG)
    secondary = road_threat_score(100, "secondary", _FROG)
    assert motorway > secondary


def test_road_threat_score_zero_class_weight_returns_zero():
    """A path has weight 0.0 for frogs — score must be 0.0 regardless of distance."""
    assert _FROG_PATH_WEIGHT == 0.0
    assert road_threat_score(0, "path", _FROG) == 0.0


# ---------------------------------------------------------------------------
# Species sensitivity short-circuit
# ---------------------------------------------------------------------------


def test_road_threat_score_zero_for_immune_species_at_any_distance():
    """Flamingos have road_sensitivity=0.0 — score is 0.0 regardless of distance or class."""
    assert road_threat_score(0, "motorway", _FLAMINGO) == 0.0
    assert road_threat_score(1, "motorway", _FLAMINGO) == 0.0
    assert road_threat_score(0, "primary", _FLAMINGO) == 0.0


def test_road_threat_score_frog_higher_than_elephant_same_conditions():
    """Reed frogs are more road-sensitive than elephants at identical conditions."""
    frog_score = road_threat_score(100, "motorway", _FROG)
    elephant_score = road_threat_score(100, "motorway", _ELEPHANT)
    assert frog_score > elephant_score


# ---------------------------------------------------------------------------
# Output bounds
# ---------------------------------------------------------------------------


def test_road_threat_score_is_always_between_0_and_1():
    """Score must always be in [0.0, 1.0] for any valid input."""
    test_cases = [
        (0, "motorway", _FROG),
        (0, "motorway", _ELEPHANT),
        (0, "motorway", _FLAMINGO),
        (_FROG_THRESHOLD / 2, "primary", _FROG),
        (_ELEPHANT_THRESHOLD * 2, "trunk", _ELEPHANT),
    ]
    for distance, road_class, species in test_cases:
        score = road_threat_score(distance, road_class, species)
        assert 0.0 <= score <= 1.0, f"Score {score} out of bounds for ({distance}, {road_class}, {species})"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_road_threat_score_raises_for_unknown_species():
    with pytest.raises(KeyError):
        road_threat_score(100, "motorway", "Unicornus fantasticus")


def test_road_threat_score_raises_for_unknown_road_class():
    with pytest.raises(KeyError):
        road_threat_score(100, "highway", _FROG)
