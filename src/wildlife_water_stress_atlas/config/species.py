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
Add one entry to SPECIES_CONFIG below. No other file needs to change.
All values are validated at import time by the functions at the bottom of this file.

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
"""

SPECIES_CONFIG: dict[str, dict] = {
    "Loxodonta africana": {
        # ---------------------------------------------------------------
        # African Elephant
        # ---------------------------------------------------------------
        # Elephants are among the most water-dependent large mammals.
        # Adults drink 150–300 litres per day and rarely stray more than
        # ~50km from water in dry conditions, though tracked individuals
        # have been recorded up to ~180km from permanent water during
        # exceptional dry-season movements.
        #
        # The 300km threshold is a conservative upper bound that ensures
        # those extreme cases score at or near 1.0 without capping too
        # aggressively in normal conditions. This is a placeholder — see
        # Section 4 of the project bible for the full gap acknowledgment.
        "water_threshold_m": 300_000,

        # Pans, wetlands, floodplains, and surface_water added here —
        # this is the config change that fixes the phantom thirst bug.
        # These types are now visible to filter_accessible_water() and
        # will be included in the distance calculation once their source
        # classes are loaded in the pipeline.
        "accessible_water_types": {
            "river", "lake", "pan", "wetland", "floodplain",
            "surface_water", "saline_lake", "permanent_water"
        },

        # Permanent sources weighted at 1.0 — fully reliable year-round.
        # Seasonal sources weighted lower — less reliable in dry season.
        # These are heuristic placeholders, honest about being estimates.
        # Ecological validation from Save the Elephants / IUCN is a future step.
        "water_type_weights": {
            "river":         1.0,
            "lake":          1.0,
            "pan":           0.4,
            "wetland":       0.7,
            "floodplain":    0.7,
            "surface_water": 0.6,
            "saline_lake":   0.4,
            "permanent_water": 0.8,
        },

        # 50km is a commonly cited upper bound for elephant daily range.
        "daily_range_m": 50_000,

        # Elephants are highly water-dependent — drinking daily is
        # non-negotiable for adults.
        "water_dependency": "high",
    },
}

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
# These checks run once at import time — if someone adds a malformed species
# entry, the error surfaces immediately rather than causing a silent failure
# deep inside the scoring pipeline at runtime.

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
            raise ValueError(
                f"{species}: water_type_weights keys must exactly match accessible_water_types. "
                f"Got {set(cfg['water_type_weights'].keys())} vs {cfg['accessible_water_types']}"
            )

        # All weights must be floats in (0.0, 1.0]
        for water_type, weight in cfg["water_type_weights"].items():
            if not isinstance(weight, float) or not (0.0 < weight <= 1.0):
                raise ValueError(
                    f"{species}/{water_type}: weight must be a float between 0 (exclusive) and 1 (inclusive)"
                )

        # daily_range_m must be a positive number
        if not isinstance(cfg["daily_range_m"], (int, float)) or cfg["daily_range_m"] <= 0:
            raise ValueError(f"{species}: daily_range_m must be a positive number")

        # water_dependency must be one of the allowed values
        if cfg["water_dependency"] not in valid_dependency_values:
            raise ValueError(
                f"{species}: water_dependency must be one of {valid_dependency_values}, "
                f"got '{cfg['water_dependency']}'"
            )


# Run validation immediately when this module is imported.
# This means any misconfigured entry fails loudly at startup,
# not silently at scoring time.
_validate_species_config(SPECIES_CONFIG)