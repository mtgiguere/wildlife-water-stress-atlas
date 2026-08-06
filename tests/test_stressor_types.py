"""
test_stressor_types.py

Tests for the stressor-KIND contract (docs/ARCHITECTURE.md §4–§5):

    StressorKind      — HAZARD (closer=worse) / RESOURCE (closer=better) / AMBIENT (no distance)
    Measurement       — FeatureProximity(distance, class) / FieldSample(value)
    StressorConfig    — the expert-set sensitivity + params for one species×stressor
    StressorType.score(measurement, cfg) -> Score

The reference types must REPRODUCE today's scoring exactly (the golden guard in
B4 depends on this): a hazard reproduces road_threat_score, a resource
reproduces water_stress_score. Ambient proves the contract carries a non-distance
stressor with no distance/decay assumption.
"""

import pytest

from tests._scoring_oracle import road_threat_score, water_stress_score
from wildlife_water_stress_atlas.analytics.stress_engine import species_stressors
from wildlife_water_stress_atlas.analytics.stressors import (
    AmbientStressor,
    FeatureProximity,
    FieldSample,
    HazardStressor,
    ResourceStressor,
    Score,
    StressorConfig,
    StressorKind,
)

_FROG = "Hyperolius marmoratus"
_ELEPHANT = "Loxodonta africana"


def _stressor_cfg(species: str, stressor_id: str) -> StressorConfig:
    """The species' StressorConfig for one stressor, built from its stressors
    list by the engine's own builder (the post-cutout single source of truth)."""
    return next(c for c in species_stressors(species) if c.stressor_id == stressor_id)


def _road_cfg(species: str) -> StressorConfig:
    return _stressor_cfg(species, "roads")


def _water_cfg(species: str) -> StressorConfig:
    # Water is a RESOURCE with sensitivity 1.0 — reproduces the original
    # min(d/threshold, 1.0) formula.
    return _stressor_cfg(species, "water")


# ---------------------------------------------------------------------------
# Kinds
# ---------------------------------------------------------------------------


def test_kinds_exist():
    assert {StressorKind.HAZARD, StressorKind.RESOURCE, StressorKind.AMBIENT}


def test_reference_types_declare_their_kind():
    assert HazardStressor().kind is StressorKind.HAZARD
    assert ResourceStressor().kind is StressorKind.RESOURCE
    assert AmbientStressor().kind is StressorKind.AMBIENT


# ---------------------------------------------------------------------------
# HAZARD — closer = worse (roads, settlements)
# ---------------------------------------------------------------------------


def test_hazard_at_zero_distance_is_sensitivity_times_class_weight():
    cfg = _road_cfg(_FROG)
    expected = cfg.sensitivity * cfg.params["class_weights"]["motorway"]
    assert HazardStressor().score(FeatureProximity(0, "motorway"), cfg).value == pytest.approx(expected)


def test_hazard_decreases_with_distance():
    cfg = _road_cfg(_FROG)
    near = HazardStressor().score(FeatureProximity(100, "motorway"), cfg).value
    far = HazardStressor().score(FeatureProximity(500, "motorway"), cfg).value
    assert near > far


def test_hazard_at_or_beyond_threshold_is_zero_but_covered():
    cfg = _road_cfg(_FROG)
    result = HazardStressor().score(FeatureProximity(cfg.params["threshold_m"], "motorway"), cfg)
    assert result == Score(0.0, True)


def test_hazard_immune_species_scores_zero_covered():
    cfg = StressorConfig("roads", sensitivity=0.0, params={"threshold_m": 1000, "class_weights": {"motorway": 1.0}})
    assert HazardStressor().score(FeatureProximity(0, "motorway"), cfg) == Score(0.0, True)


def test_hazard_no_measurement_is_uncovered():
    assert HazardStressor().score(None, _road_cfg(_FROG)) == Score(None, False)


@pytest.mark.parametrize("distance", [0, 100, 500, 1000, 5000, 50_000])
@pytest.mark.parametrize("road_class", ["motorway", "primary", "track", "path"])
def test_hazard_reproduces_road_threat_score(distance, road_class):
    """The generic HAZARD stressor must match the legacy road_threat_score
    exactly for the frog across distances and classes."""
    cfg = _road_cfg(_FROG)
    generic = HazardStressor().score(FeatureProximity(distance, road_class), cfg).value
    legacy = road_threat_score(distance, road_class, _FROG)
    assert generic == pytest.approx(legacy)


