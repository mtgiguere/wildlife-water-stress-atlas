# Wildlife Stress Atlas — Backlog & Status

> **How to use this file:** phases are ordered — do them top-down. Each is
> independently shippable and follows strict TDD (RED first — see
> `docs/TDD_CONTRACT.md`). The target design is `docs/ARCHITECTURE.md`.
> **Update the "Current status" block and the checkboxes as you go**, so any
> future session can pick up cold.

---

## Current status — 2026-07 (Phase C essentially done; cutover complete)

**All merged to `main`:** Phase-1 prototype (11 species; water/road/settlement;
Mapbox + Streamlit), the settlements feature (#24), the dependabot bumps, **Phase
A** (species = JSON plugins, #26), **Phase B** (generic kind-aware scoring engine,
#27), and Phase C C1–C5 (stressors-list config, generic export, STRESS view +
per-stressor toggle with a permanent SwiftShader visual guard, stressor-TYPE
plugins). `main` is green with the full extensible engine.

- **Phase C — scoring CUTOVER complete** on branch `feat/cutover-unify-scoring`
  (off `main`; open for review): the generic engine is now the **sole scoring
  path**. Deleted `analytics/threat_scoring.py` and `scoring.water_stress_score`
  (kept `classify_stress_level`); the export scripts + `water_access` + streamlit
  `stats` all score via `score_stressor` / read params via `get_stressor_params`.
  Removed the `_flatten_stressors` bridge — the **`stressors` list is the single
  config shape** (no flat water_*/road_*/settlement_* keys). The golden
  "reproduces the original scores" guarantee is preserved by a frozen test-only
  oracle (`tests/_scoring_oracle.py`). Config validation was re-pointed to the
  stressors list, preserving all prior guards (incl. class-weight completeness).
  746 tests, 99% coverage, lint clean.
- **Remaining in Phase C (not started):** species compare mode; scenario toggles.
- **Deferred: realm gating** — blocked on marine stressor *types* that don't
  exist yet, and redundant with current validation for the existing (all
  terrestrial/freshwater) species. Revisit when a marine species/stressor lands.
- **Data caveat:** the committed settlement GeoJSON is a SUBSET (kenya/tanzania/
  south-africa); run the full continental fetch + export before shipping. The new
  STRESS view also needs a continental `stress_gbif_*` export before it's populated
  (its data is gitignored dev data today).
- **Deploy:** a GitHub Pages workflow (`ci/pages-mapbox-deploy`) publishes the
  static Mapbox app; requires Settings → Pages → Source = "GitHub Actions".

**Design decided and locked (do not re-litigate):** stressor **kinds**
(hazard/resource/ambient); **noisy-OR** aggregation `1−∏(1−sᵢ)` as the single
house formula; scores carry **coverage** (no-data ≠ no-stress); plugins are
**JSON**; the scoring engine is **query-shaped**. Rationale in `docs/ARCHITECTURE.md`.

---

## Phase A — Species become plugins  ✅ DONE

Goal: one file per species; dynamic discovery; adding a species = adding a file.
Kept the registry OUTPUT shape identical so scoring/export/frontend didn't change.

- [x] Loader `config/species_loader.py`: discover `species_plugins/*.json`, key by
      `scientific_name`, validate each independently, **skip + log** a malformed
      one (don't crash), reject duplicate names, `transform` hook for coercion.
      (`test_species_loader.py`, 12 tests)
- [x] Plugins are **JSON, not Python** — inert data (safe from contributors),
      machine-generatable (future submission form), portable (frontend/DB/API).
      Ecological rationale promoted from code comments to a `rationale` data field.
- [x] `species_plugins/_template.json` + `README.md` field docs for a non-maintainer
- [x] Migrated all 11 species into `species_plugins/*.json` (rationale preserved)
- [x] Wired `config/species.py` to build `SPECIES_CONFIG` via the loader
      (1021 → 251 lines); public import surface unchanged
- [x] Closed the validation gap: road/settlement fields now validated
      (`_validate_proximity_stressor`); `test_species_config.py` extended
- [x] Golden regression test: loaded registry deep-equals a frozen pre-migration
      snapshot (`test_species_migration.py` + `tests/_species_config_snapshot.py`)
- [ ] `SpeciesConfig` dataclass + `Realm` enum → **moved to Phase B** (see note above)

## Phase B — Stressors become plugins + generic scoring engine  ✅ CORE DONE

Goal: stressor types are kind-aware; the engine aggregates a species' stressors.
Built ADDITIVELY — the engine reads the existing flat config via a builder and
reproduces today's scores; the legacy pipeline (scoring/threat_scoring) is
untouched. All in `analytics/stressors.py` + `analytics/stress_engine.py`.

- [x] `StressorKind` enum (hazard / resource / ambient)
- [x] Reference stressor types: `HazardStressor`, `ResourceStressor`,
      `AmbientStressor` (each owns its kind's math; `score()→Score`)
- [x] `Measurement` abstraction (`FeatureProximity` / `FieldSample`)
- [x] `StressorConfig` (sensitivity, params, `source`, `validated`)
- [x] `Score(value, covered)` + `aggregate_stress` = noisy-OR over covered
      (cumulative, no-data honest) (`test_stress_aggregation.py`, 12)
- [x] Generic engine `score_species_stress(species, measurements)` →
      per-stressor breakdown + noisy-OR aggregate + coverage (`stress_engine.py`)
- [x] **Engine is QUERY-shaped** (per species×location), not batch `export_all()`
- [x] `Realm` enum + `realm` on all 11 plugins + validated (`species.py`)
- [x] **GOLDEN**: engine reproduces road/settlement/water scores EXACTLY for all
      11 species × every class (`test_stress_engine.py`, 148 tests)
- [x] Per-kind behavior tests (hazard decays, resource inverts, ambient ignores
      distance) (`test_stressor_types.py`, 43)

Deferred to Phase C (need the generic path to be the consumer first):
- [ ] `realm` GATING of required stressors — needs the plugin config to move from
      flat fields to a `stressors` list (a marine species then omits road fields).
      Realm is added + validated now; gating lands with that restructure.
- [ ] Migrate consumers (export scripts, frontend) onto the engine, then retire
      the flat fields / legacy scoring functions.

## Phase C — Genericize export + frontend  🟡 IN PROGRESS

Goal: views/legends/export driven by which stressors exist, not hardcoded.
Branch `feat/stressors-list-config`.

- [x] **C1** — plugins → `stressors` list (source of truth); `_flatten_stressors`
      bridge keeps legacy consumers green; engine reads the list.
      (`test_stressors_list_config.py`; golden guards hold)
- [x] **C2** — `compute_species_stress` composes overlap + engine over occurrences
      → per-stressor breakdown + noisy-OR aggregate; golden-verified vs legacy
      pipelines (`scripts/export_stress.py`, `test_export_stress.py`)
- [x] **C3** — generic file-writing export: `export_species_stress` /
      `export_all_stress` write one `stress_gbif_<slug>.geojson` per species with
      per-stressor + aggregate columns (`scripts/export_stress.py`,
      `test_export_stress.py`). (Retiring the special-case export scripts happens
      at cutover, once the frontend reads the generic output.)
- [x] **C4** — stressor-driven map views + legends. ⚑ STRESS view colors
      occurrences by `stress_aggregate` (cumulative noisy-OR) with a per-stressor
      breakdown in the hover tooltip, **plus a "colour by" toggle** to recolor by
      any single stressor's contribution (Total / Water / Roads / Settlements) —
      the map-layer form of the breakdown. DOM e2e tests; **permanent SwiftShader
      visual guards** (aggregate paints + toggle recolors) fed by an INLINE stress
      fixture, so they need no gitignored data file — RED-verified by zeroing the
      dot radii. (`test_mapbox_visual.spec.ts`)
- [x] **C5** — stressor TYPES are plugins: JSON declarations {stressor_id, kind}
      referencing hazard/resource/ambient scorers; `stressor_type_loader.py`
      discovers them (skip+log malformed) and the engine builds STRESSOR_TYPES
      from `config/stressor_plugins/`. Adding a stressor type of an existing kind
      is now one JSON file, no code (demonstrated with a `fences` drop-in). Closes
      the retro gap; golden reproduction holds. (`test_stressor_type_loader.py`, 8)
- [x] **CUTOVER** — the generic engine is the SOLE scoring path. Added
      `score_stressor` (single scalar via the engine); routed the road/settlement/
      water export scripts + `water_access` + streamlit `stats` through it; deleted
      `threat_scoring.py`, `scoring.water_stress_score`, and the `_flatten_stressors`
      bridge; the `stressors` list is now the single config shape (no flat keys) with
      validation re-pointed to it. Golden reproduction preserved by a frozen test
      oracle (`tests/_scoring_oracle.py`). (branch `feat/cutover-unify-scoring`)
- [ ] Species compare mode (Savannah vs Forest elephant)
- [x] **Scenario toggles** — STRESS view "Include" control excludes a stressor and
      re-aggregates the cumulative noisy-OR LIVE (client-side Mapbox expression over
      the enabled per-stressor props; legend + tooltip annotate exclusions). DOM
      e2e + a SwiftShader visual guard (RED-verified). Raised the stress visual
      threshold above the render-noise floor. (branch `feat/scenario-toggles`)
      **Follow-on:** per-stressor reweight (slider) + live re-aggregate.

## Phase D — Range + grid scoring

- [ ] Range per species: derive-from-points default + optional IUCN polygon override
- [ ] Score a grid/surface over the range (not just occurrence points)
- [ ] Surface the confidence/coverage layer on the map (no-data ≠ no-stress, visibly)

## Phase E — Temporal

- [ ] Time-series measurements; per-year stress
- [ ] Trend-based stressors (score from rate-of-change, e.g. rainfall decline) —
      the bridge into the 3-phase roadmap's "Predict"
- [ ] Fix the "current snapshot stamped onto all years" limitation

## Phase F — Infra: render / delivery

- [ ] Mapbox GL JS → MapLibre GL JS (+ an open basemap style; drop the token)
- [ ] Static GeoJSON → PMTiles (rework client filtering to tile attrs / feature-state)

## Phase G — Infra: compute layer  *(gated)*

- [ ] FastAPI + AWS Lambda + PostGIS behind seam 3
- [ ] Plugin submission flow — **REQUIRES a design conversation first**
      (`docs/ARCHITECTURE.md` §11)

---

## Cross-cutting (every phase)

- **TDD**: RED first; golden regression tests at every seam. Field-name drift
  between loader → registry → scoring is the documented bug class this repo was
  burned by — write the contract test before the implementation.
- **Keep the authoring loop fast** (edit file → see it on the map). "Ultimate
  power" for an ecologist is only real if the cycle is seconds, not a 30-minute
  continental re-fetch.
- **Provenance**: every expert value carries `source` + `validated`.
- **JIT scope**: build the seam, implement the local version, don't gold-plate a
  future phase.

## Housekeeping (not blocking the phases)

- [ ] Merge the settlements branch (decide: before or alongside architecture work)
- [ ] Run the full continental fetch + export before shipping settlement data
- [ ] Merge the 4 kosher dependabot PRs
