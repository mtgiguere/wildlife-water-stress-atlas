import pytest

from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG, _validate_species_config

# ---------------------------------------------------------------------------
# Registry structure
# ---------------------------------------------------------------------------


def test_species_config_contains_african_elephant():
    assert "Loxodonta africana" in SPECIES_CONFIG


def test_all_species_have_required_keys():
    required_keys = {
        "water_threshold_m",
        "accessible_water_types",
        "water_type_weights",
        "daily_range_m",
        "water_dependency",
    }
    for species, config in SPECIES_CONFIG.items():
        missing = required_keys - config.keys()
        assert not missing, f"{species} is missing keys: {missing}"


# ---------------------------------------------------------------------------
# Field types and constraints
# ---------------------------------------------------------------------------


def test_water_threshold_m_is_positive_number():
    for species, config in SPECIES_CONFIG.items():
        assert isinstance(config["water_threshold_m"], (int, float)), f"{species}: water_threshold_m must be int or float"
        assert config["water_threshold_m"] > 0, f"{species}: water_threshold_m must be positive"


def test_accessible_water_types_is_nonempty_set():
    for species, config in SPECIES_CONFIG.items():
        assert isinstance(config["accessible_water_types"], set), f"{species}: accessible_water_types must be a set"
        assert len(config["accessible_water_types"]) > 0, f"{species}: accessible_water_types must not be empty"


def test_water_type_weights_keys_match_accessible_water_types():
    for species, config in SPECIES_CONFIG.items():
        assert config["water_type_weights"].keys() == config["accessible_water_types"], f"{species}: water_type_weights keys must match accessible_water_types"


def test_water_type_weights_are_floats_between_0_and_1():
    for species, config in SPECIES_CONFIG.items():
        for water_type, weight in config["water_type_weights"].items():
            assert isinstance(weight, float), f"{species}/{water_type}: weight must be a float"
            assert 0.0 < weight <= 1.0, f"{species}/{water_type}: weight must be between 0 (exclusive) and 1 (inclusive)"


def test_daily_range_m_is_positive_number():
    for species, config in SPECIES_CONFIG.items():
        assert isinstance(config["daily_range_m"], (int, float)), f"{species}: daily_range_m must be int or float"
        assert config["daily_range_m"] > 0, f"{species}: daily_range_m must be positive"


def test_water_dependency_is_valid_string():
    valid_values = {"low", "moderate", "high"}
    for species, config in SPECIES_CONFIG.items():
        assert config["water_dependency"] in valid_values, f"{species}: water_dependency must be one of {valid_values}"


# ---------------------------------------------------------------------------
# African elephant specific values
# ---------------------------------------------------------------------------


def test_elephant_water_threshold_matches_existing_scoring_module():
    assert SPECIES_CONFIG["Loxodonta africana"]["water_threshold_m"] == 300_000


def test_elephant_accessible_water_types_are_correct():
    assert SPECIES_CONFIG["Loxodonta africana"]["accessible_water_types"] == {"river", "lake", "pan", "wetland", "floodplain", "surface_water", "saline_lake", "permanent_water"}


def test_elephant_water_type_weights_are_correct():
    weights = SPECIES_CONFIG["Loxodonta africana"]["water_type_weights"]
    assert weights["river"] == 1.0
    assert weights["lake"] == 1.0
    assert weights["pan"] == 0.4
    assert weights["wetland"] == 0.7
    assert weights["floodplain"] == 0.7
    assert weights["surface_water"] == 0.6
    assert weights["saline_lake"] == 0.4
    assert weights["permanent_water"] == 0.8


# ---------------------------------------------------------------------------
# Unknown species
# ---------------------------------------------------------------------------


def test_unknown_species_raises_key_error():
    with pytest.raises(KeyError):
        _ = SPECIES_CONFIG["Unicornus fantasticus"]


# ---------------------------------------------------------------------------
# Validation — malformed entries should raise at import time
# ---------------------------------------------------------------------------


def test_missing_required_key_raises_value_error():

    bad_config = {
        "Fake species": {
            # water_threshold_m is missing
            "accessible_water_types": {"river"},
            "water_type_weights": {"river": 1.0},
            "daily_range_m": 50_000,
            "water_dependency": "high",
            "icon_url": "https://example.com/icon.png",
        }
    }
    with pytest.raises(ValueError, match="missing required keys"):
        _validate_species_config(bad_config)


def test_invalid_water_threshold_raises_value_error():

    bad_config = {
        "Fake species": {
            "water_threshold_m": -1,  # negative — invalid
            "accessible_water_types": {"river"},
            "water_type_weights": {"river": 1.0},
            "daily_range_m": 50_000,
            "water_dependency": "high",
            "icon_url": "https://example.com/icon.png",
        }
    }
    with pytest.raises(ValueError, match="water_threshold_m"):
        _validate_species_config(bad_config)


