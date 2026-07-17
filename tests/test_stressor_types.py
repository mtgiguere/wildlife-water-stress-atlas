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
