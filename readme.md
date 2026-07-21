# Wildlife Water Stress Atlas

A geospatial decision-support platform that models wildlife survival risk
as a function of freshwater access and environmental pressure across Africa.

> 🐸 **Are you an ecologist who wants to add a species or a stressor?**
> Start with **[docs/USER_GUIDE.md](docs/USER_GUIDE.md)** — a plain-language guide
> to how it works, how to add your animal/pressure as a simple file (no coding),
> and exactly what the algorithm does with your numbers.

---

## What It Does

Maps water stress for wildlife populations by computing the distance from
species occurrence records to the nearest accessible water source, scoring
that distance against species-specific thresholds, and visualizing the
results on an interactive map with a temporal year slider and species selector.

Eleven African species are currently tracked, spanning four ecological tiers:

| Tier | Species | Why It Matters |
|---|---|---|
| Megafauna anchor | 🐘 African Elephant | Largest land animal, 150–300L/day, ecosystem engineer |
| Megafauna anchor | 🦛 Hippopotamus | Near-crocodile-tier water obligate — skin desiccates without immersion |
| Large herbivores | 🦓 Plains Zebra | Mass migration tracks seasonal water |
| Large herbivores | 🦒 Giraffe | Vulnerable IUCN — sparse records tell the story |
| Large herbivores | 🐃 Cape Buffalo | Dry-season indicator — contracts range to permanent water |
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
- **Searchable, realm-grouped species selector** in the sidebar (scales as species are added)
- A **time scrubber** across the top (play + Slow/Med/Fast) that defaults to the **last full year of data**
- ⬤ **Points view** — occurrence dots coloured by water stress (green→yellow→red; a 0-stress animal stays green so the animal is always visible), with clustering at low zoom
- ▦ **Countries view** — choropleth shaded by record count per country per year
- ⚠ **Roads view** — occurrences coloured by road threat (proximity to the nearest major road, weighted by species road-sensitivity), over an amber backbone road network. Reed frogs light up beside motorways; flamingos stay dark (they fly — immune)
- 🏘 **Settlements view** — occurrences coloured by settlement threat (proximity to the nearest city/town, weighted by species settlement-sensitivity), over violet city & town points. Lions blaze near settlements (retaliatory killing); flamingos stay dark
- ⚑ **STRESS view** — occurrences coloured by **cumulative** stress (noisy-OR of every stressor), with a **Colour by** toggle (Total or any single stressor) and live **Scenario** controls: include/exclude a stressor or slide its weight (0–100%) and watch the map re-aggregate instantly — the "what if we mitigate roads?" lens. Controls are generated from each species' stressor list, not hardcoded
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
python scripts/fetch_road_data.py             # download OSM roads + settlements from Geofabrik in one pass (run once)
python scripts/export_road_threats.py         # export per-species road threat + backbone roads
python scripts/export_settlement_threats.py   # export per-species settlement threat + city/town points
cd apps/mapbox
python -m http.server 3000
# Open http://localhost:3000
```

---

## The Streamlit App

Live: **https://wildlife-water-stress-atlas-ngvdrwg2yhzekplfeq6nvd.streamlit.app**

An interactive web app built with Streamlit and PyDeck allows users to:
- Select any of 11 species from the sidebar dropdown
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

**One generic, kind-aware scoring engine.** Every stressor — water, roads,
settlements, and any future one — is scored by a single engine, not per-stressor
functions. A stressor has a **kind** that owns its math: *hazard* (closer = worse,
e.g. roads/settlements), *resource* (farther = worse, e.g. water), or *ambient*
(a measured value, no distance). Per-stressor scores are combined into one
comparable 0–1 cumulative score via **noisy-OR** (`1 − ∏(1 − sᵢ)`), and scores
carry **coverage** so "no data" is never a fake zero. See
[`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) for the ecologist-facing explanation
and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the design.

**Analytics modules:**
- `analytics/stressors.py` — `StressorKind` + the reference scorers
  (`HazardStressor`/`ResourceStressor`/`AmbientStressor`) and `aggregate_stress`
  (noisy-OR over covered scores)
