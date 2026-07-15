"""
test_stressors_list_config.py

Phase C1: plugins move from flat fields to a `stressors` list (source of truth).
`_flatten_stressors` derives the legacy flat keys from that list so existing
consumers (scoring / water_access / threat_scoring / exports) keep working
unchanged while we migrate them onto the engine over later increments.

This tests the flatten bridge in isolation, then the assembled SPECIES_CONFIG.
"""

from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG, _flatten_stressors


def _entry_with_stressors() -> dict:
    return {
        "scientific_name": "Test species",
        "realm": "terrestrial",
        "stressors": [
            {"stressor_id": "water", "sensitivity": 1.0, "params": {"threshold_m": 300000, "accessible_types": ["river", "lake"], "type_weights": {"river": 1.0, "lake": 0.8}}},
            {"stressor_id": "roads", "sensitivity": 0.3, "params": {"threshold_m": 5000, "class_weights": {"motorway": 1.0}}},
            {"stressor_id": "settlements", "sensitivity": 0.5, "params": {"threshold_m": 10000, "class_weights": {"city": 1.0}}},
        ],
    }


# ---------------------------------------------------------------------------
# _flatten_stressors — derives legacy flat keys from the stressors list
# ---------------------------------------------------------------------------


def test_flatten_derives_water_flat_keys():
    out = _flatten_stressors(_entry_with_stressors())
    assert out["water_threshold_m"] == 300000
    assert out["accessible_water_types"] == ["river", "lake"]
    assert out["water_type_weights"] == {"river": 1.0, "lake": 0.8}


def test_flatten_derives_road_flat_keys():
    out = _flatten_stressors(_entry_with_stressors())
    assert out["road_sensitivity"] == 0.3
    assert out["road_threshold_m"] == 5000
    assert out["road_class_weights"] == {"motorway": 1.0}


def test_flatten_derives_settlement_flat_keys():
    out = _flatten_stressors(_entry_with_stressors())
    assert out["settlement_sensitivity"] == 0.5
    assert out["settlement_threshold_m"] == 10000
    assert out["settlement_class_weights"] == {"city": 1.0}


def test_flatten_preserves_the_stressors_list_and_metadata():
    out = _flatten_stressors(_entry_with_stressors())
    assert "stressors" in out
    assert out["scientific_name"] == "Test species"
    assert out["realm"] == "terrestrial"


# ---------------------------------------------------------------------------
# Assembled SPECIES_CONFIG — stressors list present AND flat keys still work
# ---------------------------------------------------------------------------


def test_all_species_have_a_stressors_list():
    for species, cfg in SPECIES_CONFIG.items():
        assert isinstance(cfg.get("stressors"), list) and cfg["stressors"], f"{species} missing stressors list"
        ids = {s["stressor_id"] for s in cfg["stressors"]}
        assert ids == {"water", "roads", "settlements"}, f"{species} stressor ids: {ids}"


def test_legacy_flat_keys_still_present_via_bridge():
    # Elephant's flat values must survive the restructure (consumers read these).
    elephant = SPECIES_CONFIG["Loxodonta africana"]
    assert elephant["water_threshold_m"] == 300_000
    assert elephant["road_sensitivity"] == 0.3
    assert elephant["settlement_sensitivity"] == 0.5
    assert elephant["accessible_water_types"] == {"river", "lake", "pan", "wetland", "floodplain", "surface_water", "saline_lake", "permanent_water"}