def test_empty_accessible_water_types_raises_value_error():

    bad_config = {
        "Fake species": {
            "water_threshold_m": 100_000,
            "accessible_water_types": set(),  # empty — invalid
            "water_type_weights": {},
            "daily_range_m": 50_000,
            "water_dependency": "high",
            "icon_url": "https://example.com/icon.png",
        }
    }
    with pytest.raises(ValueError, match="accessible_water_types"):
        _validate_species_config(bad_config)


def test_mismatched_weight_keys_raises_value_error():

    bad_config = {
        "Fake species": {
            "water_threshold_m": 100_000,
            "accessible_water_types": {"river", "lake"},
            "water_type_weights": {"river": 1.0},  # missing "lake" — invalid
            "daily_range_m": 50_000,
            "water_dependency": "high",
            "icon_url": "https://example.com/icon.png",
        }
    }
    with pytest.raises(ValueError, match="water_type_weights keys"):
        _validate_species_config(bad_config)


def test_invalid_weight_value_raises_value_error():

    bad_config = {
        "Fake species": {
            "water_threshold_m": 100_000,
            "accessible_water_types": {"river"},
            "water_type_weights": {"river": 1.5},  # > 1.0 — invalid
            "daily_range_m": 50_000,
            "water_dependency": "high",
            "icon_url": "https://example.com/icon.png",
        }
    }
    with pytest.raises(ValueError, match="weight must be a float"):
        _validate_species_config(bad_config)


def test_invalid_daily_range_raises_value_error():

    bad_config = {
        "Fake species": {
            "water_threshold_m": 100_000,
            "accessible_water_types": {"river"},
            "water_type_weights": {"river": 1.0},
            "daily_range_m": 0,  # zero — invalid
            "water_dependency": "high",
            "icon_url": "https://example.com/icon.png",
        }
    }
    with pytest.raises(ValueError, match="daily_range_m"):
        _validate_species_config(bad_config)


def test_invalid_water_dependency_raises_value_error():

    bad_config = {
        "Fake species": {
            "water_threshold_m": 100_000,
            "accessible_water_types": {"river"},
            "water_type_weights": {"river": 1.0},
            "daily_range_m": 50_000,
            "water_dependency": "extreme",  # not in {"low", "moderate", "high"}
            "icon_url": "https://example.com/icon.png",
        }
    }
    with pytest.raises(ValueError, match="water_dependency"):
        _validate_species_config(bad_config)


def test_all_species_have_icon_url():
    for species, config in SPECIES_CONFIG.items():
        assert "icon_url" in config, f"{species} is missing icon_url"
        assert isinstance(config["icon_url"], str), f"{species}: icon_url must be a string"
        assert config["icon_url"].startswith("https://"), f"{species}: icon_url must be a valid URL"


def test_elephant_icon_url_is_twemoji_elephant():
    assert SPECIES_CONFIG["Loxodonta africana"]["icon_url"] == "https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/1f418.png"


def test_invalid_icon_url_raises_value_error():

    bad_config = {
        "Fake species": {
            "water_threshold_m": 100_000,
            "accessible_water_types": {"river"},
            "water_type_weights": {"river": 1.0},
            "daily_range_m": 50_000,
            "water_dependency": "high",
            "icon_url": "not-a-valid-url",  # missing https:// — invalid
        }
    }
    with pytest.raises(ValueError, match="icon_url"):
        _validate_species_config(bad_config)


def test_species_config_contains_plains_zebra():
    assert "Equus quagga" in SPECIES_CONFIG


def test_all_species_have_icon_static_path():
    for species, config in SPECIES_CONFIG.items():
        assert "icon_static_path" in config, f"{species} is missing icon_static_path"
        assert config["icon_static_path"].startswith("app/static/"), f"{species}: icon_static_path must start with 'app/static/'"


def test_all_species_have_gbif_cache_file():
    for species, config in SPECIES_CONFIG.items():
        assert "gbif_cache_file" in config, f"{species} is missing gbif_cache_file"
        assert config["gbif_cache_file"].endswith(".gpkg"), f"{species}: gbif_cache_file must end with .gpkg"


def test_all_species_have_emoji():
    for species, config in SPECIES_CONFIG.items():
        assert "emoji" in config, f"{species} is missing emoji"
        assert isinstance(config["emoji"], str), f"{species}: emoji must be a string"


