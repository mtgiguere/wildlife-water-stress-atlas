"""
_scoring_oracle.py — FROZEN reference scoring formulas (test-only).

After the full-unify cutover, production has exactly ONE scoring path: the
kind-aware engine (analytics/stressors.py + stress_engine.py). These pure
functions are the immutable reference that engine is held to — the original
water / road / settlement formulas, kept OUT of production so they can never be
imported into real code or drift back into use.

The golden guards in test_stress_engine.py and test_stressor_types.py assert the
engine reproduces THESE exactly, for every species x class x distance. If the
engine's math ever changes, those comparisons fail — a conscious decision, not a
silent drift.

Parameters are read from each species' `stressors` list (the post-cutover config
shape), NOT the retired flat fields — so this oracle has no dependency on the
deleted flatten bridge. The formulas are copied verbatim from the pre-cutover
scoring.water_stress_score / threat_scoring.road_threat_score /
settlement_threat_score.
"""

from wildlife_water_stress_atlas.config.species import (
    KNOWN_ROAD_CLASSES,
    KNOWN_SETTLEMENT_CLASSES,
    SPECIES_CONFIG,
)


def _stressor(species: str, stressor_id: str):
    """Return (sensitivity, params) for one stressor from the species' list."""
    for s in SPECIES_CONFIG[species]["stressors"]:
        if s["stressor_id"] == stressor_id:
            return s["sensitivity"], s["params"]
    raise KeyError(f"{species!r} has no stressor {stressor_id!r}")


def water_stress_score(distance_meters: float, species: str) -> float:
    """Original resource formula: score = min(distance / threshold_m, 1.0)."""
    _sensitivity, params = _stressor(species, "water")
    return min(distance_meters / params["threshold_m"], 1.0)


def _hazard_score(distance_m: float, feature_class: str, species: str, stressor_id: str, known_classes) -> float:
    """Original hazard formula: sensitivity * class_weight * (1 - d/threshold),
    clamped to 0 for immune species / beyond threshold. Shared by road + settlement."""
    if feature_class not in known_classes:
        raise KeyError(f"Unknown {stressor_id} class: '{feature_class}'. Must be one of {known_classes}")

    sensitivity, params = _stressor(species, stressor_id)
    if sensitivity == 0.0:
        return 0.0

    threshold = params["threshold_m"]
    if distance_m >= threshold:
        return 0.0

    class_weight = params["class_weights"][feature_class]
    return sensitivity * class_weight * (1.0 - (distance_m / threshold))


def road_threat_score(distance_m: float, road_class: str, species: str) -> float:
    return _hazard_score(distance_m, road_class, species, "roads", KNOWN_ROAD_CLASSES)


def settlement_threat_score(distance_m: float, settlement_class: str, species: str) -> float:
    return _hazard_score(distance_m, settlement_class, species, "settlements", KNOWN_SETTLEMENT_CLASSES)
