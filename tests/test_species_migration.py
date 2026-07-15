"""
test_species_migration.py

Golden regression guard for the species-plugin migration (BACKLOG Phase A).

`SPECIES_CONFIG` is now assembled by the loader from one plugin file per
species. This asserts that assembly deep-equals a frozen snapshot of the
pre-migration monolithic config — so the migration provably changed structure
without changing a single value. If a species value ever changes intentionally,
regenerate tests/_species_config_snapshot.py in the same commit.
"""

from tests._species_config_snapshot import SNAPSHOT
from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG

_ADDITIVE_KEYS = {"rationale", "realm"}  # new metadata, not pre-migration scoring data


def test_registry_data_deep_equals_frozen_snapshot():
    """Every scoring-relevant value is byte-identical to the pre-migration
    config. `rationale` (ecological reasoning promoted from comments) and `realm`
    (new classification) are additive metadata, excluded from the comparison."""
    stripped = {name: {k: v for k, v in entry.items() if k not in _ADDITIVE_KEYS} for name, entry in SPECIES_CONFIG.items()}
    assert stripped == SNAPSHOT


def test_all_eleven_species_loaded():
    assert len(SPECIES_CONFIG) == 11


def test_each_entry_scientific_name_matches_its_key():
    for name, entry in SPECIES_CONFIG.items():
        assert entry["scientific_name"] == name


def test_every_species_carries_its_ecological_rationale():
    """The rationale that lived in code comments must survive as data — nothing
    lost in the JSON migration."""
    for name, entry in SPECIES_CONFIG.items():
        assert entry.get("rationale", "").strip(), f"{name} lost its rationale in migration"
