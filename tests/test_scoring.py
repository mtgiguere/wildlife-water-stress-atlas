from wildlife_water_stress_atlas.analytics.scoring import water_stress_score


def test_water_stress_score_zero_distance():
    assert water_stress_score(0, "Loxodonta africana") == 0


def test_water_stress_score_mid_range():
    assert 0 < water_stress_score(150_000, "Loxodonta africana") < 1


def test_water_stress_score_caps_at_one():
    assert water_stress_score(500_000, "Loxodonta africana") == 1.0

    