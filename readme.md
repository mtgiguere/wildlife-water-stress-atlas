# Wildlife Water Stress Atlas

A geospatial decision-support platform that models wildlife survival risk
as a function of freshwater access and environmental pressure.

---

## What It Does

Maps water stress for wildlife populations by computing the distance from
species occurrence records to the nearest accessible water source, scoring
that distance against species-specific thresholds, and visualizing the
results on an interactive map with a temporal year slider.

The current focus is African elephants (*Loxodonta africana*) across the
African continent, using a multi-source water layer that includes rivers,
wetlands, pans, floodplains, saline lakes, and seasonal surface water.

This is Phase 1 of a three-phase system:
1. **Describe** — current water stress and temporal occurrence patterns (working)
2. **Predict** — how water availability changes with climate (planned)
3. **Prescribe** — conservation intervention zones and refuge viability (planned)

---

## The Streamlit App

An interactive web app built with Streamlit and PyDeck allows users to:
- Watch **21,900 elephant occurrence records** across Africa using a year slider (2005–2026)
- See the **COVID-19 dip in 2020** — field researchers couldn't access sites, reflected in the data
- Explore water sources including rivers, wetlands, pans, and floodplains
- View per-year record counts and total dataset stats

Run locally:
```bash
streamlit run apps/streamlit/streamlit_app.py
```

---

## The Analysis Pipeline

The core library computes water stress scores for any species:
- Fetches occurrence records from GBIF (21,900+ elephant records, paginated)
- Loads water sources from multiple datasets via a normalized schema
- Scores each occurrence by distance to nearest accessible water
- Aggregates to a 50km grid for visualization

The phantom thirst bug is fixed — elephants near Etosha Pan (Namibia) and
Makgadikgadi/Sua Pan (Botswana) previously appeared falsely stressed because
those water sources weren't in the data. GLWD v2 now correctly captures them.

---

## Water Data Sources

| Source | Type | What It Adds |
|---|---|---|
| Natural Earth rivers | Shapefile (lines) | River network — lines for distance calc accuracy |
| GLWD v2 | GeoTIFF (raster) | Wetlands, pans, floodplains, saline lakes |
| JRC Global Surface Water | GeoTIFF tiles | Seasonal and ephemeral surface water |
| GBIF API | REST API | Species occurrence records (paginated, cached) |

GLWD v2 is the Global Lakes and Wetlands Database version 2 (Lehner et al.,
2025), distributed under Creative Commons Attribution 4.0. It classifies
inland water into 33 types at 500m resolution.

---

## Architecture

**Species config is a single source of truth.**
`config/species.py` holds all species-specific parameters. Adding a new
species (zebras, lions, salamanders) means adding one dict entry. No other
code changes.

**Water sources share a normalized schema.**
Every source class produces the same columns: `geometry`, `source_id`,
`water_type`, `mechanism`, `permanence`, `reliability`, `months_water`,
`region`. All source types are interchangeable downstream.

**The app is layered for multiple audiences.**
apps/
streamlit/   ← public web app, browser-optimized
qgis/        ← planned researcher plugin, full resolution

The core library knows nothing about either — it's consumed by both.

**Data gaps are insights, not failures.**
GBIF records include imprecise coordinates, historical specimens, and
potentially captive animals alongside wild GPS-tracked individuals.
These are intentionally preserved — gaps surface funding needs and
highlight understudied populations. The 2020 COVID dip is visible in
the year slider — that's a story worth telling.

---

## Running Locally

```bash
# Install dependencies
pip install -e .

# Run the Streamlit app
streamlit run apps/streamlit/streamlit_app.py

# Run the analysis pipeline (matplotlib static map)
python scripts/plot_elephants.py
```

Data files are not committed to git (too large). Required files:
- `data/raw/water/glwd/GLWD_v2_0_main_class.tif` — HydroSHEDS GLWD v2
- `data/raw/water/rivers/ne_10m_rivers_lake_centerlines_scale_rank.shp` — Natural Earth
- `data/raw/water/jrc_gsw/` — JRC Global Surface Water tiles (Africa)
- `data/processed/gbif_loxodonta_africana.gpkg` — cached GBIF records (built on first run)
- `data/processed/water_africa.gpkg` — cached water layer (built on first run)
- `data/processed/water_africa_simplified.gpkg` — browser-optimized water layer (built on first run)

---

## Development

Strict TDD — tests written before implementation, always.

```bash
# Run unit tests
pytest

# Run integration tests (requires real data files)
pytest -m integration

# Lint and format
ruff check . --fix
ruff format .

# E2E tests (requires Streamlit app running on localhost:8501)
# Run in standalone PowerShell with Node.js v22
npx playwright test
```

**Test coverage: 230 unit tests + 14 Playwright E2E tests, 100% unit coverage**

---

## Project Status

| Component | Status |
|---|---|
| Species config registry | ✅ Done |
| Water source class architecture | ✅ Done |
| GLWD v2 integration (wetlands, pans, floodplains) | ✅ Done |
| JRC Global Surface Water (Africa tiles) | ✅ Done |
| Phantom thirst bug (Etosha, Botswana pans) | ✅ Fixed |
| GBIF pagination (21,900 records) | ✅ Done |
| GBIF occurrence caching | ✅ Done |
| Streamlit web app with year slider | ✅ Done |
| PyDeck interactive map (Voyager basemap) | ✅ Done |
| CI/CD pipeline (GitHub Actions) | ✅ Done |
| Playwright E2E tests (14 tests) | ✅ Done |
| 100% unit test coverage | ✅ Done |
| Species animal icons on map | 🔧 In progress |
| Deploy to Streamlit Community Cloud | 📋 Next |
| Year distribution chart (COVID story) | 📋 Next |
| Auto-play animation | 📋 Next |
| Species selector dropdown | 📋 Next |
| Data confidence layer | 📋 Planned |
| QGIS plugin | 📋 Planned |
| Human pressure layer (roads, fences) | 📋 Planned |
| Phase 2 — Predict (climate modeling) | 📋 Future |
| Phase 3 — Prescribe (intervention zones) | 📋 Future |

---

## Citation

If using GLWD v2 data, please cite:

Lehner, B., et al. (2025). Mapping the world's inland surface waters: an
upgrade to the Global Lakes and Wetlands Database (GLWD v2). Earth System
Science Data. https://doi.org/10.6084/m9.figshare.28519994