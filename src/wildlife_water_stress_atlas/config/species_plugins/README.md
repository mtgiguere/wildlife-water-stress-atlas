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

## Fields

| Field | Type | Notes |
|---|---|---|
| `scientific_name` | string | Unique key for the species. |
| `common_name` | string | Display name. |
| `emoji` | string | Shown in UI labels. |
| `water_threshold_m` | number > 0 | Distance (m) at which the species is fully water-stressed (score 1.0). Water is a **resource** — stress rises with distance from it. |
| `accessible_water_types` | array of strings (non-empty) | Water types this species can use (e.g. `["river","lake","pan"]`). |
| `water_type_weights` | object → floats in (0, 1] | Reliability weight per type. **Keys must exactly match `accessible_water_types`.** |
| `daily_range_m` | number > 0 | Typical daily movement range; used for grid sizing / future modeling. |
| `water_dependency` | `"low"` \| `"moderate"` \| `"high"` | Qualitative descriptor. |
| `icon_url` | string | Must start with `https://`. |
| `icon_static_path` | string | Must start with `app/static/`. |
| `gbif_cache_file` | string | Must end with `.gpkg`. |
| `road_sensitivity` | float in [0, 1] | How strongly roads threaten this species. `0.0` = immune (short-circuits). Roads are a **hazard** — threat rises with proximity. |
| `road_threshold_m` | number > 0 | Distance beyond which roads have no effect. |
| `road_class_weights` | object → floats in [0, 1] | Per-class severity (0.0 allowed). Keys must cover exactly: `motorway, trunk, primary, secondary, tertiary, track, path`. |
| `settlement_sensitivity` | float in [0, 1] | How strongly settlements threaten this species. `0.0` = immune. Hazard. |
| `settlement_threshold_m` | number > 0 | Distance beyond which settlements have no effect. |
| `settlement_class_weights` | object → floats in [0, 1] | Per-class severity. Keys must cover exactly: `city, town, village, hamlet`. |
| `rationale` | string | The ecology behind your values, with sources where possible. Preserved from the original inline comments; surfaces in the UI. |

## Coming in Phase B

The road/settlement fields will migrate to a generic `stressors` list, so you'll
be able to attach **any** stressor type — climate, salinity, shipping lanes,
air pollution — each with a `kind` (hazard / resource / ambient), not just these
three. A `realm` field (terrestrial / freshwater / marine) will gate which
stressors apply. See `docs/ARCHITECTURE.md`.
