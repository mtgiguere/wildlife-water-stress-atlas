from wildlife_water_stress_atlas.analytics.scoring import water_stress_score


def test_water_stress_score_zero_distance():
    assert water_stress_score(0, "Loxodonta africana") == 0


def test_water_stress_score_mid_range():
    assert 0 < water_stress_score(150_000, "Loxodonta africana") < 1


def test_water_stress_score_caps_at_one():
    assert water_stress_score(500_000, "Loxodonta africana") == 1.0

def test_classify_stress_level_returns_high_for_scores_at_or_above_0_8():
    from wildlife_water_stress_atlas.analytics.scoring import classify_stress_level

    assert classify_stress_level(0.8) == "high"
    assert classify_stress_level(1.0) == "high"

def test_classify_stress_level_returns_moderate_for_mid_range():
    from wildlife_water_stress_atlas.analytics.scoring import classify_stress_level

    assert classify_stress_level(0.5) == "moderate"


def test_classify_stress_level_returns_low_for_small_values():
    from wildlife_water_stress_atlas.analytics.scoring import classify_stress_level

    assert classify_stress_level(0.1) == "low"