# ---------------------------------------------------------------------------
# RESOURCE — closer = better (water); stress rises with distance
# ---------------------------------------------------------------------------


def test_resource_increases_with_distance():
    cfg = _water_cfg(_ELEPHANT)
    near = ResourceStressor().score(FeatureProximity(1_000, None), cfg).value
    far = ResourceStressor().score(FeatureProximity(100_000, None), cfg).value
    assert far > near


def test_resource_saturates_at_threshold():
    cfg = _water_cfg(_ELEPHANT)  # sensitivity 1.0
    thr = cfg.params["threshold_m"]
    assert ResourceStressor().score(FeatureProximity(thr, None), cfg).value == pytest.approx(1.0)


def test_resource_no_measurement_is_uncovered():
    assert ResourceStressor().score(None, _water_cfg(_ELEPHANT)) == Score(None, False)


@pytest.mark.parametrize("distance", [0, 1_000, 50_000, 150_000, 300_000, 600_000])
def test_resource_reproduces_water_stress_score(distance):
    """The generic RESOURCE stressor (sensitivity 1.0) must match the legacy
    water_stress_score exactly for the elephant across distances."""
    cfg = _water_cfg(_ELEPHANT)
    generic = ResourceStressor().score(FeatureProximity(distance, None), cfg).value
    legacy = water_stress_score(distance, _ELEPHANT)
    assert generic == pytest.approx(legacy)


# ---------------------------------------------------------------------------
# AMBIENT — always present, NO distance (climate, air pollution, salinity)
# ---------------------------------------------------------------------------


def test_ambient_scores_from_a_field_sample_not_distance():
    # Linear response over [low, high]; value at/above high -> full stress.
    cfg = StressorConfig("air_pollution", sensitivity=1.0, params={"low": 0.0, "high": 100.0})
    mid = AmbientStressor().score(FieldSample(50.0), cfg).value
    assert mid == pytest.approx(0.5)


def test_ambient_respects_sensitivity():
    cfg = StressorConfig("air_pollution", sensitivity=0.5, params={"low": 0.0, "high": 100.0})
    assert AmbientStressor().score(FieldSample(100.0), cfg).value == pytest.approx(0.5)


def test_ambient_no_measurement_is_uncovered():
    cfg = StressorConfig("air_pollution", sensitivity=1.0, params={"low": 0.0, "high": 100.0})
    assert AmbientStressor().score(None, cfg) == Score(None, False)


def test_ambient_ramp_uses_a_nonzero_low_bound():
    # A non-zero `low` pins the (value - low)/(high - low) formula: with low=0
    # every earlier test can't tell `-` from `+` (0-0 == 0+0). (Mutation-audit gap.)
    cfg = StressorConfig("air_pollution", sensitivity=1.0, params={"low": 10.0, "high": 50.0})
    assert AmbientStressor().score(FieldSample(30.0), cfg).value == pytest.approx(0.5)  # (30-10)/(50-10)
    assert AmbientStressor().score(FieldSample(20.0), cfg).value == pytest.approx(0.25)  # (20-10)/40
    # clamps outside [low, high]
    assert AmbientStressor().score(FieldSample(5.0), cfg).value == pytest.approx(0.0)
    assert AmbientStressor().score(FieldSample(60.0), cfg).value == pytest.approx(1.0)


def test_ambient_with_measurement_is_covered():
    # Pins the covered flag on the scored path (mutation-audit gap: True→None survived).
    cfg = StressorConfig("air_pollution", sensitivity=1.0, params={"low": 10.0, "high": 50.0})
    assert AmbientStressor().score(FieldSample(30.0), cfg).covered is True


# ---------------------------------------------------------------------------
# ResourceStressor honours per-type reliability weights
#
# A resource is only worth its dependability. Every species config already
# carries expert `type_weights` (elephant: river 1.0, wetland 0.7, pan 0.4,
# saline_lake 0.4) and species.py validates them against accessible_types —
# but nothing consumed them, so a pan holding water 2 months a year relieved
# exactly as much stress as a permanent river at the same distance.
#
# Formula: stress = sensitivity × (1 − weight × (1 − scarcity)),
#          scarcity = min(distance / threshold, 1).
# weight 1.0 collapses to sensitivity × scarcity — today's behaviour exactly,
# which is why the golden water guards still hold.
# ---------------------------------------------------------------------------


