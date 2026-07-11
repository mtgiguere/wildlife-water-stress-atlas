"""
test_settlement_threat_scoring.py

Tests for settlement_threat_score in
src/wildlife_water_stress_atlas/analytics/threat_scoring.py

The settlement threat layer is the second human-pressure type (after roads),
built on the same three-factor scoring contract:

SCORING CONTRACT:
-----------------
    score = settlement_sensitivity * settlement_class_weight * (1 - distance_m / settlement_threshold_m)
    clamped to [0.0, 1.0], 0.0 when distance >= settlement_threshold_m

    Where:
        settlement_sensitivity   — per-species [0.0, 1.0]; 0.0 means settlements are irrelevant
        settlement_class_weight  — per-species per-class [0.0, 1.0] (city > town > village > hamlet)
        settlement_threshold_m   — per-species distance beyond which settlements have no effect
"""

import pytest

from wildlife_water_stress_atlas.analytics.threat_scoring import settlement_threat_score
from wildlife_water_stress_atlas.config.species import KNOWN_SETTLEMENT_CLASSES, SPECIES_CONFIG

_FROG = "Hyperolius marmoratus"
_ELEPHANT = "Loxodonta africana"
_FLAMINGO = "Phoenicopterus roseus"

_FROG_THRESHOLD = SPECIES_CONFIG[_FROG]["settlement_threshold_m"]
_FROG_SENSITIVITY = SPECIES_CONFIG[_FROG]["settlement_sensitivity"]
_FROG_CITY_WEIGHT = SPECIES_CONFIG[_FROG]["settlement_class_weights"]["city"]


# ---------------------------------------------------------------------------
# Boundary conditions
# ---------------------------------------------------------------------------


def test_settlement_threat_score_at_zero_distance_is_sensitivity_times_class_weight():
    """At distance 0, proximity factor = 1.0, so score = sensitivity * class_weight."""
    expected = _FROG_SENSITIVITY * _FROG_CITY_WEIGHT
    assert settlement_threat_score(0, "city", _FROG) == pytest.approx(expected)


def test_settlement_threat_score_at_exact_threshold_is_zero():
    """At exactly the threshold distance, proximity = 0.0, so score = 0.0."""
    assert settlement_threat_score(_FROG_THRESHOLD, "city", _FROG) == 0.0


def test_settlement_threat_score_beyond_threshold_is_zero():
    """Any distance beyond the threshold returns 0.0 — settlements have no effect."""
    assert settlement_threat_score(_FROG_THRESHOLD * 2, "city", _FROG) == 0.0


def test_settlement_threat_score_well_beyond_threshold_does_not_go_negative():
    """Score must never be negative — clamped to 0.0 floor."""
    assert settlement_threat_score(_FROG_THRESHOLD * 100, "city", _FROG) >= 0.0


# ---------------------------------------------------------------------------
# Linear decay
# ---------------------------------------------------------------------------


def test_settlement_threat_score_linear_decay_at_half_threshold():
    """At half the threshold, proximity = 0.5, so score = sensitivity * weight * 0.5."""
    expected = _FROG_SENSITIVITY * _FROG_CITY_WEIGHT * 0.5
    assert settlement_threat_score(_FROG_THRESHOLD / 2, "city", _FROG) == pytest.approx(expected)


def test_settlement_threat_score_decreases_with_distance():
    """Score nearer a settlement must exceed the score farther away."""
    score_near = settlement_threat_score(100, "city", _FROG)
    score_far = settlement_threat_score(200, "city", _FROG)
    assert score_near > score_far


# ---------------------------------------------------------------------------
# Settlement class scaling
# ---------------------------------------------------------------------------


def test_settlement_threat_score_scales_by_class():
    """A city (large, permanent) must pose more threat than a village at equal distance."""
    city = settlement_threat_score(100, "city", _FROG)
    village = settlement_threat_score(100, "village", _FROG)
    assert city > village


# ---------------------------------------------------------------------------
# Species sensitivity short-circuit
# ---------------------------------------------------------------------------


def test_settlement_threat_score_zero_for_immune_species_at_any_distance():
    """Flamingos are treated as immune to ground-based human pressure (they fly
    between remote saline lakes) — settlement_sensitivity=0.0 short-circuits to 0.0."""
    assert settlement_threat_score(0, "city", _FLAMINGO) == 0.0
    assert settlement_threat_score(1, "city", _FLAMINGO) == 0.0
    assert settlement_threat_score(0, "village", _FLAMINGO) == 0.0


def test_settlement_threat_score_frog_higher_than_elephant_same_conditions():
    """Reed frogs (wetland drainage/pollution) are more settlement-sensitive than
    elephants at identical conditions."""
    frog_score = settlement_threat_score(100, "city", _FROG)
    elephant_score = settlement_threat_score(100, "city", _ELEPHANT)
    assert frog_score > elephant_score


# ---------------------------------------------------------------------------
# Output bounds
# ---------------------------------------------------------------------------


def test_settlement_threat_score_is_always_between_0_and_1():
    """Score must always be in [0.0, 1.0] for any valid input."""
    test_cases = [
        (0, "city", _FROG),
        (0, "city", _ELEPHANT),
        (0, "city", _FLAMINGO),
        (_FROG_THRESHOLD / 2, "town", _FROG),
        (_FROG_THRESHOLD * 2, "hamlet", _ELEPHANT),
    ]
    for distance, settlement_class, species in test_cases:
        score = settlement_threat_score(distance, settlement_class, species)
        assert 0.0 <= score <= 1.0, f"Score {score} out of bounds for ({distance}, {settlement_class}, {species})"


# ---------------------------------------------------------------------------
# Config completeness — every species must score for every known class
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("species", sorted(SPECIES_CONFIG.keys()))
@pytest.mark.parametrize("settlement_class", sorted(KNOWN_SETTLEMENT_CLASSES))
def test_every_species_scores_every_known_settlement_class(species, settlement_class):
    """Guards config drift: each species' settlement_class_weights must cover every
    KNOWN_SETTLEMENT_CLASS, so scoring never raises for a valid class."""
    score = settlement_threat_score(50, settlement_class, species)
    assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_settlement_threat_score_raises_for_unknown_species():
    with pytest.raises(KeyError):
        settlement_threat_score(100, "city", "Unicornus fantasticus")


def test_settlement_threat_score_raises_for_unknown_settlement_class():
    with pytest.raises(KeyError):
        settlement_threat_score(100, "metropolis", _FROG)
