# src/wildlife_water_stress_atlas/config/species.py

"""
species.py

Single source of truth for all species configuration in the atlas.

WHY THIS FILE EXISTS:
---------------------
Species-specific values used to be scattered across multiple modules, so adding a
species meant editing several files — a maintenance hazard. This registry is the
single source of truth: every module that needs species data imports from here.

HOW TO ADD A NEW SPECIES:
--------------------------
Copy config/species_plugins/_template.json to a new JSON file (one per species)
and fill it in — see config/species_plugins/README.md for field docs. The loader
in species_loader.py discovers it automatically, builds SPECIES_CONFIG, and
validates each plugin independently — a malformed one is skipped and logged, not
fatal. No edits to this file or any other are needed.

ENTRY SHAPE (post-cutover):
---------------------------
Each entry has species-level metadata plus a `stressors` list. Stressor params
live ONLY in that list — there are no flat water_*/road_*/settlement_* keys.
Consumers read params via get_stressor_params(species, stressor_id); the scoring
engine reads the list directly.

Top-level metadata:
    scientific_name  : str — the registry key.
    common_name      : str — UI label.
    daily_range_m    : int | float > 0 — typical daily movement range (grid sizing).
    water_dependency : "low" | "moderate" | "high" — qualitative dependence.
    realm            : "terrestrial" | "freshwater" | "marine" — see Realm.
    icon_url         : https:// URL (Mapbox/UI icon).
    icon_static_path : "app/static/..." (Streamlit same-origin icon).
    gbif_cache_file  : "*.gpkg" occurrence cache filename.
    emoji            : str — UI/chart label.
    rationale        : str — ecological justification (provenance).

stressors : list[dict] — one entry per stressor, each:
    stressor_id : "water" | "roads" | "settlements" | ...  (see stressor_plugins)
    sensitivity : float in [0.0, 1.0] — per-species multiplier (0.0 = immune).
    params      : dict — kind-specific:
        water (RESOURCE): threshold_m > 0; accessible_types (non-empty list);
                          type_weights {type: (0.0, 1.0]} keyed by accessible_types.
        roads / settlements (HAZARD): threshold_m > 0; class_weights {class: [0.0, 1.0]}
                          covering KNOWN_ROAD_CLASSES / KNOWN_SETTLEMENT_CLASSES.
All values are heuristic placeholders pending ecological validation.
"""

from enum import Enum
from pathlib import Path

from wildlife_water_stress_atlas.config.species_loader import load_species_plugins

PLUGINS_DIR = Path(__file__).parent / "species_plugins"

# ---------------------------------------------------------------------------
# Road threat model — human pressure layer (Pressure Type 2)
# ---------------------------------------------------------------------------
# The canonical road classes used throughout the threat pipeline. These are
# the normalized OSM highway classes after _link variants and minor footway
# types are folded into their parents (see ingest/threats.OSM_HIGHWAY_MAP).
# Every species' road_class_weights must provide a weight for each of these.
KNOWN_ROAD_CLASSES: set[str] = {
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "track",
    "path",
}


# ---------------------------------------------------------------------------
# Settlement threat model — human pressure layer (Pressure Type 2, settlements)
# ---------------------------------------------------------------------------
# Canonical settlement classes after OSM place tags are normalized (see
# ingest/threats — gis_osm_places fclass values folded into these). Ordered
# by human footprint: city (largest) → hamlet (smallest). Every species'
# settlement_class_weights must provide a weight for each of these.
KNOWN_SETTLEMENT_CLASSES: set[str] = {
    "city",
    "town",
    "village",
    "hamlet",
}


# ---------------------------------------------------------------------------
# Realm — ecological classification
# ---------------------------------------------------------------------------
# Groups species (UI) and — once the generic stressor system lands — gates which
# stressor types a species must supply (a marine species needn't declare road or
# settlement stressors). Unlocks marine/aquatic species without a redesign.
class Realm(Enum):
    TERRESTRIAL = "terrestrial"
    FRESHWATER = "freshwater"
    MARINE = "marine"


VALID_REALMS: set[str] = {r.value for r in Realm}


