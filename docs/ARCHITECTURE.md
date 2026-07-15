# Wildlife Stress Atlas — Target Architecture (v2: Extensible)

> **Status:** DESIGN AGREED (2026-07-15). **Not yet implemented.**
> Phased work + current status live in [`docs/BACKLOG.md`](BACKLOG.md).
> This file is the authoritative target design — **read it before touching
> `config/species.py`, `analytics/scoring.py`, or any threat/stressor module.**
>
> Supersedes the old `docs/wildlife_atlas_architecture_changes.md` (removed).
> That brief was written without seeing the code and contained an assumption
> since proven wrong — that water/road/settlement "share one shape." They do
> not (see §4). This document reflects the corrected design.

---

## 1. Vision

Turn the Phase-1 prototype (a fixed set of 11 African savanna species; water,
road, and settlement stressors; a Mapbox static site) into an **extensible
wildlife stress atlas** where:

- **Ecologists add species and stressor types as plugin files** — one file
  each, no core-code edits.
- It supports any **realm** — terrestrial, freshwater, **marine** (a dolphin
  cares about shipping lanes and fishing gear, not roads or settlements).
- It aggregates the **set** of stressors an expert assigns to an animal into a
  single, comparable **stress** read-out, shown on a map, with a
  per-stressor breakdown, and comparable across species (e.g. Savannah vs
  Forest elephant).
- It is architected so heavy compute can move to **AWS later as a swap behind a
  stable seam**, not a rewrite.
- End goal: **hand it to a conservation org** (TNC / WWF / similar) whose own
  staff extend it.

## 2. The ecologist's loop (this IS the product)

> add an animal → pick/define the stressors that affect it → set the values
> (their expert judgment) → see it on the map → get one aggregate stress per
> animal from its 1..* stressors, *with the per-stressor breakdown* → compare
> animals.

Everything below serves that loop. The tool supplies the machinery; **the
expert supplies the judgment** (which stressors, and how strongly).

## 3. Core principle — stable contracts + swappable seams; implement local first

Four seams, each independently replaceable:

1. **Plugins** — species + stressor-type files; validated and discovered dynamically.
2. **Scoring engine** — kind-aware; reads plugins; knows nothing about any
   specific species or stressor.
3. **Compute/data layer** — behind an interface. "Local Python pipeline" today;
   "FastAPI + PostGIS on AWS Lambda" later — **without touching seams 1–2.**
4. **Render/delivery** — MapLibre + PMTiles, driven by whatever stressors exist;
   no hardcoded per-stressor views.

**Build stable contracts for all four now; implement only the local versions.**
AWS is a swap behind seam 3, not a rewrite. Rendering + delivery stay static and
effectively free at any traffic; only compute costs money, and only when working.

## 4. Stressor *kinds* — why "one shape" was wrong

The prototype's three stressors do **not** share one shape:

| Kind | Meaning | Examples | Score direction |
|---|---|---|---|
| `HAZARD` | closer = worse | roads, settlements, shipping lanes, fishing gear | `∝ (1 − dist/threshold)` |
| `RESOURCE` | closer = better | water | `∝ dist/threshold` (inverted) |
| `AMBIENT` | always present, no distance | climate, air pollution, salinity-as-field | from a sampled field value |
| *(extensible)* | new kinds added as plugins | — | type-defined |

Water is a **resource** (stress rises with *distance*); roads/settlements are
**hazards** (threat rises with *proximity*). Water also has no "sensitivity"
today and its weights mean *reliability*, not *severity*. This is exactly why a
generic stressor system needs **kinds**: the stressor *type* owns its own math,
and the **species-facing contract bakes in no distance/decay assumption**, so
ambient and future kinds fit with no redesign.

## 5. The contract (target shapes)

```python
class StressorKind(Enum):
    HAZARD = "hazard"; RESOURCE = "resource"; AMBIENT = "ambient"   # extensible

class Realm(Enum):
    TERRESTRIAL = "terrestrial"; FRESHWATER = "freshwater"; MARINE = "marine"

@dataclass(frozen=True)
class Score:
    value: float | None   # 0.0–1.0, or None when uncovered
    covered: bool         # False = "no data here" (NEVER silently 0 — see §6)

# Measurement is kind-specific AND general enough to be a point, a grid cell,
# or a time-series (so trend-stressors and grid scoring slot in — §7, §8):
#   FeatureProximity(distance_m, feature_class)   # hazard / resource
#   FieldSample(value)                            # ambient
#   TimeSeries(samples_by_year)                   # trend-based stressors

class StressorType(Protocol):          # one per stressor-type plugin file
    stressor_id: str
    name: str
    kind: StressorKind
    class_keys: frozenset[str] | None  # valid class_weights keys, or None
    def score(self, measurement, cfg: "StressorConfig") -> Score: ...
    def validate(self, cfg: "StressorConfig") -> None: ...   # type-specific param check

@dataclass
class StressorConfig:                  # ← the EXPERT fills this in, per species
    stressor_id: str
    sensitivity: float                 # 0.0 = immune (short-circuits); 1.0 = max
    params: dict                       # validated by the stressor TYPE, not the species
    source: str | None = None          # citation for the values (defensibility)
    validated: bool = False            # True = expert-validated; False = heuristic placeholder

@dataclass
class SpeciesConfig:                    # ← one per species plugin file
    scientific_name: str; common_name: str; emoji: str
    realm: Realm
    stressors: list[StressorConfig]
    range_polygon: "Geometry | None" = None   # optional IUCN override; else derived (§7)
```

