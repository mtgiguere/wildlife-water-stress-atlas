"""
species_loader.py

Discovery loader for species plugins — the engine behind "one file per species"
(docs/ARCHITECTURE.md §5, docs/BACKLOG.md Phase A).

Plugins are **JSON** files: inert data (safe to accept from contributors, unlike
executable Python), machine-generatable (a future submission form emits JSON),
and portable across the Python pipeline, the JS frontend, and a future
backend/DB. Each `*.json` file IS one species object and must include a
`"scientific_name"`. `load_species_plugins()` assembles the
`{scientific_name: entry}` registry and — critically — **skips and logs a
malformed plugin rather than crashing the whole load**, so one bad file an
ecologist adds can't take down the atlas.

Files whose names start with `_` (e.g. `_template.json`) are ignored, so a
copy-me template can live alongside real plugins.
"""

import json
import logging
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)


def _read_species_file(path: Path) -> dict:
    """Parse one plugin JSON file into a species entry dict.

    Raises on any problem (bad JSON, not an object, missing/blank
    scientific_name) so the caller can skip-and-log uniformly.
    """
    with path.open(encoding="utf-8") as f:
        entry = json.load(f)  # may raise json.JSONDecodeError

    if not isinstance(entry, dict):
        raise ValueError(f"{path.name}: plugin must be a JSON object")

    name = entry.get("scientific_name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"{path.name}: plugin must include a non-empty 'scientific_name'")

    return entry


def load_species_plugins(
    plugins_dir: str | Path,
    validate: Callable[[dict], None] | None = None,
    transform: Callable[[dict], dict] | None = None,
) -> dict[str, dict]:
    """
    Discover and load every species plugin (`*.json`) in a directory.

    Args:
        plugins_dir : Directory holding one `*.json` file per species. Files
                      whose names start with `_` are ignored (templates).
        validate    : Optional per-entry validator called as `validate(entry)`;
                      should raise on an invalid entry. A plugin that fails
                      validation is skipped and logged.
        transform   : Optional per-entry transform applied AFTER parsing and
                      BEFORE validation/storage — the home for domain-specific
                      coercion (e.g. JSON arrays → sets) so the loader itself
                      stays schema-agnostic.

    Returns:
        `{scientific_name: entry}` for every plugin that loaded and validated
        cleanly. Malformed plugins are skipped with a logged warning.

    Raises:
        ValueError: If two plugins declare the same scientific_name.
    """
    plugins_dir = Path(plugins_dir)
    registry: dict[str, dict] = {}

    for path in sorted(plugins_dir.glob("*.json")):
        if path.name.startswith("_"):
            continue

        try:
            entry = _read_species_file(path)
        except Exception as e:
            logger.warning("Skipping malformed species plugin '%s': %s", path.name, e)
            continue

        name = entry["scientific_name"]
        if name in registry:
            raise ValueError(f"Duplicate scientific_name '{name}' (second in {path.name})")

        if transform is not None:
            entry = transform(entry)

        if validate is not None:
            try:
                validate(entry)
            except Exception as e:
                logger.warning("Skipping invalid species plugin '%s' (%s): %s", path.name, name, e)
                continue

        registry[name] = entry

    return registry
