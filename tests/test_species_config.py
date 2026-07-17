import pytest

from wildlife_water_stress_atlas.config.species import (
    KNOWN_ROAD_CLASSES,
    KNOWN_SETTLEMENT_CLASSES,
    SPECIES_CONFIG,
    _validate_species_config,
    get_stressor_params,
)

# ---------------------------------------------------------------------------
# Registry structure
# ---------------------------------------------------------------------------


def test_species_config_contains_african_elephant():
    assert "Loxodonta africana" in SPECIES_CONFIG


def test_all_species_have_required_keys():
    required_keys = {
        "scientific_name",
        "common_name",
        "stressors",
        "daily_range_m",
        "water_dependency",
    }
    for species, config in SPECIES_CONFIG.items():
        missing = required_keys - config.keys()
        assert not missing, f"{species} is missing keys: {missing}"


# ---------------------------------------------------------------------------
# Water stressor params (the stressors list is the source of truth)
# ---------------------------------------------------------------------------


def test_water_threshold_m_is_positive_number():
    for species in SPECIES_CONFIG:
        threshold = get_stressor_params(species, "water")["threshold_m"]
        assert isinstance(threshold, (int, float)), f"{species}: water threshold_m must be int or float"
        assert threshold > 0, f"{species}: water threshold_m must be positive"


def test_accessible_types_is_nonempty():
    for species in SPECIES_CONFIG:
        types = get_stressor_params(species, "water")["accessible_types"]
        assert len(types) > 0, f"{species}: water accessible_types must not be empty"


def test_type_weights_keys_match_accessible_types():
    for species in SPECIES_CONFIG:
        params = get_stressor_params(species, "water")
        assert set(params["type_weights"].keys()) == set(params["accessible_types"]), f"{species}: type_weights keys must match accessible_types"


def test_type_weights_are_numbers_between_0_and_1():
    for species in SPECIES_CONFIG:
        for water_type, weight in get_stressor_params(species, "water")["type_weights"].items():
            assert isinstance(weight, (int, float)), f"{species}/{water_type}: weight must be a number"
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


def test_elephant_water_threshold_is_correct():
    assert get_stressor_params("Loxodonta africana", "water")["threshold_m"] == 300_000


def test_elephant_accessible_types_are_correct():
    assert set(get_stressor_params("Loxodonta africana", "water")["accessible_types"]) == {"river", "lake", "pan", "wetland", "floodplain", "surface_water", "saline_lake", "permanent_water"}


def test_elephant_type_weights_are_correct():
    weights = get_stressor_params("Loxodonta africana", "water")["type_weights"]
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
# Validation — a complete valid entry, then one bad field per negative test
# ---------------------------------------------------------------------------


def _valid_entry() -> dict:
    """A complete, valid single-species entry (stressors-list shape) — the base
    for negative tests so each isolates exactly one bad field regardless of the
    validation check order."""
    return {
        "scientific_name": "Fake species",
        "common_name": "Faker",
        "daily_range_m": 50_000,
        "water_dependency": "high",
        "icon_url": "https://example.com/icon.png",
        "icon_static_path": "app/static/fake.png",
        "gbif_cache_file": "gbif_fake.gpkg",
        "emoji": "🦁",
        "realm": "terrestrial",
        "stressors": [
            {"stressor_id": "water", "sensitivity": 1.0, "params": {"threshold_m": 100_000, "accessible_types": ["river"], "type_weights": {"river": 1.0}}},
            {"stressor_id": "roads", "sensitivity": 0.5, "params": {"threshold_m": 5_000, "class_weights": {c: 0.5 for c in KNOWN_ROAD_CLASSES}}},
            {"stressor_id": "settlements", "sensitivity": 0.5, "params": {"threshold_m": 5_000, "class_weights": {c: 0.5 for c in KNOWN_SETTLEMENT_CLASSES}}},
        ],
    }


def _stressor(entry: dict, stressor_id: str) -> dict:
    return next(s for s in entry["stressors"] if s["stressor_id"] == stressor_id)


