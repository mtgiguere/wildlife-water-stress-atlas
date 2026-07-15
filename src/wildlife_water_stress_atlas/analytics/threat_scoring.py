"""
threat_scoring.py

Scoring functions for human threat proximity.

SCORING CONTRACT:
-----------------
    score = road_sensitivity * road_class_weight * (1 - distance_m / road_threshold_m)
    clamped to [0.0, 1.0], 0.0 when distance >= road_threshold_m

The three-factor structure mirrors water_stress_score:
    - road_sensitivity       : per-species multiplier (0.0 = immune, short-circuits)
    - road_class_weight      : per-species per-class severity (0.0–1.0)
    - proximity factor       : linear decay from 1.0 at distance 0 to 0.0 at threshold

settlement_threat_score is the second human-pressure layer and uses the same
three-factor structure with settlement_* config fields (see below).
"""

from wildlife_water_stress_atlas.config.species import (
    KNOWN_ROAD_CLASSES,
    KNOWN_SETTLEMENT_CLASSES,
    SPECIES_CONFIG,
)


def road_threat_score(distance_m: float, road_class: str, species: str) -> float:
    """
    Score the road threat to a species at a given distance from a road.

    Args:
        distance_m  : Distance from the nearest road of this class (meters).
        road_class  : OSM highway tag value. Must be in KNOWN_ROAD_CLASSES.
        species     : Scientific name. Must exist in SPECIES_CONFIG.

    Returns:
        float in [0.0, 1.0].
            0.0 → no threat (beyond threshold, immune species, or zero-weight class)
            1.0 → maximum possible threat for this species/class combination

    Raises:
        KeyError: If species is not in SPECIES_CONFIG.
        KeyError: If road_class is not in KNOWN_ROAD_CLASSES.
    """
    if road_class not in KNOWN_ROAD_CLASSES:
        raise KeyError(f"Unknown road class: '{road_class}'. Must be one of {KNOWN_ROAD_CLASSES}")

    cfg = SPECIES_CONFIG[species]  # raises KeyError for unknown species

    sensitivity = cfg["road_sensitivity"]
    if sensitivity == 0.0:
        return 0.0

    threshold = cfg["road_threshold_m"]
    if distance_m >= threshold:
        return 0.0

    class_weight = cfg["road_class_weights"][road_class]
    proximity = 1.0 - (distance_m / threshold)

    return sensitivity * class_weight * proximity


def settlement_threat_score(distance_m: float, settlement_class: str, species: str) -> float:
    """
    Score the settlement threat to a species at a given distance from a settlement.

    Structurally identical to road_threat_score, using the settlement_* config
    fields. This is the second human-pressure layer (Pressure Type 2, settlements).

    Args:
        distance_m       : Distance from the nearest settlement of this class (meters).
        settlement_class : Normalized place class. Must be in KNOWN_SETTLEMENT_CLASSES.
        species          : Scientific name. Must exist in SPECIES_CONFIG.

    Returns:
        float in [0.0, 1.0].
            0.0 → no threat (beyond threshold, immune species, or zero-weight class)
            1.0 → maximum possible threat for this species/class combination

    Raises:
        KeyError: If species is not in SPECIES_CONFIG.
        KeyError: If settlement_class is not in KNOWN_SETTLEMENT_CLASSES.
    """
    if settlement_class not in KNOWN_SETTLEMENT_CLASSES:
        raise KeyError(f"Unknown settlement class: '{settlement_class}'. Must be one of {KNOWN_SETTLEMENT_CLASSES}")

    cfg = SPECIES_CONFIG[species]  # raises KeyError for unknown species

    sensitivity = cfg["settlement_sensitivity"]
    if sensitivity == 0.0:
        return 0.0

    threshold = cfg["settlement_threshold_m"]
    if distance_m >= threshold:
        return 0.0

    class_weight = cfg["settlement_class_weights"][settlement_class]
    proximity = 1.0 - (distance_m / threshold)

    return sensitivity * class_weight * proximity
