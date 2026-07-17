"""
test_score_stressor.py

Cutover (full-unify): `score_stressor` is the single scalar scoring path that
replaces the legacy per-view functions (scoring.water_stress_score,
threat_scoring.road_threat_score / settlement_threat_score). It returns ONE
stressor's stress value for a species at a location — exactly the number the
`apply_*` export helpers used to get from the legacy functions.

These assertions are engine-INTERNAL (score_stressor == the matching entry in
score_species_stress's breakdown), so they survive the deletion of the legacy
modules. The engine⇔legacy equivalence itself is proven by the golden guard in
test_stress_engine.py.
"""

import pytest

from wildlife_water_stress_atlas.analytics.stress_engine import (
    score_species_stress,
    score_stressor,
)
from wildlife_water_stress_atlas.analytics.stressors import FeatureProximity


def _breakdown_value(species, stressor_id, measurement):
    return score_species_stress(species, {stressor_id: measurement}).breakdown[stressor_id].value


@pytest.mark.parametrize(
    "species, stressor_id, measurement",
    [
        ("Panthera leo", "roads", FeatureProximity(0, "motorway")),
        ("Panthera leo", "roads", FeatureProximity(5_000, "primary")),
        ("Loxodonta africana", "settlements", FeatureProximity(0, "city")),
        ("Loxodonta africana", "settlements", FeatureProximity(50_000, "town")),
        ("Hyperolius marmoratus", "water", FeatureProximity(0, None)),
        ("Hyperolius marmoratus", "water", FeatureProximity(300_000, None)),
    ],
)
def test_score_stressor_matches_breakdown_entry(species, stressor_id, measurement):
    assert score_stressor(species, stressor_id, measurement) == _breakdown_value(species, stressor_id, measurement)


def test_score_stressor_scores_only_the_requested_stressor():
    # Passing one measurement must not require the others to be present, and must
    # return that stressor's own value (not the noisy-OR aggregate).
    m = FeatureProximity(0, "motorway")
    value = score_stressor("Panthera leo", "roads", m)
    assert 0.0 <= value <= 1.0
    assert value == score_species_stress("Panthera leo", {"roads": m}).breakdown["roads"].value


def test_score_stressor_unknown_stressor_id_raises():
    with pytest.raises((KeyError, StopIteration)):
        score_stressor("Panthera leo", "not_a_stressor", FeatureProximity(0, "motorway"))