def test_valid_full_entry_passes_validation():
    _validate_species_config({"Fake species": _valid_entry()})  # must not raise


def test_missing_required_key_raises_value_error():
    entry = _valid_entry()
    del entry["daily_range_m"]
    with pytest.raises(ValueError, match="missing required keys"):
        _validate_species_config({"Fake species": entry})


def test_stressors_not_a_list_raises_value_error():
    with pytest.raises(ValueError, match="stressors must be a list"):
        _validate_species_config({"Fake species": {**_valid_entry(), "stressors": {"not": "a list"}}})


# --- water stressor ---


def test_missing_water_stressor_raises_value_error():
    entry = _valid_entry()
    entry["stressors"] = [s for s in entry["stressors"] if s["stressor_id"] != "water"]
    with pytest.raises(ValueError, match="water"):
        _validate_species_config({"Fake species": entry})


def test_invalid_water_threshold_raises_value_error():
    entry = _valid_entry()
    _stressor(entry, "water")["params"]["threshold_m"] = -1
    with pytest.raises(ValueError, match="threshold_m"):
        _validate_species_config({"Fake species": entry})


def test_empty_accessible_types_raises_value_error():
    entry = _valid_entry()
    _stressor(entry, "water")["params"]["accessible_types"] = []
    _stressor(entry, "water")["params"]["type_weights"] = {}
    with pytest.raises(ValueError, match="accessible_types"):
        _validate_species_config({"Fake species": entry})


def test_mismatched_type_weight_keys_raises_value_error():
    entry = _valid_entry()
    _stressor(entry, "water")["params"]["accessible_types"] = ["river", "lake"]
    _stressor(entry, "water")["params"]["type_weights"] = {"river": 1.0}  # missing "lake"
    with pytest.raises(ValueError, match="type_weights keys"):
        _validate_species_config({"Fake species": entry})


def test_invalid_type_weight_value_raises_value_error():
    entry = _valid_entry()
    _stressor(entry, "water")["params"]["type_weights"] = {"river": 1.5}  # > 1.0
    with pytest.raises(ValueError, match="type_weight"):
        _validate_species_config({"Fake species": entry})


# --- other top-level fields ---


def test_invalid_daily_range_raises_value_error():
    with pytest.raises(ValueError, match="daily_range_m"):
        _validate_species_config({"Fake species": {**_valid_entry(), "daily_range_m": 0}})


def test_invalid_water_dependency_raises_value_error():
    with pytest.raises(ValueError, match="water_dependency"):
        _validate_species_config({"Fake species": {**_valid_entry(), "water_dependency": "extreme"}})


def test_invalid_icon_url_raises_value_error():
    with pytest.raises(ValueError, match="icon_url"):
        _validate_species_config({"Fake species": {**_valid_entry(), "icon_url": "not-a-valid-url"}})


def test_invalid_icon_static_path_raises_value_error():
    with pytest.raises(ValueError, match="icon_static_path"):
        _validate_species_config({"Fake species": {**_valid_entry(), "icon_static_path": "not/a/valid/path.png"}})


def test_invalid_gbif_cache_file_raises_value_error():
    with pytest.raises(ValueError, match="gbif_cache_file"):
        _validate_species_config({"Fake species": {**_valid_entry(), "gbif_cache_file": "not_a_gpkg_file.csv"}})


def test_invalid_emoji_raises_value_error():
    with pytest.raises(ValueError, match="emoji"):
        _validate_species_config({"Fake species": {**_valid_entry(), "emoji": 123}})


# ---------------------------------------------------------------------------
# Registry membership & per-species metadata
# ---------------------------------------------------------------------------


def test_all_species_have_icon_url():
    for species, config in SPECIES_CONFIG.items():
        assert isinstance(config["icon_url"], str) and config["icon_url"].startswith("https://"), f"{species}: icon_url must be a valid URL"


def test_elephant_icon_url_is_twemoji_elephant():
    assert SPECIES_CONFIG["Loxodonta africana"]["icon_url"] == "https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/1f418.png"


def test_all_species_have_icon_static_path():
    for species, config in SPECIES_CONFIG.items():
        assert config["icon_static_path"].startswith("app/static/"), f"{species}: icon_static_path must start with 'app/static/'"


