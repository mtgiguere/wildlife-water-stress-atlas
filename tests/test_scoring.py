from wildlife_water_stress_atlas.analytics.scoring import water_stress_score
from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG

_ELEPHANT = "Loxodonta africana"
_THRESHOLD = SPECIES_CONFIG[_ELEPHANT]["water_threshold_m"]


def test_water_stress_score_zero_distance():
    assert water_stress_score(0, _ELEPHANT) == 0


def test_water_stress_score_linear_scaling():
    """At half the threshold, score is exactly 0.5 — verifies linear relationship."""
    assert water_stress_score(_THRESHOLD / 2, _ELEPHANT) == 0.5


def test_water_stress_score_at_exact_threshold_is_one():
    """At exactly the threshold distance, score is 1.0."""
    assert water_stress_score(_THRESHOLD, _ELEPHANT) == 1.0


def test_water_stress_score_caps_at_one():
    """Any distance beyond the threshold is capped at 1.0, not allowed to exceed it."""
    assert water_stress_score(_THRESHOLD * 2, _ELEPHANT) == 1.0


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
        water_stress_score(100_000, "Unicornus fantasticus")
