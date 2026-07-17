# Wildlife Water Stress Atlas — Claude Context

## What This Project Is

A geospatial decision-support platform mapping environmental stress for 11 African species (elephant, zebra, giraffe, lion, cheetah, crocodile, flamingo, painted reed frog, clawed frog, hippo, buffalo). Computes distance from GBIF occurrence records to nearest accessible water (and to roads/settlements) scored against species-specific thresholds.

**Three-phase roadmap:**
- Phase 1 — Describe (current water stress) ✅ working
- Phase 2 — Predict (climate modeling) 🔲 planned
- Phase 3 — Prescribe (conservation interventions) 🔲 planned

---

## ⭐ Direction: v2 Extensible Architecture (design agreed 2026-07-15, build not started)

The project is being re-architected from this fixed prototype into an
**extensible wildlife stress atlas**: ecologists add **species AND stressor
types** as plugin files (incl. **marine** realms), stressors aggregate into one
comparable stress score per animal, and the compute layer is designed to move to
AWS later behind a stable seam. End goal: hand it to a conservation org (TNC/WWF).

- **Target design → [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)** — read before touching `config/species.py`, `analytics/scoring.py`, or any threat/stressor module.
- **Phased work + current status → [`docs/BACKLOG.md`](docs/BACKLOG.md)** — next work starts at **Phase A (species-as-plugins)**.
- **Decided & locked (do not re-litigate; see ARCHITECTURE.md for why):** stressor **kinds** — hazard / resource / ambient (water is a RESOURCE, inverted from roads/settlements; ambient = climate/pollution with no distance); aggregation = **noisy-OR** `1−∏(1−sᵢ)` (one house formula for comparability; experts set per-stressor weights); scores carry **coverage** so no-data ≠ no-stress.

---

## TDD Is Non-Negotiable

**Read `docs/TDD_CONTRACT.md` before writing any code.**

This document contains real bugs from a prior project that were caused by writing tests after implementation. Every new function, every bug fix, every edge case follows the same sequence:

1. Write the test. Run it. **Confirm RED.**
2. Write the minimum implementation. Run it. **Confirm GREEN.**
3. Refactor if needed. Reconfirm GREEN.
4. Then and only then commit or open a PR.

The RED step is not optional. Skipping it means you are doing TAD, not TDD.

---

## Architecture

```
src/wildlife_water_stress_atlas/   # Core library
├── config/species.py              # Single source of truth: all 11 species params
│                                  #   (water, road-threat AND settlement-threat fields;
│                                  #   KNOWN_ROAD_CLASSES, KNOWN_SETTLEMENT_CLASSES)
├── analytics/                     # overlap, scoring, spatial, water_access, trends,
│                                  #   apply, threat_scoring (road + settlement proximity)
├── ingest/                        # gbif.py, water.py, threats.py (OSMRoads + OSMSettlements)
├── visualization/maps.py
└── utils/generic_threader.py

apps/
├── streamlit/                     # Python/PyDeck interactive app
└── mapbox/                        # Vanilla JS + static GeoJSON (no server required)
                                   #   Views: POINTS (stress), COUNTRIES, ROADS (road threat),
                                   #   SETTLEMENTS (settlement threat)

scripts/                           # Data processing and export (run once)
                                   #   fetch_road_data.py (downloads roads + settlements in one
                                   #   pass), export_road_threats.py, export_settlement_threats.py
tests/                             # unit test files + e2e/ (Playwright)
docs/TDD_CONTRACT.md               # Read this before coding (has a road-threat addendum)
```

---

## Key Conventions

- **`config/species.py`** is the single source of truth for all species parameters. Never hardcode species data elsewhere.
- **Water source types** use a normalized schema across all ingest paths.
- **Integration tests** are marked `@pytest.mark.integration` and skipped in CI (require real data files on disk).
- **Mathematical/algorithmic functions** use Hypothesis property-based tests, not seed-based assertions.

---

## Commands

```bash
# Unit tests
pytest

# Unit tests with coverage
pytest --cov=wildlife_water_stress_atlas --cov-report=term-missing

# Lint
ruff check .
ruff format .

# E2E tests (Streamlit)
npx playwright test --config=playwright.config.ts

# E2E tests (Mapbox — DOM). NOTE: this config has NO webServer block; it expects
# a static server already running on :3000. Start one first:
#   (cd apps/mapbox && python -m http.server 3000)
npx playwright test --config=playwright.mapbox.config.ts

# Visual guards (Mapbox — SwiftShader/WebGL). This config DOES start its own
# server, so no manual step is needed.
npx playwright test --config=playwright.visual.config.ts
```

---

## Tech Stack

| Layer | Tools |
|-------|-------|
| Core | Python 3.12, GeoPandas, Rasterio, Shapely, PyProj, PyOGRIO |
| Frontend (interactive) | Streamlit, PyDeck |
| Frontend (static) | Mapbox GL JS, vanilla JS |
| Testing | pytest, pytest-cov, Hypothesis, Playwright |
| Lint | Ruff (line-length 200, Py312 target) |
| CI | GitHub Actions — lint + test + pip-audit on push/PR to main |
| Optional DB | PostgreSQL + PostGIS via SQLAlchemy + GeoAlchemy2 |