def test_all_species_have_gbif_cache_file():
    for species, config in SPECIES_CONFIG.items():
        assert config["gbif_cache_file"].endswith(".gpkg"), f"{species}: gbif_cache_file must end with .gpkg"


def test_all_species_have_emoji():
    for species, config in SPECIES_CONFIG.items():
        assert isinstance(config["emoji"], str), f"{species}: emoji must be a string"


@pytest.mark.parametrize(
    "scientific_name",
    [
        "Equus quagga",
        "Giraffa camelopardalis",
        "Panthera leo",
        "Acinonyx jubatus",
        "Crocodylus niloticus",
        "Phoenicopterus roseus",
        "Hyperolius marmoratus",
        "Xenopus laevis",
        "Hippopotamus amphibius",
        "Syncerus caffer",
    ],
)
def test_species_config_contains_species(scientific_name):
    assert scientific_name in SPECIES_CONFIG


def test_hippo_water_threshold_is_tight():
    # Hippos seldom move more than 3km from water — 15km is a generous
    # upper bound that accounts for drought-driven dispersal movements.
    assert get_stressor_params("Hippopotamus amphibius", "water")["threshold_m"] == 15_000


def test_hippo_water_dependency_is_high():
    assert SPECIES_CONFIG["Hippopotamus amphibius"]["water_dependency"] == "high"


def test_hippo_accessible_types_are_correct():
    assert set(get_stressor_params("Hippopotamus amphibius", "water")["accessible_types"]) == {"river", "lake", "wetland", "floodplain", "permanent_water"}


def test_buffalo_water_threshold_is_correct():
    # Buffalo drink daily and contract their range sharply around
    # permanent water in dry season — 100km reflects dry-season max.
    assert get_stressor_params("Syncerus caffer", "water")["threshold_m"] == 100_000


def test_buffalo_accessible_types_are_correct():
    assert set(get_stressor_params("Syncerus caffer", "water")["accessible_types"]) == {"river", "lake", "pan", "wetland", "floodplain", "surface_water", "permanent_water"}


# ---------------------------------------------------------------------------
# Realm — species classification that (in future) gates which stressors apply
# ---------------------------------------------------------------------------


def test_all_species_have_a_valid_realm():
    valid = {"terrestrial", "freshwater", "marine"}
    for species, cfg in SPECIES_CONFIG.items():
        assert cfg.get("realm") in valid, f"{species}: realm must be one of {valid}, got {cfg.get('realm')!r}"


def test_missing_realm_raises_value_error():
    entry = _valid_entry()
    del entry["realm"]
    with pytest.raises(ValueError, match="realm"):
        _validate_species_config({"Fake species": entry})


def test_invalid_realm_raises_value_error():
    with pytest.raises(ValueError, match="realm"):
        _validate_species_config({"Fake species": {**_valid_entry(), "realm": "atmospheric"}})


# ---------------------------------------------------------------------------
# Road & settlement stressor validation (from the stressors list)
# ---------------------------------------------------------------------------


def test_all_species_have_road_and_settlement_stressors():
    for species, cfg in SPECIES_CONFIG.items():
        ids = {s["stressor_id"] for s in cfg["stressors"]}
        assert {"roads", "settlements"} <= ids, f"{species} missing road/settlement stressors: {ids}"


def test_missing_roads_stressor_raises_value_error():
    entry = _valid_entry()
    entry["stressors"] = [s for s in entry["stressors"] if s["stressor_id"] != "roads"]
    with pytest.raises(ValueError, match="roads"):
        _validate_species_config({"Fake species": entry})


def test_road_sensitivity_out_of_range_raises_value_error():
    entry = _valid_entry()
    _stressor(entry, "roads")["sensitivity"] = 1.5
    with pytest.raises(ValueError, match="sensitivity"):
        _validate_species_config({"Fake species": entry})


def test_road_threshold_not_positive_raises_value_error():
    entry = _valid_entry()
    _stressor(entry, "roads")["params"]["threshold_m"] = 0
    with pytest.raises(ValueError, match="threshold_m"):
        _validate_species_config({"Fake species": entry})