Decided refinements:
- **`score()` returns value + coverage** — "no data" is honest, never a fake 0 (§6).
- **`StressorConfig` carries `source` + `validated`** — every expert value can
  cite its basis; today's numbers are all heuristic placeholders, and that
  honesty should be machine-readable for an org handoff.
- **Measurement is general** — point / grid cell / time-series — so §7 (grid) and
  §8 (trend) need no contract change later.

## 6. Aggregation — how 1..* stressors become one "stress"

**House formula (ONE, fixed):** probabilistic union / noisy-OR:

> **stress = 1 − ∏ (1 − sᵢ)**

- Captures cumulative "death by a thousand cuts": four small 0.2 stressors →
  `1 − 0.8⁴ = 0.59`, not `0.20`. (Max-wins was rejected precisely because it
  hides this.)
- Bounded [0,1]; adding a 0.0 stressor doesn't dilute; strictly monotonic;
  order-independent.
- **Per-stressor weights are expert-set** (they set each `sᵢ` via sensitivity +
  params). **The combine formula is fixed house policy, NOT per-species** — the
  moment two species aggregate differently, cross-species comparison
  (Savannah vs Forest elephant) becomes apples-to-oranges.
- **Always expose the per-stressor breakdown** in the UI — seeing the small
  contributors is the whole reason we rejected worst-wins.

## 7. Range & spatial output

- We score a **surface over the animal's range**, not just observed points —
  occurrence points are biased by observation effort (the COVID / GBIF-effort
  caveat that motivated this whole project's honesty stance).
- **Range = derive-from-occurrence-points by default** (keeps "add an animal =
  one file, zero extra work"), with an **optional expert-supplied IUCN range
  polygon override** (curated, defensible — the kind of judgment org users want
  to supply).
- Occurrences are **evidence for the range + a validation set**, NOT individual
  animal tracks (GBIF records are independent historical observations).
- The prototype currently scores per-occurrence-point; **grid-over-range is a
  follow-on phase** — the contract already supports it (measurement is
  location-agnostic).

## 8. Time

- Some stressors are **inherently temporal**: the stressful thing is the
  **trend / rate of change**, not the level. Rainfall at a stable 400mm isn't
  stress; 400→300→200 over decades is — the animal adapts to stable conditions
  but not to a moving baseline.
- The contract supports a **time-series measurement**; a trend-stressor scores
  from the slope. This is the bridge into the roadmap's Phase-2 "Predict."
- Two temporal modes to support: **snapshot-per-year** (roads in 2010 vs 2020)
  and **trend-as-the-stressor** (rainfall decline). The prototype currently
  stamps a single current snapshot onto every year — a known limitation noted
  in the code; fix it when temporal lands.

## 9. Infrastructure (later phases)

- **Mapbox GL JS → MapLibre GL JS.** Open-source, no token, no per-view billing.
  Caveat: the current basemap `mapbox://styles/mapbox/dark-v11` is a
  *proprietary Mapbox-hosted style requiring a token* — MapLibre needs an **open
  style** (OpenFreeMap / Protomaps / MapTiler). And MapLibre forked before
  Mapbox GL **v2**, so it is *not* 1:1 with the v2 API in use. Real work, not a
  find-replace.
- **Static GeoJSON/GeoPackage → PMTiles.** Cloud-optimized vector tiles served
  from S3/any CDN via HTTP range requests; no tile server. Caveat: this changes
  the **client-side filtering model** — today the year-slider/species switch
  filter GeoJSON in the browser; with pre-baked tiles you filter via tile
  attributes + feature-state (or separate tilesets).
- **FastAPI on AWS Lambda + PostGIS** for the compute layer (seam 3) — mirrors
  the Global Freshwater Intelligence stack, so not a new stack to learn.
  **Last phase**, and **gated on the plugin-submission-flow decision** (§11).

## 10. Non-goals (this era)

- Do **not** source/wire real poaching-incident or disease-prevalence data —
  both largely non-public; out of scope until a conservation-org data partner.
- Do **not** build marine/aquatic/bird species *content* yet — only ensure
  `realm` + kinds don't block adding them.
- Do **not** build a non-technical (web-form) plugin-submission flow yet — the
  target authoring UX is "an ecologist copies a template file and fills in
  values," not "a form generates the file."

## 11. Open questions (resolve when reached — do NOT guess)

- **Plugin submission flow:** how a new species/stressor file gets from
  "written" to "validated, running, live." GitHub PR + CI validation? A backend
  form? Needs a conversation before Phase G.
- Which stressors get real time-series vs static current-snapshot.
- **Stressor interactions/synergy** (e.g. drought × water). Aggregation is
  independent-union for now; don't design so rigidly it can *never* express
  interaction.
- **Response-curve library** (linear / step-cliff / sigmoid / categorical) —
  types offer, experts pick. Salt tolerance is a cliff, not a line.