# ---------------------------------------------------------------------------
# Stressors-list accessors
# ---------------------------------------------------------------------------
# Plugins declare a `stressors` list — the single source of truth for a species'
# stressor parameters (post-cutover; the flat-key bridge is gone). Consumers and
# validation read stressor params through these accessors.


def _find_stressor(entry: dict, stressor_id: str) -> dict | None:
    """Return the stressor dict with this id from an entry's `stressors` list, or None."""
    for s in entry.get("stressors", []):
        if isinstance(s, dict) and s.get("stressor_id") == stressor_id:
            return s
    return None


def get_stressor_params(species: str, stressor_id: str) -> dict:
    """
    Return the params of a species' stressor, read from its `stressors` list.

    Args:
        species     : Scientific name (must be in SPECIES_CONFIG).
        stressor_id : Stressor id, e.g. "water" / "roads" / "settlements".

    Raises:
        KeyError: If the species or the stressor is absent.
    """
    stressor = _find_stressor(SPECIES_CONFIG[species], stressor_id)
    if stressor is None:
        raise KeyError(f"{species} has no {stressor_id!r} stressor")
    return stressor.get("params", {})


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
# These checks run once at import time — if someone adds a malformed species
# entry, the error surfaces immediately rather than causing a silent failure
# deep inside the scoring pipeline at runtime.


def _validate_water_stressor(species: str, entry: dict) -> None:
    """
    Validate the required `water` stressor's params in a species' stressors list.

    params.threshold_m positive; params.accessible_types a non-empty list;
    params.type_weights a dict whose keys exactly match accessible_types with
    values in (0.0, 1.0] (water weights must be > 0 — an accessible type that
    provides no water is a contradiction, unlike a zero-threat road class).
    """
    stressor = _find_stressor(entry, "water")
    if stressor is None:
        raise ValueError(f"{species}: missing 'water' stressor")

    params = stressor.get("params", {})

    threshold = params.get("threshold_m")
    if not isinstance(threshold, (int, float)) or threshold <= 0:
        raise ValueError(f"{species}: water threshold_m must be a positive number")

    types = params.get("accessible_types")
    if not isinstance(types, (list, tuple, set)) or not types:
        raise ValueError(f"{species}: water accessible_types must be a non-empty list")

    weights = params.get("type_weights")
    if not isinstance(weights, dict) or set(weights.keys()) != set(types):
        raise ValueError(f"{species}: water type_weights keys must exactly match accessible_types. Got {set(weights.keys()) if isinstance(weights, dict) else type(weights)} vs {set(types)}")

    for water_type, weight in weights.items():
        if not isinstance(weight, (int, float)) or not (0.0 < weight <= 1.0):
            raise ValueError(f"{species}/{water_type}: type_weight must be a number between 0 (exclusive) and 1 (inclusive)")


def _validate_proximity_stressor(species: str, entry: dict, stressor_id: str, known_classes: set[str]) -> None:
    """
    Validate a feature-proximity stressor (roads, settlements) in the stressors list.

    Both share the same shape: `sensitivity` in [0,1], params.`threshold_m`
    positive, and params.`class_weights` covering exactly `known_classes` with
    values in [0,1] (0.0 allowed — e.g. a footpath poses no threat to a frog,
    unlike water weights which must be > 0).

    This preserves the import-time guard against the "unvalidated fields" class of
    bug (docs/TDD_CONTRACT.md), now reading from the stressors list rather than
    the retired flat keys.
    """
    stressor = _find_stressor(entry, stressor_id)
    if stressor is None:
        raise ValueError(f"{species}: missing '{stressor_id}' stressor")

    sensitivity = stressor.get("sensitivity")
    if not isinstance(sensitivity, (int, float)) or not (0.0 <= sensitivity <= 1.0):
        raise ValueError(f"{species}: {stressor_id} sensitivity must be a number in [0.0, 1.0]")

    params = stressor.get("params", {})

    threshold = params.get("threshold_m")
    if not isinstance(threshold, (int, float)) or threshold <= 0:
        raise ValueError(f"{species}: {stressor_id} threshold_m must be a positive number")

    weights = params.get("class_weights")
    if not isinstance(weights, dict) or set(weights.keys()) != set(known_classes):
        raise ValueError(f"{species}: {stressor_id} class_weights keys must exactly cover {known_classes}, got {set(weights.keys()) if isinstance(weights, dict) else type(weights)}")

    for cls, weight in weights.items():
        if not isinstance(weight, (int, float)) or not (0.0 <= weight <= 1.0):
            raise ValueError(f"{species}: {stressor_id} class_weights value for '{cls}' must be a number in [0.0, 1.0]")


