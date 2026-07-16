"""
stress_engine.py

The generic, kind-aware scoring engine (docs/ARCHITECTURE.md §5–§6, §10).

It ties the species config to the stressor types and produces, for one species
at one location, a per-stressor breakdown plus a cumulative aggregate. It is
QUERY-shaped — `score_species_stress(species, measurements)` answers a bounded
question — so the same function is driven by a batch tile-baker today and can
run on-demand (AWS Lambda) later without changing shape (§10).

Phase B is ADDITIVE: this engine reads the existing flat species config via a
builder, and reproduces today's exact scores (the golden guard in
test_stress_engine.py). The current pipeline (scoring.py / threat_scoring.py)
is untouched; migrating consumers onto this engine is a later phase.
"""

from dataclasses import dataclass
from pathlib import Path

from wildlife_water_stress_atlas.analytics.stressor_type_loader import load_stressor_types
from wildlife_water_stress_atlas.analytics.stressors import (
    Score,
    StressorConfig,
    aggregate_stress,
)
from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG

# Registry of stressor types by id, discovered from plugin declarations under
# config/stressor_plugins/. Adding a stressor type of an existing kind is one
# JSON file, no code (see stressor_type_loader / the plugins README).
STRESSOR_PLUGINS_DIR = Path(__file__).parent.parent / "config" / "stressor_plugins"
STRESSOR_TYPES = load_stressor_types(STRESSOR_PLUGINS_DIR)


@dataclass(frozen=True)
class StressResult:
    """One species at one location: the cumulative stress plus the per-stressor
    breakdown (always exposed — seeing the small contributors is why we chose
    cumulative over worst-wins, §6)."""

    aggregate: Score
    breakdown: dict[str, Score]


def species_stressors(species: str) -> list[StressorConfig]:
    """
    Build the StressorConfig list for a species from its `stressors` config.

    Reads the plugin's stressors list directly (Phase C). Each stressor type
    reads only the params it needs (a RESOURCE uses threshold_m; extra water
    params like accessible_types are ignored by the scorer), so water — a
    RESOURCE with sensitivity 1.0 — reproduces the legacy min(dist/threshold, 1).

    Raises:
        KeyError: If species is not in SPECIES_CONFIG.
    """
    cfg = SPECIES_CONFIG[species]
    return [StressorConfig(stressor_id=s["stressor_id"], sensitivity=s["sensitivity"], params=s["params"]) for s in cfg["stressors"]]


def score_species_stress(species: str, measurements: dict) -> StressResult:
    """
    Score one species at one location.

    Args:
        species      : Scientific name (must be in SPECIES_CONFIG).
        measurements : {stressor_id: Measurement | None}. A stressor whose
                       measurement is absent/None is uncovered ("no data here"),
                       excluded from the aggregate — never treated as 0 stress.

    Returns:
        StressResult(aggregate, breakdown). `breakdown` has one Score per
        applicable stressor; `aggregate` is the noisy-OR over covered scores.
    """
    breakdown: dict[str, Score] = {}
    for cfg in species_stressors(species):
        stressor_type = STRESSOR_TYPES[cfg.stressor_id]
        measurement = measurements.get(cfg.stressor_id)
        breakdown[cfg.stressor_id] = stressor_type.score(measurement, cfg)

    aggregate = aggregate_stress(breakdown.values())
    return StressResult(aggregate=aggregate, breakdown=breakdown)
