# Wildlife Water Stress Atlas

A geospatial decision-support platform that models wildlife survival risk
as a function of freshwater access and environmental pressure across Africa.

---

## What It Does

Maps water stress for wildlife populations by computing the distance from
species occurrence records to the nearest accessible water source, scoring
that distance against species-specific thresholds, and visualizing the
results on an interactive map with a temporal year slider and species selector.

Nine African species are currently tracked, spanning four ecological tiers:

| Tier | Species | Why It Matters |
|---|---|---|
| Megafauna anchor | 🐘 African Elephant | Largest land animal, 150–300L/day, ecosystem engineer |
| Large herbivores | 🦓 Plains Zebra | Mass migration tracks seasonal water |
| Large herbivores | 🦒 Giraffe | Vulnerable IUCN — sparse records tell the story |
| Carnivores | 🦁 Lion | Follows prey which follows water |
| Carnivores | 🐆 Cheetah | Wide range, low direct water dependency |
| Sensitive indicators | 🐊 Nile Crocodile | Permanent water obligate — if crocs are gone, the river is gone |
| Sensitive indicators | 🦩 Greater Flamingo | Saline lake specialist — extreme habitat specificity |
| Sensitive indicators | 🐸 Painted Reed Frog | Amphibian canary — first to vanish when wetlands shrink |
| Sensitive indicators | 🐸 African Clawed Frog | Most studied African amphibian, huge GBIF dataset |

Switching between species in the sidebar reveals the contrast between
resilient megafauna and sensitive indicator species — elephants distributed
broadly, reed frogs clustered tightly around remaining wetlands. That
progression is the funding conversation.

This is Phase 1 of a three-phase system:
1. **Describe** — current water stress and temporal occurrence patterns (working)
2. **Predict** — how water availability changes with climate (planned)
3. **Prescribe** — conservation intervention zones and refuge viability (planned)

---

## The Mapbox App

Live: **https://mtgiguere.github.io/wildlife-water-stress-atlas/**

A high-performance interactive web app built with Mapbox GL JS. All rendering
happens client-side via WebGL — no server, no payload limits, instant response.

Features:
- Select any of 9 species from the sidebar
- ⬤ **Points view** — occurrence dots with animated year slider and autoplay (Slow/Med/Fast)
- ▦ **Countries view** — choropleth shaded by record count per country per year
- Click any country → **trend chart** slides up with linear regression, slope, r², and INCREASING/STABLE/DECLINING classification
- Dark Mapbox basemap with blue water network (rivers, wetlands, pans, floodplains)
- COVID-19 dip annotation — 2020 record drop reflects field access disruption
- Fly-to-Africa animation on species switch
- Per-year and total record counts, tooltips on hover

**Why Mapbox over Streamlit:** The Streamlit Community Cloud app was hitting
payload size limits shipping raw GeoJSON from a Python server to the browser
on every interaction. Mapbox GL JS renders everything on the client GPU —
same data, zero server overhead, instant filtering. The GeoJSON files are
pre-exported once and served as static assets.

Run locally:
```bash
python scripts/export_mapbox_data.py          # export occurrence + water GeoJSON (run once)
python scripts/export_country_aggregates.py   # export country counts with trend data (run once)
cd apps/mapbox
python -m http.server 3000
# Open http://localhost:3000
```

---

## The Streamlit App

Live: **https://wildlife-water-stress-atlas-ngvdrwg2yhzekplfeq6nvd.streamlit.app**

An interactive web app built with Streamlit and PyDeck allows users to:
- Select any of 9 species from the sidebar dropdown
- Watch occurrence records shift across Africa using a year slider
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
- Fetches occurrence records from GBIF (paginated, cached to GeoPackage)
- Loads water sources from multiple datasets via a normalized schema
- Scores each occurrence by distance to nearest accessible water
- Aggregates to a 50km grid for visualization

**Analytics modules:**
- `analytics/overlap.py` — distance from each occurrence to nearest water source
- `analytics/scoring.py` — water stress score (0–1) per occurrence
- `analytics/water_access.py` — species-specific water type filtering
- `analytics/spatial.py` — aggregates point scores to 50km grid
- `analytics/trends.py` — `compute_linear_regression()`, `classify_trend()`, `get_country_time_series()`, `add_trends_to_country_counts()`. Trend regression is computed in the Python pipeline and baked into exported GeoJSON — slope, r², and trend classification are pre-computed, not computed at runtime in the browser.

The phantom thirst bug is fixed — elephants near Etosha Pan (Namibia) and
Makgadikgadi/Sua Pan (Botswana) previously appeared falsely stressed because
those water sources weren't in the data. GLWD v2 now correctly captures them.

---

## Data Sources

| Source | Type | What It Adds |
|---|---|---|
| Natural Earth rivers | Shapefile (lines) | River network — lines for distance calc accuracy |
| Natural Earth countries | Shapefile (polygons) | Country boundaries for choropleth aggregation |
| GLWD v2 | GeoTIFF (raster) | Wetlands, pans, floodplains, saline lakes |
| JRC Global Surface Water | GeoTIFF tiles | Seasonal and ephemeral surface water |
| GBIF API | REST API | Species occurrence records (paginated, cached) |

