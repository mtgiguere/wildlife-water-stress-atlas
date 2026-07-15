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
- **Architecture v2 (extensible):** **Phase A DONE** (species are plugins);
  next is **Phase B**. On branch `feat/species-plugins` (uncommitted at time of
  writing). Design decided and locked (do not re-litigate): stressor **kinds**
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

## Phase B — Stressors become plugins + generic scoring engine

Goal: stressor types are plugins; the engine is kind-aware; species reference
stressors + expert params. **This is the real scoring-layer rewrite.**

- [ ] `StressorKind` enum (hazard / resource / ambient)
- [ ] `StressorType` protocol/plugin (`stressor_id`, `name`, `kind`,
      `class_keys`, `score()→Score(value,coverage)`, `validate()`)
- [ ] `Measurement` abstraction (FeatureProximity / FieldSample; series-capable)
- [ ] `StressorConfig` (sensitivity, type-validated params, `source`, `validated`)
- [ ] Refactor water (RESOURCE) and roads+settlements (HAZARD) into reference
      stressor-type plugins
- [ ] Generic scoring engine: iterate `cfg.stressors` → look up type → score →
      aggregate via noisy-OR → carry coverage
- [ ] **Engine interface is QUERY-shaped** — `score(species, region/tile, year)`,
      NOT a batch `export_all()`. The one scale-critical decision (ARCHITECTURE
      §10): keeps precompute-to-static and compute-on-demand a seam-3 swap, not a
      rewrite. A thin batch driver calls it to bake tiles today.
- [ ] `realm` gating in validation (marine species not required to supply
      terrestrial stressors)
- [ ] **GOLDEN regression test**: the generic engine reproduces today's EXACT
      road/settlement/water scores for all 11 species (the safety net)
- [ ] RED-first per-kind behavior tests (hazard decays with distance; resource
      inverts; ambient ignores distance entirely)

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
