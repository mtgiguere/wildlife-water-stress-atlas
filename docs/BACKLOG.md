# Wildlife Stress Atlas — Backlog & Status

> **How to use this file:** phases are ordered — do them top-down. Each is
> independently shippable and follows strict TDD (RED first — see
> `docs/TDD_CONTRACT.md`). The target design is `docs/ARCHITECTURE.md`.
> **Update the "Current status" block and the checkboxes as you go**, so any
> future session can pick up cold.

---

## Current status — 2026-07-15

- **Phase-1 prototype: SHIPPED.** 11 African species; water / road / settlement
  stressors; Mapbox static site (GitHub Pages) + Streamlit app.
- **Settlements feature:** committed + pushed on branch
  `feat/settlements-pressure-layer` (**not merged**). Its subset settlement
  GeoJSON is **gitignored** — a full continental fetch + export must run before
  that data ships. See `[[project-settlements-pressure]]` memory.
- **Dependabot:** 4 open PRs, all inspected and **kosher** (actions/checkout v7,
  actions/setup-python v6, @playwright/test 1.61.1, @types/node 26.1.1). Safe to
  merge; run the two Playwright suites after the playwright bump (a visual test
  imports `playwright-core/lib/utilsBundle`).
- **Architecture v2 (extensible):** **Phase A DONE** (species are JSON plugins,
  committed + pushed on `feat/species-plugins`). **Phase B CORE DONE** (generic
  kind-aware scoring engine, reproduces today's scores — on branch
  `feat/stressor-plugins`, uncommitted). Next is **Phase C** (genericize
  export/frontend; realm gating + consumer migration land there). Design decided
  and locked (do not re-litigate): stressor **kinds**
  (hazard/resource/ambient); **noisy-OR** aggregation `1−∏(1−sᵢ)` as the single
  house formula; scores carry **coverage** (no-data ≠ no-stress). Rationale in
  `docs/ARCHITECTURE.md`.
  - JIT deviation from the original Phase-A plan: the `SpeciesConfig` **dataclass
    + `realm`** were deferred to **Phase B**, where the stressor restructure
    finalizes their shape (writing them in A then rewriting in B = wasted churn).
    Phase A stayed a pure, golden-verified structural refactor.

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

## Phase C — Genericize export + frontend

Goal: views/legends/export driven by which stressors exist, not hardcoded.

- [ ] Generic per-stressor export (replace the `export_road_threats` /
      `export_settlement_threats` special-casing)
- [ ] Stressor-driven map views + legends: an aggregate-stress layer **plus**
      per-stressor breakdown/toggle
- [ ] Species compare mode (Savannah vs Forest elephant)
- [ ] Scenario toggles: stressor on/off, reweight, live re-aggregate

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
