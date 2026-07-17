"""
test_scoring.py

After the full-unify cutover, scoring.py keeps only classify_stress_level (a
score→risk-category helper, still used by the export scripts). The scoring math
itself (water_stress_score / road_threat_score / settlement_threat_score) now
lives solely in the engine; its exact reproduction of the original formulas is
guarded by test_stress_engine.py / test_stressor_types.py against the frozen
tests/_scoring_oracle.py.
"""

from wildlife_water_stress_atlas.analytics.scoring import classify_stress_level


def test_classify_stress_level_returns_high_for_scores_at_or_above_0_8():
    assert classify_stress_level(0.8) == "high"
    assert classify_stress_level(1.0) == "high"


def test_classify_stress_level_returns_moderate_for_mid_range():
    assert classify_stress_level(0.4) == "moderate"
    assert classify_stress_level(0.5) == "moderate"


def test_classify_stress_level_returns_low_for_small_values():
    assert classify_stress_level(0.0) == "low"
    assert classify_stress_level(0.1) == "low"