GLWD v2 is the Global Lakes and Wetlands Database version 2 (Lehner et al.,
2025), distributed under Creative Commons Attribution 4.0. It classifies
inland water into 33 types at 500m resolution.

**Why GBIF?** GBIF — the Global Biodiversity Information Facility — is
government-funded intergovernmental infrastructure used by IUCN for Red List
assessments. More than 6 peer-reviewed papers per day cite GBIF data.

**The honest caveat:** Record counts increase over time not because animal
populations are booming, but because data collection has grown. The COVID-19
dip in 2020 is visible in the year slider — field researchers couldn't access
sites. Data gaps are insights, not errors. The linear regression trend in the
country chart reflects observation effort as much as ecological signal — this
is surfaced explicitly via the r² value.

---

## Architecture

**Species config is a single source of truth.**
`config/species.py` holds all species-specific parameters. Adding a new
species means adding one dict entry — no other code changes.

**Water sources share a normalized schema.**
Every source class produces the same columns: `geometry`, `source_id`,
`water_type`, `mechanism`, `permanence`, `reliability`, `months_water`,
`region`. All source types are interchangeable downstream.

**The app is layered for multiple audiences.**
```
apps/
  streamlit/   ← public web app, Python/PyDeck
  mapbox/      ← high-performance web app, Mapbox GL JS + static GeoJSON
  qgis/        ← planned researcher plugin, full resolution
scripts/
  export_mapbox_data.py         ← exports occurrence + water GeoJSON from .gpkg
  export_country_aggregates.py  ← spatial join to Natural Earth countries,
                                   aggregates by country + year, runs linear
                                   regression, bakes slope/r2/trend into GeoJSON
```

**Pipeline philosophy — static pre-computation:**
Country aggregation and trend regression are computed once in Python and
exported to static GeoJSON. The frontend reads pre-computed fields directly.
No server, no runtime computation. When GBIF data updates, re-run the export
scripts. A scheduled GitHub Actions job can automate this in Phase 2.

**Data gaps are insights, not failures.**
GBIF records include imprecise coordinates, historical specimens, and
potentially captive animals alongside wild GPS-tracked individuals.
These are intentionally preserved — gaps surface funding needs and
highlight understudied populations.

---

## Running Locally

```bash
# Install dependencies
pip install -e .

# Pre-fetch GBIF occurrence data for all species (run once)
python scripts/prefetch_gbif.py

# Export GeoJSON for Mapbox app (run once, or after adding species)
python scripts/export_mapbox_data.py

# Export country-level aggregates with trend data (run once, or after adding species)
python scripts/export_country_aggregates.py

# Run the Mapbox app
cd apps/mapbox && python -m http.server 3000

# Run the Streamlit app
streamlit run apps/streamlit/streamlit_app.py

# Run the analysis pipeline (matplotlib static map)
python scripts/plot_elephants.py
```

Data files are not committed to git (too large). Required files:
- `data/raw/water/glwd/GLWD_v2_0_main_class.tif` — HydroSHEDS GLWD v2
- `data/raw/water/rivers/ne_10m_rivers_lake_centerlines_scale_rank.shp` — Natural Earth rivers
- `data/raw/countries/ne_110m_admin_0_countries.shp` — Natural Earth countries (choropleth)
- `data/raw/water/jrc_gsw/` — JRC Global Surface Water tiles (Africa)
- `data/processed/gbif_*.gpkg` — cached GBIF records per species (built by prefetch_gbif.py)
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

**Test coverage: 299 unit tests + 16 Playwright E2E tests, 100% unit coverage**

---

## Project Status

| Component | Status |
|---|---|
| Species config registry | ✅ Done |
| Water source class architecture | ✅ Done |
| GLWD v2 integration (wetlands, pans, floodplains) | ✅ Done |
| JRC Global Surface Water (Africa tiles) | ✅ Done |
| Phantom thirst bug (Etosha, Botswana pans) | ✅ Fixed |
| GBIF pagination | ✅ Done |
| GBIF occurrence caching | ✅ Done |
| Bulk GBIF prefetch script | ✅ Done |
| Streamlit web app with year slider | ✅ Done |
| Species selector dropdown (9 species) | ✅ Done |
| PyDeck dark map with species icons | ✅ Done |
| Hero banner + dark theme | ✅ Done |
| Playwright E2E tests (16 tests) | ✅ Done |
| 100% unit test coverage | ✅ Done |
| Deploy to Streamlit Community Cloud | ✅ Live |
| Year distribution chart (COVID story) | ✅ Done |
| CI/CD pipeline (GitHub Actions) | ✅ Done |
| Mapbox GL JS app (WebGL, client-side rendering) | ✅ Done |
| GeoJSON export pipeline (gpkg → static assets) | ✅ Done |
| Deploy to GitHub Pages | ✅ Live |
| Auto-play animation with speed controls | ✅ Done |
| Fly-to-Africa on species switch | ✅ Done |
| Country choropleth view (Natural Earth spatial join) | ✅ Done |
| Linear regression trend analytics (core library, TDD) | ✅ Done |
| Country trend chart (click country → slide-up chart) | ✅ Done |
| Icon clustering at low zoom | 📋 Next |
| Multi-species overlay mode | 📋 Planned |
| Add Hippo + Buffalo | 📋 Planned |
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
