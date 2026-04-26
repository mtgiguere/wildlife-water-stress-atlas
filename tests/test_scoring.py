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


def test_water_stress_score_reads_from_species_config():
    # Proves water_stress_score() reads water_threshold_m from SPECIES_CONFIG
    # rather than its own hardcoded dict. We temporarily halve the threshold
    # and verify the score doubles for the same distance — if it were reading
    # from a local dict this change would have no effect.
    from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG

    original_threshold = SPECIES_CONFIG["Loxodonta africana"]["water_threshold_m"]

    try:
        SPECIES_CONFIG["Loxodonta africana"]["water_threshold_m"] = 150_000

        score = water_stress_score(150_000, "Loxodonta africana")

        # At the halved threshold, 150_000m should score 1.0
        assert score == 1.0

    finally:
        SPECIES_CONFIG["Loxodonta africana"]["water_threshold_m"] = original_threshold


def test_water_stress_score_raises_for_unknown_species():
    from pytest import raises

    with raises(KeyError):
        water_stress_score(100_000, "Panthera leo")
