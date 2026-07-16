"""
stressor_type_loader.py

Discovery loader for stressor-TYPE plugins (docs/ARCHITECTURE.md §5, BACKLOG C5).

A stressor type is an inert JSON declaration — {stressor_id, name, kind} — where
`kind` (hazard / resource / ambient) supplies the scoring math via KIND_SCORERS.
So adding a stressor type of an existing kind (e.g. a `fences` hazard) is one
JSON file, no code; a genuinely new *kind* is the only thing that needs code.

Mirrors the species loader: discovers `*.json` (ignoring `_`-prefixed), maps each
to its kind's scorer, and SKIPS + logs a malformed declaration rather than
crashing the whole load. Returns {stressor_id: scorer} — the scorer exposes
`.kind` and `.score(measurement, cfg)`.
"""

import json
import logging
from pathlib import Path

from wildlife_water_stress_atlas.analytics.stressors import (
    AmbientStressor,
    HazardStressor,
    ResourceStressor,
    StressorKind,
)

logger = logging.getLogger(__name__)

# One scorer per kind — the math lives here; stressor-type plugins just pick a
# kind. Adding a new KIND is the only change that requires code.
KIND_SCORERS = {
    StressorKind.HAZARD.value: HazardStressor(),
    StressorKind.RESOURCE.value: ResourceStressor(),
    StressorKind.AMBIENT.value: AmbientStressor(),
}


def load_stressor_types(plugins_dir: str | Path) -> dict:
    """
    Discover stressor-type plugins (`*.json`) and map each to its kind's scorer.

    Args:
        plugins_dir : Directory of stressor-type JSON declarations. `_`-prefixed
                      files (e.g. `_template.json`) are ignored.

    Returns:
        {stressor_id: scorer}. A declaration with a bad/unknown kind, a missing
        stressor_id, or invalid JSON is skipped and logged.

    Raises:
        ValueError: If two plugins declare the same stressor_id.
    """
    plugins_dir = Path(plugins_dir)
    registry: dict = {}

    for path in sorted(plugins_dir.glob("*.json")):
        if path.name.startswith("_"):
            continue

        try:
            with path.open(encoding="utf-8") as f:
                decl = json.load(f)

            if not isinstance(decl, dict):
                raise ValueError("plugin must be a JSON object")

            stressor_id = decl.get("stressor_id")
            if not isinstance(stressor_id, str) or not stressor_id.strip():
                raise ValueError("missing non-empty 'stressor_id'")

            kind = decl.get("kind")
            if kind not in KIND_SCORERS:
                raise ValueError(f"unknown kind {kind!r}; must be one of {sorted(KIND_SCORERS)}")
        except Exception as e:
            logger.warning("Skipping malformed stressor-type plugin '%s': %s", path.name, e)
            continue

        if stressor_id in registry:
            raise ValueError(f"Duplicate stressor_id '{stressor_id}' (second in {path.name})")

        registry[stressor_id] = KIND_SCORERS[kind]

    return registry