def test_road_class_weights_missing_class_raises_value_error():
    entry = _valid_entry()
    weights = _stressor(entry, "roads")["params"]["class_weights"]
    weights.pop(next(iter(weights)))  # drop one required class
    with pytest.raises(ValueError, match="class_weights"):
        _validate_species_config({"Fake species": entry})


def test_road_class_weight_out_of_range_raises_value_error():
    entry = _valid_entry()
    weights = _stressor(entry, "roads")["params"]["class_weights"]
    weights[next(iter(weights))] = 2.0
    with pytest.raises(ValueError, match="class_weights"):
        _validate_species_config({"Fake species": entry})


def test_road_class_weight_zero_is_allowed():
    """A 0.0 class weight is valid (e.g. a footpath poses no threat to a frog) —
    unlike water weights, which must be > 0."""
    entry = _valid_entry()
    _stressor(entry, "roads")["params"]["class_weights"]["path"] = 0.0
    _validate_species_config({"Fake species": entry})  # must not raise


def test_settlement_sensitivity_out_of_range_raises_value_error():
    entry = _valid_entry()
    _stressor(entry, "settlements")["sensitivity"] = -0.1
    with pytest.raises(ValueError, match="sensitivity"):
        _validate_species_config({"Fake species": entry})


def test_settlement_class_weights_missing_class_raises_value_error():
    entry = _valid_entry()
    weights = _stressor(entry, "settlements")["params"]["class_weights"]
    weights.pop(next(iter(weights)))
    with pytest.raises(ValueError, match="class_weights"):
        _validate_species_config({"Fake species": entry})


# ---------------------------------------------------------------------------
# Boundary / edge cases surfaced by a mutation audit — each pins a bound that a
# passing suite previously left un-nailed (e.g. `<= 0` vs `== 0`, strict `> 0`
# for water, exact key-set match vs subset).
# ---------------------------------------------------------------------------


def test_water_threshold_of_exactly_zero_raises_value_error():
    entry = _valid_entry()
    _stressor(entry, "water")["params"]["threshold_m"] = 0
    with pytest.raises(ValueError, match="threshold_m"):
        _validate_species_config({"Fake species": entry})


def test_water_type_weight_of_exactly_zero_raises_value_error():
    # Water weights must be strictly > 0 (an accessible type that provides no
    # water is a contradiction) — unlike road/settlement class weights, where 0 is
    # allowed. This pins that distinction.
    entry = _valid_entry()
    _stressor(entry, "water")["params"]["type_weights"] = {"river": 0.0}
    with pytest.raises(ValueError, match="type_weight"):
        _validate_species_config({"Fake species": entry})


def test_water_type_weights_extra_key_raises_value_error():
    # An extra key (superset of accessible_types) must be rejected, not just a
    # missing one.
    entry = _valid_entry()
    _stressor(entry, "water")["params"]["type_weights"]["lake"] = 0.5
    with pytest.raises(ValueError, match="type_weights keys"):
        _validate_species_config({"Fake species": entry})


def test_negative_proximity_threshold_raises_value_error():
    entry = _valid_entry()
    _stressor(entry, "roads")["params"]["threshold_m"] = -1
    with pytest.raises(ValueError, match="threshold_m"):
        _validate_species_config({"Fake species": entry})


def test_proximity_class_weights_extra_key_raises_value_error():
    entry = _valid_entry()
    _stressor(entry, "roads")["params"]["class_weights"]["not_a_real_class"] = 0.5
    with pytest.raises(ValueError, match="class_weights"):
        _validate_species_config({"Fake species": entry})


def test_negative_daily_range_raises_value_error():
    with pytest.raises(ValueError, match="daily_range_m"):
        _validate_species_config({"Fake species": {**_valid_entry(), "daily_range_m": -1}})


def test_get_stressor_params_unknown_stressor_raises_key_error():
    with pytest.raises(KeyError):
        get_stressor_params("Loxodonta africana", "not_a_stressor")