- `analytics/stress_engine.py` — the query-shaped engine: `score_stressor(...)` /
  `score_species_stress(species, measurements)` → per-stressor breakdown + cumulative
- `analytics/overlap.py` — distance from each occurrence to nearest water / road /
  settlement, all via the indexed `sjoin_nearest`
- `analytics/water_access.py` — species-specific water-type filtering
- `analytics/scoring.py` — `classify_stress_level()` (score → low/moderate/high label)
- `analytics/spatial.py` — aggregates point scores to a 50km grid
- `analytics/trends.py` — linear-regression trend analytics, baked into exported GeoJSON

Stressor **types** and **species** are plugins (`config/stressor_plugins/*.json`,
`config/species_plugins/*.json`) — adding either is one JSON file, no code. The
export scripts (`export_stress.py`, `export_road_threats.py`, …) all score through
the same engine.

**Phantom thirst — the honest water story.** Distance-to-water is only as good as
the water map. Elephants near Etosha/Makgadikgadi pans were once falsely stressed
until GLWD v2 added those pans; more recently, *obligate-aquatic* species (hippos,
crocodiles) read as ~14 km from "mapped" water because the river network was too
coarse. Adding **HydroRIVERS** (~1.5M African segments) collapsed hippo water-stress
from ~53% high to ~3.5% — while leaving genuinely water-independent species (lion,
cheetah, elephant) untouched. Residual amphibian stress reflects small wetlands no
dataset fully captures — a real gap, surfaced honestly, not hidden.

---

## Data Sources

| Source | Type | What It Adds |
|---|---|---|
| HydroRIVERS v10 (HydroSHEDS) | File Geodatabase (lines) | Dense river network (~1.5M African segments) — the accuracy that stops obligate-aquatic species reading as far from water |
| Natural Earth rivers | Shapefile (lines) | Coarse river centerlines (legacy; superseded by HydroRIVERS for scoring) |
| Natural Earth countries | Shapefile (polygons) | Country boundaries for choropleth aggregation |
| GLWD v2 | GeoTIFF (raster) | Wetlands, pans, floodplains, saline lakes |
| JRC Global Surface Water | GeoTIFF tiles | Seasonal and ephemeral surface water |
| GBIF API | REST API | Species occurrence records (paginated, cached) |
| Geofabrik / OpenStreetMap | GeoPackage (`.gpkg.zip`) | Major roads AND settlements (cities/towns/villages/hamlets) across 26 African countries — the human pressure layers, both extracted from one download pass |

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

**Species and stressors are file plugins.**
Each species is a JSON file in `config/species_plugins/`; each stressor *type* is
a JSON file in `config/stressor_plugins/`. `config/species.py` discovers and
validates them at import, exposing the registry. Adding a species or a stressor of
an existing kind is **one JSON file, no code** — see
[`docs/USER_GUIDE.md`](docs/USER_GUIDE.md).

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
  fetch_road_data.py            ← downloads OSM major roads from Geofabrik,
                                   merges data/raw/threats/africa_roads.gpkg
  export_road_threats.py        ← per-species road-threat GeoJSON + simplified
                                   backbone road network for the ROADS view
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

# Fetch OSM roads + settlements (Geofabrik, one download pass) + export threat layers (run once)
python scripts/fetch_road_data.py
python scripts/export_road_threats.py
python scripts/export_settlement_threats.py

# Run the Mapbox app
cd apps/mapbox && python -m http.server 3000

# Run the Streamlit app
streamlit run apps/streamlit/streamlit_app.py

