# src/wildlife_water_stress_atlas/config/species.py

"""
species.py

Single source of truth for all species configuration in the atlas.

WHY THIS FILE EXISTS:
---------------------
Previously, species-specific values were scattered across multiple modules:
  - analytics/scoring.py       held water_threshold_m
  - analytics/water_access.py  held accessible_water_types and water_type_weights

That meant adding a new species required editing multiple files — a maintenance
hazard and a violation of the core architectural principle:
  "Adding a new species = adding one config entry. Nothing else should change."

This registry fixes that. Every module that needs species data imports from here.

HOW TO ADD A NEW SPECIES:
--------------------------
Copy config/species_plugins/_template.json to a new JSON file (one per species)
and fill it in — see config/species_plugins/README.md for field docs. The loader
in species_loader.py discovers it automatically, builds SPECIES_CONFIG, and
validates each plugin independently — a malformed one is skipped and logged, not
fatal. No edits to this file or any other are needed.

FIELD REFERENCE:
----------------
water_threshold_m       : int | float
    Maximum distance in meters at which the species is considered water-stressed.
    Used to normalize the stress score to a 0–1 range.
    Example: 300_000 means "if an elephant is 300km from water, stress = 1.0"

accessible_water_types  : set[str]
    The water source types this species can actually use.
    Must match the 'type' column values produced by the water ingestion layer.
    Example: {"river", "lake", "pan", "wetland"}

water_type_weights      : dict[str, float]
    Relative reliability/preference weight for each accessible water type.
    Keys MUST exactly match accessible_water_types.
    Values are floats in the range (0.0, 1.0].
    1.0 = fully reliable source, lower = seasonal or less preferred.
    Example: {"river": 1.0, "pan": 0.8} means pans are slightly less reliable.

daily_range_m           : int | float
    Typical maximum daily movement range in meters.
    Used for grid cell sizing and future movement modeling.
    Example: 50_000 (50km is a reasonable upper bound for elephants)

water_dependency        : str — one of "low", "moderate", "high"
    Qualitative descriptor of how tightly this species depends on
    surface water availability. Used for weighting in composite stress
    scores when multiple pressure types are combined in future phases.
road_sensitivity        : float in [0.0, 1.0]
    Per-species multiplier for how strongly roads threaten this species.
    0.0 means roads are irrelevant (e.g. flying species). Higher values
    mean roads (mortality, fragmentation, poaching access) matter more.
    A short-circuit: sensitivity 0.0 makes road_threat_score return 0.0
    regardless of distance or road class.

road_threshold_m        : int | float
    Distance in meters beyond which a road has no measured effect on the
    species. Inside this distance the threat decays linearly to 0.0 at
    the threshold. Mirrors water_threshold_m but for the pressure layer.

road_class_weights      : dict[str, float]
    Per-class severity in [0.0, 1.0]. Keys must cover KNOWN_ROAD_CLASSES.
    Larger/faster roads carry higher weight. A weight of 0.0 means that
    road class poses no threat to this species (e.g. a footpath to a frog).
    All road fields are heuristic placeholders pending ecological validation.

settlement_sensitivity  : float in [0.0, 1.0]
    Per-species multiplier for how strongly human settlements threaten this
    species (habitat conversion, human-wildlife conflict, retaliatory
    killing, disturbance). 0.0 short-circuits settlement_threat_score to 0.0
    regardless of distance or class. Mirrors road_sensitivity for the second
    human-pressure layer (Pressure Type 2, settlements).

settlement_threshold_m  : int | float
    Distance in meters beyond which a settlement has no measured effect on
    the species. Inside this distance the threat decays linearly to 0.0 at
    the threshold. Mirrors road_threshold_m.

settlement_class_weights: dict[str, float]
    Per-class severity in [0.0, 1.0]. Keys must cover KNOWN_SETTLEMENT_CLASSES.
    Larger, more permanent settlements carry higher weight
    (city > town > village > hamlet). All settlement fields are heuristic
    placeholders pending ecological validation.
"""

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
# Validation
# ---------------------------------------------------------------------------
# These checks run once at import time — if someone adds a malformed species
# entry, the error surfaces immediately rather than causing a silent failure
# deep inside the scoring pipeline at runtime.