def _validate_species_config(config: dict[str, dict]) -> None:
    """
    Validate the structure and constraints of SPECIES_CONFIG at import time.

    Raises:
        ValueError: If any species entry is missing required keys, has
                    wrong types, or violates field constraints.
    """
    required_keys = {
        "scientific_name",
        "common_name",
        "stressors",
        "daily_range_m",
        "water_dependency",
        "icon_url",
    }
    valid_dependency_values = {"low", "moderate", "high"}

    for species, cfg in config.items():
        # Every required key must be present
        missing = required_keys - cfg.keys()
        if missing:
            raise ValueError(f"{species} is missing required keys: {missing}")

        # stressors must be a list (the single source of truth for stressor params)
        if not isinstance(cfg["stressors"], list):
            raise ValueError(f"{species}: stressors must be a list")

        # daily_range_m must be a positive number
        if not isinstance(cfg["daily_range_m"], (int, float)) or cfg["daily_range_m"] <= 0:
            raise ValueError(f"{species}: daily_range_m must be a positive number")

        # water_dependency must be one of the allowed values
        if cfg["water_dependency"] not in valid_dependency_values:
            raise ValueError(f"{species}: water_dependency must be one of {valid_dependency_values}, got '{cfg['water_dependency']}'")

        # icon_url must be a non-empty string starting with https://
        if not isinstance(cfg["icon_url"], str) or not cfg["icon_url"].startswith("https://"):
            raise ValueError(f"{species}: icon_url must be a valid https:// URL")

        # icon_static_path must point to Streamlit's static folder —
        # same-origin serving avoids CORS issues with PyDeck IconLayer.
        if not isinstance(cfg["icon_static_path"], str) or not cfg["icon_static_path"].startswith("app/static/"):
            raise ValueError(f"{species}: icon_static_path must start with 'app/static/'")

        # gbif_cache_file must be a .gpkg filename — GeoPackage is the
        # standard cache format throughout the pipeline.
        if not isinstance(cfg["gbif_cache_file"], str) or not cfg["gbif_cache_file"].endswith(".gpkg"):
            raise ValueError(f"{species}: gbif_cache_file must be a .gpkg filename")

        # emoji must be a string — used in UI labels and chart headers.
        if not isinstance(cfg["emoji"], str):
            raise ValueError(f"{species}: emoji must be a string")

        # realm — ecological classification (gates stressor applicability in
        # future; groups species in the UI).
        if cfg.get("realm") not in VALID_REALMS:
            raise ValueError(f"{species}: realm must be one of {VALID_REALMS}, got {cfg.get('realm')!r}")

        # Stressor params (the single source of truth). Water is required;
        # roads/settlements share the sensitivity/threshold/class_weights shape.
        _validate_water_stressor(species, cfg)
        _validate_proximity_stressor(species, cfg, "roads", KNOWN_ROAD_CLASSES)
        _validate_proximity_stressor(species, cfg, "settlements", KNOWN_SETTLEMENT_CLASSES)


# Build the registry from per-species plugin files (JSON) under species_plugins/.
# Each plugin is validated independently; a malformed one is skipped and logged
# (see species_loader), not fatal. Adding a species = adding one JSON file.
#
# The `stressors` list is the single source of truth for stressor params — no
# flattening to legacy keys (the bridge was retired at the scoring cutover).
# Consumers read stressor params via get_stressor_params(); the engine reads the
# list directly.
SPECIES_CONFIG = load_species_plugins(
    PLUGINS_DIR,
    validate=lambda entry: _validate_species_config({entry["scientific_name"]: entry}),
)