def test_invalid_icon_static_path_raises_value_error():
    bad_config = {
        "Fake species": {
            "water_threshold_m": 100_000,
            "accessible_water_types": {"river"},
            "water_type_weights": {"river": 1.0},
            "daily_range_m": 50_000,
            "water_dependency": "high",
            "icon_url": "https://example.com/icon.png",
            "icon_static_path": "not/a/valid/path.png",  # missing app/static/ prefix
            "gbif_cache_file": "gbif_fake.gpkg",
            "emoji": "🦁",
        }
    }
    with pytest.raises(ValueError, match="icon_static_path"):
        _validate_species_config(bad_config)


def test_invalid_gbif_cache_file_raises_value_error():
    bad_config = {
        "Fake species": {
            "water_threshold_m": 100_000,
            "accessible_water_types": {"river"},
            "water_type_weights": {"river": 1.0},
            "daily_range_m": 50_000,
            "water_dependency": "high",
            "icon_url": "https://example.com/icon.png",
            "icon_static_path": "app/static/fake.png",
            "gbif_cache_file": "not_a_gpkg_file.csv",  # wrong extension
            "emoji": "🦁",
        }
    }
    with pytest.raises(ValueError, match="gbif_cache_file"):
        _validate_species_config(bad_config)


def test_invalid_emoji_raises_value_error():
    bad_config = {
        "Fake species": {
            "water_threshold_m": 100_000,
            "accessible_water_types": {"river"},
            "water_type_weights": {"river": 1.0},
            "daily_range_m": 50_000,
            "water_dependency": "high",
            "icon_url": "https://example.com/icon.png",
            "icon_static_path": "app/static/fake.png",
            "gbif_cache_file": "gbif_fake.gpkg",
            "emoji": 123,  # not a string
        }
    }
    with pytest.raises(ValueError, match="emoji"):
        _validate_species_config(bad_config)


def test_species_config_contains_giraffe():
    assert "Giraffa camelopardalis" in SPECIES_CONFIG


def test_species_config_contains_lion():
    assert "Panthera leo" in SPECIES_CONFIG


def test_species_config_contains_cheetah():
    assert "Acinonyx jubatus" in SPECIES_CONFIG


def test_species_config_contains_nile_crocodile():
    assert "Crocodylus niloticus" in SPECIES_CONFIG


def test_species_config_contains_greater_flamingo():
    assert "Phoenicopterus roseus" in SPECIES_CONFIG


def test_species_config_contains_painted_reed_frog():
    assert "Hyperolius marmoratus" in SPECIES_CONFIG


def test_species_config_contains_african_clawed_frog():
    assert "Xenopus laevis" in SPECIES_CONFIG


def test_species_config_contains_hippopotamus():
    assert "Hippopotamus amphibius" in SPECIES_CONFIG


def test_species_config_contains_african_buffalo():
    assert "Syncerus caffer" in SPECIES_CONFIG


def test_hippo_water_threshold_is_tight():
    # Hippos seldom move more than 3km from water — 15km is a generous
    # upper bound that accounts for drought-driven dispersal movements.
    assert SPECIES_CONFIG["Hippopotamus amphibius"]["water_threshold_m"] == 15_000


def test_hippo_water_dependency_is_high():
    assert SPECIES_CONFIG["Hippopotamus amphibius"]["water_dependency"] == "high"


def test_hippo_accessible_water_types_are_correct():
    assert SPECIES_CONFIG["Hippopotamus amphibius"]["accessible_water_types"] == {"river", "lake", "wetland", "floodplain", "permanent_water"}


def test_hippo_water_type_weights_are_correct():
    weights = SPECIES_CONFIG["Hippopotamus amphibius"]["water_type_weights"]
    assert weights["river"] == 1.0
    assert weights["lake"] == 1.0
    assert weights["wetland"] == 0.8
    assert weights["floodplain"] == 0.9
    assert weights["permanent_water"] == 1.0


def test_buffalo_water_threshold_is_correct():
    # Buffalo drink daily and contract their range sharply around
    # permanent water in dry season — 100km reflects dry-season max.
    assert SPECIES_CONFIG["Syncerus caffer"]["water_threshold_m"] == 100_000


def test_buffalo_water_dependency_is_high():
    assert SPECIES_CONFIG["Syncerus caffer"]["water_dependency"] == "high"


def test_buffalo_accessible_water_types_are_correct():
    assert SPECIES_CONFIG["Syncerus caffer"]["accessible_water_types"] == {"river", "lake", "pan", "wetland", "floodplain", "surface_water", "permanent_water"}


def test_buffalo_water_type_weights_are_correct():
    weights = SPECIES_CONFIG["Syncerus caffer"]["water_type_weights"]
    assert weights["river"] == 1.0
    assert weights["lake"] == 1.0
    assert weights["pan"] == 0.5
    assert weights["wetland"] == 0.7
    assert weights["floodplain"] == 0.9
    assert weights["surface_water"] == 0.6
    assert weights["permanent_water"] == 0.9
