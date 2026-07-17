"""
scoring.py

Score → risk-category classification.

WHY THIS FILE IS SMALL:
-----------------------
The scoring MATH (water/road/settlement) used to live here and in
threat_scoring.py. After the full-unify cutover it lives solely in the kind-aware
engine (analytics/stressors.py + stress_engine.py) — one scoring truth. What
remains here is classify_stress_level, a presentation helper that buckets an
already-computed 0–1 score into a risk label; it carries no scoring math and no
species config, so it stayed while water_stress_score was removed.
"""


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
