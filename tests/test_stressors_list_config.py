"""
test_stressors_list_config.py

The `stressors` list is the single source of truth for a species' stressor
params (post-cutover — the flatten-to-legacy-keys bridge is retired). Every
species declares water/roads/settlements stressors, and consumers read their
params via config.species.get_stressor_params.
"""

from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG, get_stressor_params


def test_all_species_have_the_expected_stressors_list():
    for species, cfg in SPECIES_CONFIG.items():
        assert isinstance(cfg.get("stressors"), list) and cfg["stressors"], f"{species} missing stressors list"
        ids = {s["stressor_id"] for s in cfg["stressors"]}
        assert ids == {"water", "roads", "settlements"}, f"{species} stressor ids: {ids}"


def test_no_legacy_flat_keys_remain():
    # The bridge is gone: stressor params live ONLY in the stressors list.
    elephant = SPECIES_CONFIG["Loxodonta africana"]
    for dead_key in ("water_threshold_m", "road_sensitivity", "settlement_sensitivity", "accessible_water_types", "water_type_weights"):
        assert dead_key not in elephant, f"stale flat key {dead_key!r} still present"


def test_stressor_params_read_via_accessor():
    # Elephant's params must be reachable through the accessor consumers use.
    water = get_stressor_params("Loxodonta africana", "water")
    assert water["threshold_m"] == 300_000
    assert set(water["accessible_types"]) == {"river", "lake", "pan", "wetland", "floodplain", "surface_water", "saline_lake", "permanent_water"}

    roads = get_stressor_params("Loxodonta africana", "roads")
    assert roads["threshold_m"] > 0 and isinstance(roads["class_weights"], dict)
