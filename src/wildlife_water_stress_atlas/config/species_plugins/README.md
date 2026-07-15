# Species plugins

One JSON file per species. **To add a species: copy `_template.json` to
`<genus_species>.json`, fill in the values, done.** The loader
(`config/species_loader.py`) discovers it on the next run, validates it
independently, and — if something's wrong — skips *just that file* with a logged
error naming the problem, so one bad plugin never takes down the atlas.

Files whose names start with `_` (like `_template.json`) are ignored.

> Why JSON, not Python? Plugins are **data, not code** — safe to accept from
> contributors, machine-generatable (a future submission form emits JSON), and
> portable across the Python pipeline, the JS frontend, and a future backend.

## Shape

A plugin has **species metadata** at the top level and a **`stressors` list** —
the things that stress this animal, each with the expert's sensitivity and
type-specific params. Adding a stressor an animal doesn't care about is simply
omitting it from the list.

### Species metadata

| Field | Type | Notes |
|---|---|---|
| `scientific_name` | string | Unique key for the species. |
| `common_name` | string | Display name. |
| `realm` | `"terrestrial"` \| `"freshwater"` \| `"marine"` | Ecological realm; groups species and (soon) gates which stressors apply. |
| `emoji` | string | Shown in UI labels. |
| `daily_range_m` | number > 0 | Typical daily movement range; grid sizing / future modeling. |
| `water_dependency` | `"low"` \| `"moderate"` \| `"high"` | Qualitative descriptor (informational). |
| `icon_url` | string | Must start with `https://`. |
| `icon_static_path` | string | Must start with `app/static/`. |
| `gbif_cache_file` | string | Must end with `.gpkg`. |
| `rationale` | string | The ecology behind your values, with sources where possible. Surfaces in the UI. |

### `stressors` — a list, one entry per stressor that affects the species

Each entry: `{ "stressor_id", "sensitivity", "params" }` (optionally `source`,
`validated`). `sensitivity` is 0.0–1.0 (0.0 = immune, short-circuits). `params`
are specific to the stressor:

| stressor_id | kind | params |
|---|---|---|
| `water` | resource (stress rises with **distance** from water) | `threshold_m` (>0), `accessible_types` (array), `type_weights` (object, keys = accessible_types, floats in (0,1]) |
| `roads` | hazard (threat rises with **proximity**) | `threshold_m` (>0), `class_weights` (object, keys cover exactly `motorway, trunk, primary, secondary, tertiary, track, path`; floats in [0,1], 0.0 allowed) |
| `settlements` | hazard (proximity) | `threshold_m` (>0), `class_weights` (keys cover exactly `city, town, village, hamlet`; floats in [0,1]) |

## Coming next

- New **stressor types** (climate, salinity, shipping lanes, air pollution) will
  register as their own plugins, each with a `kind` (hazard / resource /
  ambient), so you can attach any of them here by `stressor_id`.
- `realm` will *gate* which stressors are required (a marine species won't need
  road/settlement stressors). See `docs/ARCHITECTURE.md`.