def _validate_proximity_stressor(species: str, cfg: dict, prefix: str, known_classes: set[str]) -> None:
    """
    Validate a feature-proximity stressor's fields (road, settlement).

    Both share the same shape: `{prefix}_sensitivity` in [0,1],
    `{prefix}_threshold_m` positive, and `{prefix}_class_weights` covering
    exactly `known_classes` with values in [0,1] (0.0 allowed — e.g. a footpath
    poses no threat to a frog, unlike water weights which must be > 0).

    This closes a long-standing gap: road/settlement fields were never validated
    at import (see docs/TDD_CONTRACT.md — the "unvalidated fields" class of bug).
    """
    sens_key, thr_key, cw_key = f"{prefix}_sensitivity", f"{prefix}_threshold_m", f"{prefix}_class_weights"

    for key in (sens_key, thr_key, cw_key):
        if key not in cfg:
            raise ValueError(f"{species}: missing {key}")

    if not isinstance(cfg[sens_key], (int, float)) or not (0.0 <= cfg[sens_key] <= 1.0):
        raise ValueError(f"{species}: {sens_key} must be a number in [0.0, 1.0]")

    if not isinstance(cfg[thr_key], (int, float)) or cfg[thr_key] <= 0:
        raise ValueError(f"{species}: {thr_key} must be a positive number")

    weights = cfg[cw_key]
    if not isinstance(weights, dict) or set(weights.keys()) != set(known_classes):
        raise ValueError(f"{species}: {cw_key} keys must exactly cover {known_classes}, got {set(weights.keys()) if isinstance(weights, dict) else type(weights)}")

    for cls, weight in weights.items():
        if not isinstance(weight, (int, float)) or not (0.0 <= weight <= 1.0):
            raise ValueError(f"{species}: {cw_key} value for '{cls}' must be a number in [0.0, 1.0]")


def _validate_species_config(config: dict[str, dict]) -> None:
    """
    Validate the structure and constraints of SPECIES_CONFIG at import time.

    Raises:
        ValueError: If any species entry is missing required keys, has
                    wrong types, or violates field constraints.
    """
    required_keys = {
        "water_threshold_m",
        "accessible_water_types",
        "water_type_weights",
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

        # water_threshold_m must be a positive number
        if not isinstance(cfg["water_threshold_m"], (int, float)) or cfg["water_threshold_m"] <= 0:
            raise ValueError(f"{species}: water_threshold_m must be a positive number")

        # accessible_water_types must be a non-empty set
        if not isinstance(cfg["accessible_water_types"], set) or not cfg["accessible_water_types"]:
            raise ValueError(f"{species}: accessible_water_types must be a non-empty set")

        # water_type_weights keys must exactly match accessible_water_types
        if cfg["water_type_weights"].keys() != cfg["accessible_water_types"]:
            raise ValueError(f"{species}: water_type_weights keys must exactly match accessible_water_types. Got {set(cfg['water_type_weights'].keys())} vs {cfg['accessible_water_types']}")

        # All weights must be floats in (0.0, 1.0]
        for water_type, weight in cfg["water_type_weights"].items():
            if not isinstance(weight, float) or not (0.0 < weight <= 1.0):
                raise ValueError(f"{species}/{water_type}: weight must be a float between 0 (exclusive) and 1 (inclusive)")

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

        # Human-pressure stressor fields (road, settlement) — previously
        # unvalidated. Both share the sensitivity/threshold/class_weights shape.
        _validate_proximity_stressor(species, cfg, "road", KNOWN_ROAD_CLASSES)
        _validate_proximity_stressor(species, cfg, "settlement", KNOWN_SETTLEMENT_CLASSES)


# Build the registry from per-species plugin files (JSON) under species_plugins/.
# Each plugin is validated independently; a malformed one is skipped and logged
# (see species_loader), not fatal. Adding a species = adding one JSON file.
#
# transform: JSON has no set type, so accessible_water_types arrives as a list —
# coerce it back to a set (the shape the validator and water_access expect).
# This domain-specific coercion lives here, keeping the loader schema-agnostic.
SPECIES_CONFIG = load_species_plugins(
    PLUGINS_DIR,
    validate=lambda entry: _validate_species_config({entry["scientific_name"]: entry}),
    transform=lambda entry: {**entry, "accessible_water_types": set(entry["accessible_water_types"])},
)
