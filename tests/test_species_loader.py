"""
test_species_loader.py

Tests for the species plugin loader — the discovery engine behind the
"one file per species" architecture (docs/ARCHITECTURE.md §5, BACKLOG Phase A).

Plugins are JSON files (chosen over Python for safety — inert data, not
executable code — and because JSON is machine-generatable and portable across
the Python pipeline, the JS frontend, and a future backend/DB). Each `*.json`
file IS one species object and includes a "scientific_name". A malformed plugin
must be SKIPPED (logged), never crash the load — one bad file an ecologist adds
can't take down the atlas.

Tested in isolation against tmp_path plugin files — fast and hermetic.
"""

import json
from pathlib import Path

import pytest

from wildlife_water_stress_atlas.config.species_loader import load_species_plugins


def _write(dir_: Path, filename: str, obj) -> None:
    (dir_ / filename).write_text(json.dumps(obj) if not isinstance(obj, str) else obj, encoding="utf-8")


def _species(sci: str, common: str = "Common") -> dict:
    return {"scientific_name": sci, "common_name": common, "value": 1}


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_loads_all_plugins_keyed_by_scientific_name(tmp_path):
    _write(tmp_path, "elephant.json", _species("Loxodonta africana", "Elephant"))
    _write(tmp_path, "zebra.json", _species("Equus quagga", "Zebra"))

    registry = load_species_plugins(tmp_path)

    assert set(registry.keys()) == {"Loxodonta africana", "Equus quagga"}
    assert registry["Loxodonta africana"]["common_name"] == "Elephant"


def test_registry_entry_preserves_plugin_fields(tmp_path):
    _write(tmp_path, "elephant.json", _species("Loxodonta africana"))

    registry = load_species_plugins(tmp_path)

    assert registry["Loxodonta africana"]["value"] == 1
    assert registry["Loxodonta africana"]["scientific_name"] == "Loxodonta africana"


def test_empty_dir_returns_empty_registry(tmp_path):
    assert load_species_plugins(tmp_path) == {}


# ---------------------------------------------------------------------------
# Underscore-prefixed files are ignored (templates, dunders)
# ---------------------------------------------------------------------------


def test_underscore_prefixed_files_are_ignored(tmp_path):
    _write(tmp_path, "elephant.json", _species("Loxodonta africana"))
    _write(tmp_path, "_template.json", _species("Template species"))

    registry = load_species_plugins(tmp_path)

    assert set(registry.keys()) == {"Loxodonta africana"}


def test_non_json_files_are_ignored(tmp_path):
    _write(tmp_path, "elephant.json", _species("Loxodonta africana"))
    _write(tmp_path, "README.md", "# not a plugin")

    registry = load_species_plugins(tmp_path)

    assert set(registry.keys()) == {"Loxodonta africana"}


# ---------------------------------------------------------------------------
# Malformed plugins are SKIPPED (logged), never crash the whole load
# ---------------------------------------------------------------------------


def test_invalid_json_is_skipped(tmp_path, caplog):
    _write(tmp_path, "good.json", _species("Loxodonta africana"))
    _write(tmp_path, "broken.json", "{ this is not valid json ,,, ")

    registry = load_species_plugins(tmp_path)

    assert set(registry.keys()) == {"Loxodonta africana"}
    assert "broken" in caplog.text.lower()


def test_json_that_is_not_an_object_is_skipped(tmp_path):
    _write(tmp_path, "good.json", _species("Loxodonta africana"))
    _write(tmp_path, "list.json", [1, 2, 3])  # a JSON array, not a species object

    registry = load_species_plugins(tmp_path)

    assert set(registry.keys()) == {"Loxodonta africana"}


def test_plugin_missing_scientific_name_is_skipped(tmp_path):
    _write(tmp_path, "good.json", _species("Loxodonta africana"))
    _write(tmp_path, "noname.json", {"common_name": "Nameless"})

    registry = load_species_plugins(tmp_path)

    assert set(registry.keys()) == {"Loxodonta africana"}


def test_plugin_failing_validation_is_skipped_others_kept(tmp_path):
    _write(tmp_path, "good.json", _species("Loxodonta africana"))
    _write(tmp_path, "bad.json", _species("Bad species"))

    def validate(entry: dict) -> None:
        if entry["scientific_name"] == "Bad species":
            raise ValueError("bad config")

    registry = load_species_plugins(tmp_path, validate=validate)

    assert set(registry.keys()) == {"Loxodonta africana"}


def test_valid_plugins_pass_validation(tmp_path):
    _write(tmp_path, "elephant.json", _species("Loxodonta africana"))

    seen = []
    registry = load_species_plugins(tmp_path, validate=lambda e: seen.append(e["scientific_name"]))

    assert seen == ["Loxodonta africana"]
    assert "Loxodonta africana" in registry


def test_duplicate_scientific_name_raises(tmp_path):
    _write(tmp_path, "a.json", _species("Loxodonta africana", "One"))
    _write(tmp_path, "b.json", _species("Loxodonta africana", "Dup"))

    with pytest.raises(ValueError, match="[Dd]uplicate"):
        load_species_plugins(tmp_path)


# ---------------------------------------------------------------------------
# transform hook — domain-specific coercion (e.g. list -> set) before validate
# ---------------------------------------------------------------------------


def test_transform_applied_before_validation_and_storage(tmp_path):
    _write(tmp_path, "e.json", {"scientific_name": "X", "types": ["river", "lake"]})

    seen = {}

    def validate(entry: dict) -> None:
        seen["types_type"] = type(entry["types"])

    registry = load_species_plugins(
        tmp_path,
        validate=validate,
        transform=lambda e: {**e, "types": set(e["types"])},
    )

    assert seen["types_type"] is set  # transform ran before validate
    assert registry["X"]["types"] == {"river", "lake"}