def _resource_cfg(weights=None, sensitivity=1.0, threshold=1000.0):
    params = {"threshold_m": threshold}
    if weights is not None:
        params["type_weights"] = weights
    return StressorConfig(stressor_id="water", sensitivity=sensitivity, params=params)


def test_a_fully_reliable_source_scores_exactly_as_distance_alone():
    """weight 1.0 must be the identity — this is the golden-preserving case."""
    cfg = _resource_cfg({"river": 1.0})

    weighted = ResourceStressor().score(FeatureProximity(400.0, "river"), cfg)
    unweighted = ResourceStressor().score(FeatureProximity(400.0, None), _resource_cfg())

    assert weighted.value == pytest.approx(0.4)
    assert weighted.value == pytest.approx(unweighted.value)


@pytest.mark.parametrize("water_type", ["river", "pan"])
def test_adjacency_scores_zero_whatever_the_source_type(water_type):
    """No floor. Reliability shortens the usable range; it does not tax an
    animal that is standing at the water's edge.

    This is the deliberate choice against `1 − weight × (1 − scarcity)`, which
    would make zero water stress unreachable for 74% of the continental layer
    (class `permanent_water`, weight 0.8).
    """
    cfg = _resource_cfg({"river": 1.0, "pan": 0.4})

    score = ResourceStressor().score(FeatureProximity(0.0, water_type), cfg)

    assert score.value == pytest.approx(0.0)


def test_an_unreliable_source_saturates_at_a_shorter_distance():
    """A weight-0.4 source reaches maximum stress at 40% of the range a fully
    reliable one would — that IS the penalty."""
    cfg = _resource_cfg({"pan": 0.4}, threshold=1000.0)

    just_inside = ResourceStressor().score(FeatureProximity(399.0, "pan"), cfg)
    at_saturation = ResourceStressor().score(FeatureProximity(400.0, "pan"), cfg)

    assert just_inside.value < 1.0
    assert at_saturation.value == pytest.approx(1.0)


def test_a_less_reliable_source_is_never_less_stressful_than_a_better_one():
    """Monotonicity in reliability, at a fixed distance."""
    cfg = _resource_cfg({"river": 1.0, "wetland": 0.7, "pan": 0.4})
    at = lambda c: ResourceStressor().score(FeatureProximity(500.0, c), cfg).value  # noqa: E731

    assert at("river") < at("wetland") < at("pan")


def test_reliability_cannot_push_stress_above_the_maximum():
    """At/beyond the threshold everything is already maximally stressed; a poor
    weight must not exceed sensitivity."""
    cfg = _resource_cfg({"pan": 0.4}, sensitivity=1.0)

    score = ResourceStressor().score(FeatureProximity(50_000.0, "pan"), cfg)

    assert score.value == pytest.approx(1.0)


def test_sensitivity_still_scales_the_weighted_result():
    """sensitivity 0.5, weight 0.4, threshold 1000, distance 200:
    scarcity = 200 / (0.4 × 1000) = 0.5, so the score is 0.5 × 0.5."""
    cfg = _resource_cfg({"pan": 0.4}, sensitivity=0.5, threshold=1000.0)

    score = ResourceStressor().score(FeatureProximity(200.0, "pan"), cfg)

    assert score.value == pytest.approx(0.25)


def test_a_type_with_no_configured_weight_is_scored_unweighted():
    """The water layer is not filtered to accessible_types before scoring, so an
    unlisted type can arrive. Fall back to the unweighted (identity) reading
    rather than crashing or inventing a penalty."""
    cfg = _resource_cfg({"river": 1.0})

    score = ResourceStressor().score(FeatureProximity(400.0, "lagoon"), cfg)

    assert score.value == pytest.approx(0.4)


def test_a_resource_without_configured_weights_is_unchanged():
    """Backward compatibility: type_weights is optional on a resource."""
    score = ResourceStressor().score(FeatureProximity(400.0, "pan"), _resource_cfg())

    assert score.value == pytest.approx(0.4)