# Run the analysis pipeline (matplotlib static map)
python scripts/plot_elephants.py
```

Data files are not committed to git (too large). Required files:
- `data/raw/water/glwd/GLWD_v2_0_main_class.tif` — HydroSHEDS GLWD v2
- `data/raw/water/rivers/HydroRIVERS_v10_af.gdb/` — HydroRIVERS Africa (dense river network; from hydrosheds.org)
- `data/raw/water/rivers/ne_10m_rivers_lake_centerlines_scale_rank.shp` — Natural Earth rivers (legacy)
- `data/raw/countries/ne_110m_admin_0_countries.shp` — Natural Earth countries (choropleth)
- `data/raw/water/jrc_gsw/` — JRC Global Surface Water tiles (Africa)
- `data/processed/gbif_*.gpkg` — cached GBIF records per species (built by prefetch_gbif.py)
- `data/processed/water_africa.gpkg` — cached water layer (built on first run)
- `data/processed/water_africa_simplified.gpkg` — browser-optimized water layer (built on first run)
- `data/raw/threats/africa_roads.gpkg` — merged OSM major roads (built by fetch_road_data.py)
- `data/raw/threats/africa_settlements.gpkg` — merged OSM settlements (built by fetch_road_data.py, same pass)

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

# WebGL visual guards (renders the Mapbox app via software WebGL / SwiftShader
# and asserts layers actually PAINT — the road backbone, settlement points, and
# the STRESS dots incl. the scenario recolor — guarding the invisible-render bug
# class). Auto-starts the static server.
npx playwright test --config=playwright.visual.config.ts
```

**Test coverage: ~760 unit tests (99% coverage) + 57 Mapbox DOM E2E + 8 SwiftShader
visual guards + 16 Streamlit E2E + a real-Geofabrik download integration test.
Correctness-critical modules (scoring, validation) also get periodic mutation
audits — see `docs/TDD_CONTRACT.md` ("Green ≠ Verified").**

> Note: two bug classes escape the unit/DOM suites — external-format assumptions
> (e.g. a data source's layer name) and WebGL visual rendering. Both are now
> guarded by reality-dependent tests that run on demand (not in CI):
> `tests/test_fetch_road_data_integration.py` pulls one small real Geofabrik
> country, and `tests/e2e/test_mapbox_visual.spec.ts` renders the map via
> software WebGL and asserts on pixels. See `docs/TDD_CONTRACT.md` (road-threat addendum).

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
| Species selector dropdown (11 species) | ✅ Done |
| PyDeck dark map with species icons | ✅ Done |
| Hero banner + dark theme | ✅ Done |
| Playwright E2E tests (16 tests) | ✅ Done |
| ~99% unit test coverage | ✅ Done |
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
| Icon clustering at low zoom | ✅ Done |
| Add Hippo + Buffalo (11 species) | ✅ Done |
| Water stress visualization (POINTS colored by stress) | ✅ Done |
| Human pressure layer — roads (ingest → scoring → export) | ✅ Done |
| Road threat visualization (⚠ ROADS view) | ✅ Done |
| Integration test for roads download (external-format guard) | ✅ Done |
| Visual smoke test via software WebGL (render guard) | ✅ Done |
| Human pressure layer — settlements (ingest → scoring → export) | ✅ Done |
| Settlement threat visualization (🏘 SETTLEMENTS view) | ✅ Done |
| Generic kind-aware scoring engine + noisy-OR aggregation (cutover) | ✅ Done |
| Species & stressor **types** as JSON plugins | ✅ Done |
| ⚑ STRESS view — cumulative stress + per-stressor "colour by" | ✅ Done |
| Scenario tools — include/exclude + weight a stressor, live re-aggregate | ✅ Done |
| UI overhaul — time scrubber, searchable/grouped species, 0=green dots | ✅ Done |
| HydroRIVERS water accuracy (obligate-aquatic false-red fixed) | ✅ Done |
| Ecologist guide (`docs/USER_GUIDE.md`) | ✅ Done |
| Mutation-testing audit of scoring + validation | ✅ Done |
| Full continental settlement fetch (settlement dimension) | 📋 Planned |
| Multi-species compare mode | 📋 Planned |
| Data confidence layer (surface coverage on the map) | 📋 Planned |
| MapLibre + PMTiles (drop Mapbox token; scale data delivery) | 📋 Planned |
| QGIS plugin | 📋 Planned |
| Human pressure — fences | 📋 Blocked (no reliable continental fence dataset) |
| Phase 2 — Predict (climate modeling) | 📋 Future |
| Phase 3 — Prescribe (intervention zones) | 📋 Future |

---

## Citation

If using GLWD v2 data, please cite:

Lehner, B., et al. (2025). Mapping the world's inland surface waters: an
upgrade to the Global Lakes and Wetlands Database (GLWD v2). Earth System
Science Data. https://doi.org/10.6084/m9.figshare.28519994
