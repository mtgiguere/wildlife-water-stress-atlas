# Stressor-type plugins

One JSON file per **stressor type**. **To add a stressor type: copy
`_template.json` to `<stressor_id>.json`, pick a `kind`, done.** The loader
(`analytics/stressor_type_loader.py`) discovers it and wires it to that kind's
scorer; a malformed declaration is skipped and logged, never fatal.

Files whose names start with `_` (like `_template.json`) are ignored.

## Fields

| Field | Type | Notes |
|---|---|---|
| `stressor_id` | string | Unique id; species reference it in their `stressors` list. |
| `name` | string | Human-readable name (UI). |
| `kind` | `"hazard"` \| `"resource"` \| `"ambient"` | Supplies the scoring math (see below). |

## Kinds (the math lives here)

- **`hazard`** — closer = worse (roads, settlements, shipping lanes, fences).
  `score = sensitivity × class_weight × (1 − dist/threshold)`.
- **`resource`** — closer = better; stress rises with distance (water).
  `score = sensitivity × min(dist/threshold, 1)`.
- **`ambient`** — always present, no distance (climate, air pollution, salinity).
  `score = sensitivity × clamp((value − low)/(high − low), 0, 1)`.

Adding a stressor type of an **existing** kind is pure data (this file) — no
code. A genuinely **new kind** is the only thing that needs a new scorer in
`analytics/stressors.py` + an entry in `KIND_SCORERS`.

> A stressor type still needs a way to be *measured* — a feature layer (for
> hazard/resource distance) or a sampled field (for ambient). Wiring that data
> source is separate from declaring the type here.
