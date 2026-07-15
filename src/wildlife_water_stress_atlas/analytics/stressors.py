"""
stressors.py

The generic stressor scoring core for the extensible atlas
(docs/ARCHITECTURE.md §5–§6). Phase B foundation.

This module will grow to hold the stressor-kind system (hazard / resource /
ambient), the Measurement abstraction, and the StressorType contract. It starts
with the two pieces everything else depends on:

    Score           — a 0..1 stress value that can honestly say "no data"
    aggregate_stress — combine one species' per-stressor Scores into one Score
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum


class StressorKind(Enum):
    """How a stressor relates to distance/space.

    The species-facing contract bakes in NO distance/decay assumption — the
    stressor TYPE owns its own math per kind, so new kinds (and non-distance
    stressors) slot in without a redesign.
    """

    HAZARD = "hazard"  # closer = worse   (roads, settlements, shipping lanes)
    RESOURCE = "resource"  # closer = better  (water)
    AMBIENT = "ambient"  # always present, no distance (climate, air pollution, salinity)


# --- Measurements: what the data layer hands the scorer for one location -----
# General enough to be sampled at an occurrence point OR a grid cell (§7), and
# extensible to a time-series later (§8) without changing the score() contract.


@dataclass(frozen=True)
class FeatureProximity:
    """Distance to the nearest relevant mapped feature (hazard/resource kinds)."""

    distance_m: float
    feature_class: str | None = None


@dataclass(frozen=True)
class FieldSample:
    """A continuous field value sampled at the location (ambient kind)."""

    value: float


@dataclass(frozen=True)
class StressorConfig:
    """The expert-set configuration for one species × one stressor type.

    `sensitivity` is the per-species knob (0.0 = immune, short-circuits).
    `params` are type-specific (validated by the stressor type) — e.g.
    {threshold_m, class_weights} for feature-proximity kinds, {low, high} for a
    linear ambient response. `source`/`validated` carry provenance so an
    expert's numbers can cite their basis (heuristic vs validated).
    """

    stressor_id: str
    sensitivity: float
    params: dict = field(default_factory=dict)
    source: str | None = None
    validated: bool = False


@dataclass(frozen=True)
class Score:
    """A stress score in [0, 1], or "no data".

    value   : float in [0, 1], or None when uncovered.
    covered : False means "no data here" — NEVER silently treated as 0.0 stress
              (docs/ARCHITECTURE.md §6; the project's "data gaps are insights"
              principle). A covered score of 0.0 ("we measured it; no stress")
              is distinct from an uncovered one.
    """

    value: float | None
    covered: bool


def aggregate_stress(scores: Iterable[Score]) -> Score:
    """
    Combine a species' per-stressor Scores into one cumulative stress Score.

    Uses probabilistic union (noisy-OR) over the COVERED scores:

        stress = 1 - ∏ (1 - sᵢ)

    Cumulative, not worst-wins: many small stressors accumulate. Uncovered
    scores are ignored (unknown ≠ zero); if nothing is covered, the result is
    itself uncovered. Bounded to [0, 1], order-independent, and adding a 0.0
    covered score changes nothing.

    Args:
        scores: per-stressor Scores for one location/species.

    Returns:
        Score(value, covered). covered is False (value None) iff no input was
        covered; otherwise value is the noisy-OR over the covered inputs.
    """
    covered_values = [s.value for s in scores if s.covered and s.value is not None]

    if not covered_values:
        return Score(value=None, covered=False)

    product = 1.0
    for v in covered_values:
        product *= 1.0 - v

    return Score(value=1.0 - product, covered=True)


# ---------------------------------------------------------------------------
# Reference stressor types — each owns its own math for its kind
# ---------------------------------------------------------------------------
# These reproduce today's scoring exactly (verified by the golden guard):
#   HAZARD   reproduces road_threat_score / settlement_threat_score
#   RESOURCE reproduces water_stress_score  (with sensitivity 1.0)
# A stressor TYPE turns (Measurement, StressorConfig) into a Score. A None
# measurement means "no data here" → an uncovered Score (never a fake 0.0).


class HazardStressor:
    """Closer = worse. score = sensitivity × class_weight × (1 − dist/threshold),
    clamped to 0 at/beyond the threshold; sensitivity 0.0 short-circuits to 0.0."""

    kind = StressorKind.HAZARD

    def score(self, measurement: FeatureProximity | None, cfg: StressorConfig) -> Score:
        if measurement is None:
            return Score(None, False)

        if cfg.sensitivity == 0.0:
            return Score(0.0, True)

        threshold = cfg.params["threshold_m"]
        if measurement.distance_m >= threshold:
            return Score(0.0, True)

        class_weight = cfg.params["class_weights"][measurement.feature_class]
        proximity = 1.0 - (measurement.distance_m / threshold)
        return Score(cfg.sensitivity * class_weight * proximity, True)


class ResourceStressor:
    """Closer = better (a resource). Stress rises with distance:
    score = sensitivity × min(dist/threshold, 1.0). With sensitivity 1.0 this is
    the legacy water_stress_score."""

    kind = StressorKind.RESOURCE

    def score(self, measurement: FeatureProximity | None, cfg: StressorConfig) -> Score:
        if measurement is None:
            return Score(None, False)

        threshold = cfg.params["threshold_m"]
        scarcity = min(measurement.distance_m / threshold, 1.0)
        return Score(cfg.sensitivity * scarcity, True)


class AmbientStressor:
    """Always present, NO distance. Linear response over [low, high]:
    score = sensitivity × clamp((value − low)/(high − low), 0, 1). Proves the
    contract carries non-distance stressors (climate, air pollution, salinity)
    with no distance/decay assumption."""

    kind = StressorKind.AMBIENT

    def score(self, measurement: FieldSample | None, cfg: StressorConfig) -> Score:
        if measurement is None:
            return Score(None, False)

        low, high = cfg.params["low"], cfg.params["high"]
        ramp = (measurement.value - low) / (high - low)
        ramp = max(0.0, min(ramp, 1.0))
        return Score(cfg.sensitivity * ramp, True)
