# Wildlife Water Stress Atlas — Claude Context

## What This Project Is

A geospatial decision-support platform mapping freshwater access stress for 9 African species (elephants, zebras, giraffes, lions, cheetahs, crocodiles, flamingos, frogs). Computes distance from GBIF occurrence records to nearest accessible water, scored against species-specific thresholds.

**Three-phase roadmap:**
- Phase 1 — Describe (current water stress) ✅ working
- Phase 2 — Predict (climate modeling) 🔲 planned
- Phase 3 — Prescribe (conservation interventions) 🔲 planned

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
│                                  #   (water AND road-threat fields; KNOWN_ROAD_CLASSES)
├── analytics/                     # overlap, scoring, spatial, water_access, trends,
│                                  #   apply, threat_scoring (road proximity)
├── ingest/                        # gbif.py, water.py, threats.py (OSM roads)
├── visualization/maps.py
└── utils/generic_threader.py

apps/
├── streamlit/                     # Python/PyDeck interactive app
└── mapbox/                        # Vanilla JS + static GeoJSON (no server required)
                                   #   Views: POINTS (stress), COUNTRIES, ROADS (road threat)

scripts/                           # Data processing and export (run once)
                                   #   incl. fetch_road_data.py, export_road_threats.py
tests/                             # 24 unit test files + e2e/ (Playwright)
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

# E2E tests (Mapbox)
npx playwright test --config=playwright.mapbox.config.ts
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
