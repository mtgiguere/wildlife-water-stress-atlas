"""
scoring.py

Simple scoring functions for estimating environmental risk.

This module intentionally starts with a simple, explainable model.
The goal is to provide a baseline that works end-to-end and can be
improved over time as better ecological assumptions and datasets are added.
"""

# -----------------------------------------------------------------------------
# MODEL PARAMETERS
# -----------------------------------------------------------------------------

# Species-specific maximum distance (in meters) used to normalize water stress.
#
# Why use a mapping?
# - Different species have different relationships to water
# - This lets the model evolve from a single-species heuristic into a
#   multi-species scoring system
# - Thresholds can be revised later as we incorporate better ecological evidence
#
# Current values are placeholders for initial development and visualization.
SPECIES_WATER_THRESHOLDS = {
    "Loxodonta africana": 300_000,
}


# -----------------------------------------------------------------------------
# SCORING FUNCTIONS
# -----------------------------------------------------------------------------

def water_stress_score(distance_meters: float, species: str) -> float:
    """
    Convert distance to nearest water source into a normalized stress score.

    Args:
        distance_meters: Distance from the nearest mapped water source (meters)
        species: Scientific name of the species being scored

    Returns:
        float: Value between 0 and 1
            0.0 -> no stress (very close to water)
            1.0 -> high stress (very far from water)

    Model:
        score = min(distance / species_threshold, 1.0)

    Notes:
        - Thresholds are currently heuristic placeholders
        - This structure makes it easy to support multiple species later
        - Future versions may use species-specific and nonlinear models
    """
    max_distance = SPECIES_WATER_THRESHOLDS[species]
    score = min(distance_meters / max_distance, 1.0)

    return score

def classify_stress_level(score: float) -> str:
    """
    Classify a normalized water stress score into a simple risk category.

    Args:
        score: Normalized stress score between 0 and 1.

    Returns:
        "low", "moderate", or "high"
    """
    if score >= 0.8:
        return "high"
    if score >= 0.4:
        return "moderate"
    return "low"