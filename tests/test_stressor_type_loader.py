"""
test_stressor_type_loader.py

Phase C5 — stressor TYPES become plugins (docs/ARCHITECTURE.md §5).

A stressor-type plugin is an inert JSON declaration: {stressor_id, name, kind}.
The KIND (hazard / resource / ambient) supplies the scoring math, so adding a
new stressor type of an existing kind = adding one JSON file, no code. The
loader maps each declaration to its kind's scorer and — like the species
loader — SKIPS + logs a malformed one rather than crashing the whole load.

Tested in isolation against tmp_path plugin files.
"""

import json
from pathlib import Path

import pytest

from wildlife_water_stress_atlas.analytics.stressor_type_loader import load_stressor_types
from wildlife_water_stress_atlas.analytics.stressors import StressorKind


def _write(dir_: Path, filename: str, obj) -> None:
    (dir_ / filename).write_text(json.dumps(obj) if not isinstance(obj, str) else obj, encoding="utf-8")


# ---------------------------------------------------------------------------
# Happy path — declaration → kind's scorer
# ---------------------------------------------------------------------------


def test_loads_types_mapped_to_their_kind_scorer(tmp_path):
    _write(tmp_path, "roads.json", {"stressor_id": "roads", "name": "Roads", "kind": "hazard"})
    _write(tmp_path, "water.json", {"stressor_id": "water", "name": "Water", "kind": "resource"})
    _write(tmp_path, "heat.json", {"stressor_id": "heat", "name": "Heat", "kind": "ambient"})

    reg = load_stressor_types(tmp_path)

    assert set(reg) == {"roads", "water", "heat"}
    assert reg["roads"].kind is StressorKind.HAZARD
    assert reg["water"].kind is StressorKind.RESOURCE
    assert reg["heat"].kind is StressorKind.AMBIENT


def test_scorer_actually_scores(tmp_path):
    # A loaded hazard type must produce a working scorer (proves it's wired, not
    # just a label).
    from wildlife_water_stress_atlas.analytics.stressors import FeatureProximity, StressorConfig

    _write(tmp_path, "roads.json", {"stressor_id": "roads", "name": "Roads", "kind": "hazard"})
    reg = load_stressor_types(tmp_path)

    cfg = StressorConfig("roads", sensitivity=1.0, params={"threshold_m": 1000, "class_weights": {"motorway": 1.0}})
    score = reg["roads"].score(FeatureProximity(0, "motorway"), cfg)
    assert score.value == pytest.approx(1.0)


def test_underscore_prefixed_files_ignored(tmp_path):
    _write(tmp_path, "roads.json", {"stressor_id": "roads", "kind": "hazard"})
    _write(tmp_path, "_template.json", {"stressor_id": "template", "kind": "hazard"})

    assert set(load_stressor_types(tmp_path)) == {"roads"}


# ---------------------------------------------------------------------------
# Malformed plugins are SKIPPED (logged), never crash the load
# ---------------------------------------------------------------------------


def test_unknown_kind_is_skipped(tmp_path, caplog):
    _write(tmp_path, "roads.json", {"stressor_id": "roads", "kind": "hazard"})
    _write(tmp_path, "weird.json", {"stressor_id": "weird", "kind": "quantum"})

    reg = load_stressor_types(tmp_path)

    assert set(reg) == {"roads"}
    assert "weird" in caplog.text.lower()


def test_missing_stressor_id_is_skipped(tmp_path):
    _write(tmp_path, "roads.json", {"stressor_id": "roads", "kind": "hazard"})
    _write(tmp_path, "noid.json", {"kind": "hazard"})

    assert set(load_stressor_types(tmp_path)) == {"roads"}


def test_invalid_json_is_skipped(tmp_path):
    _write(tmp_path, "roads.json", {"stressor_id": "roads", "kind": "hazard"})
    _write(tmp_path, "broken.json", "{ not valid ,,,")

    assert set(load_stressor_types(tmp_path)) == {"roads"}


def test_duplicate_stressor_id_raises(tmp_path):
    _write(tmp_path, "a.json", {"stressor_id": "roads", "kind": "hazard"})
    _write(tmp_path, "b.json", {"stressor_id": "roads", "kind": "resource"})

    with pytest.raises(ValueError, match="[Dd]uplicate"):
        load_stressor_types(tmp_path)


def test_empty_dir_returns_empty(tmp_path):
    assert load_stressor_types(tmp_path) == {}
