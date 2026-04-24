"""
scoring.py

Scoring functions for estimating environmental water stress.

WHY THIS FILE CHANGED:
----------------------
Previously this module maintained its own species threshold dict:
    SPECIES_WATER_THRESHOLDS = {"Loxodonta africana": 300_000}

That was the last remaining piece of species configuration living outside
the central registry. It has been removed. water_stress_score() now reads
water_threshold_m directly from SPECIES_CONFIG in config/species.py.

Adding a new species no longer requires touching this file at all —
add one entry to SPECIES_CONFIG and scoring works automatically.
"""

from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG

# -----------------------------------------------------------------------------
# SCORING FUNCTIONS
# -----------------------------------------------------------------------------

def water_stress_score(distance_meters: float, species: str) -> float:
    """
    Convert distance to nearest water source into a normalized stress score.

    Score is computed as:
        score = min(distance_meters / water_threshold_m, 1.0)

    Where water_threshold_m is the species-specific maximum distance beyond
    which stress is considered maximum (1.0). Values are read from the
    central species config registry in config/species.py.

    Args:
        distance_meters : Distance from the nearest mapped water source (meters).
        species         : Scientific name of the species being scored.
                          Must exist in SPECIES_CONFIG.

    Returns:
        float: Value between 0.0 and 1.0.
            0.0 → no stress (at or very close to water)
            1.0 → maximum stress (at or beyond species threshold distance)

    Raises:
        KeyError: If species is not found in SPECIES_CONFIG.

    Notes:
        - Thresholds are currently heuristic placeholders — see project bible
          Section 4 for the full gap acknowledgment.
        - The linear model is intentionally simple. Future versions may use
          nonlinear curves to better reflect real animal behavior near water.
    """
    # Raises KeyError automatically if species is not in SPECIES_CONFIG —
    # consistent with how filter_accessible_water() and get_water_type_weights()
    # handle unknown species
    max_distance = SPECIES_CONFIG[species]["water_threshold_m"]

    return min(distance_meters / max_distance, 1.0)


def classify_stress_level(score: float) -> str:
    """
    Classify a normalized water stress score into a simple risk category.

    Args:
        score: Normalized stress score between 0.0 and 1.0.

    Returns:
        "low"      → score < 0.4
        "moderate" → 0.4 <= score < 0.8
        "high"     → score >= 0.8

    Notes:
        Thresholds are placeholder values chosen for initial visualization.
        They will be revised as ecological validation data becomes available.
    """
    if score >= 0.8:
        return "high"
    if score >= 0.4:
        return "moderate"
    return "low"