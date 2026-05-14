Source classes:
- `ShapefileRivers` — Natural Earth rivers (line geometries)
- `ShapefileLakes` — Natural Earth lakes (polygon geometries) — RETIRED, replaced by GLWD class 1
- `GLWDWetlands` — GLWD v2 raster, vectorizes requested classes
- `JRCGlobalSurfaceWater` — JRC GSW raster, vectorizes by occurrence threshold

Registry function: `load_all_water(config, bbox=None, month=None)`
- `bbox` is optional but warns loudly when absent — global rasters will exhaust RAM
- `month` is accepted by all sources but not yet implemented (Phase 2)

`WaterMechanism` enum: `PERMANENT_SURFACE`, `SEASONAL_SURFACE`, `GROUNDWATER`, `ARTIFICIAL`, `DERIVED`, `RAINFALL_DERIVED`

Convenience functions `load_rivers()` and `load_lakes()` preserved for simple single-source use.

**`analytics/overlap.py`**
Computes distance from each occurrence to nearest water source.
- `add_distance_to_water(occurrences, water)` → GeoDataFrame with `distance_to_water` column
- Reprojects to EPSG:3857 for metric accuracy, returns in EPSG:4326

**`analytics/scoring.py`**
Stress scoring. Reads `water_threshold_m` from `SPECIES_CONFIG`.
- `water_stress_score(distance_meters, species)` → float 0–1
- `classify_stress_level(score)` → "low" | "moderate" | "high"

**`analytics/water_access.py`**
Species-specific filtering. Reads from `SPECIES_CONFIG`.
- `filter_accessible_water(water, species)` → filtered GeoDataFrame
- `get_water_type_weights(species)` → dict

**`analytics/apply.py`**
Clean dependency-injection pattern. No species names hardcoded. No changes needed.

**`analytics/spatial.py`**
Aggregates point-level stress scores into a grid.
- `aggregate_stress_to_grid(gdf, cell_size_meters)` → GeoDataFrame of grid cells

**`analytics/trends.py`** ← NEW
Linear regression trend analysis for country-level occurrence counts.
- `compute_linear_regression(year_counts)` → `{slope, intercept, r2}`. Pure Python, no numpy/scipy dependency. Guards for empty input and single data point (returns zeros).
- `classify_trend(slope)` → `"increasing"` | `"stable"` | `"declining"`. Uses `STABLE_THRESHOLD = 0.5` records/year — heuristic placeholder, ecological validation needed in Phase 2.
- `get_country_time_series(data, iso_a3)` → list of records for one country, sorted by year ascending.
- `add_trends_to_country_counts(data)` → adds `slope`, `r2`, `trend` fields to every record. Called by `export_country_aggregates.py` to bake regression into GeoJSON at export time — not computed at runtime in the browser.

**`scripts/plot_elephants.py`**
Main pipeline entry point. Uses `load_all_water()` with `WATER_CONFIG` dict. Species name in single `SPECIES` constant at top of file. Africa bbox `(-20, -40, 55, 40)` passed to all water sources.

**`scripts/prefetch_gbif.py`**
Bulk GBIF prefetch script. Loops through all species in `SPECIES_CONFIG` and pre-populates cache files in `data/processed/`. Run once after adding new species. Supports `--species` flag for single species fetch and `--force` flag to re-fetch existing cache files.

**`scripts/export_mapbox_data.py`** ← NEW
Exports data for the Mapbox app:
- `export_water(input_path, output_path)` — water_africa_simplified.gpkg → water.geojson
- `export_occurrences(input_path, output_path)` — per-species gpkg → occurrences_gbif_{species}.geojson. Keeps only `species`, `year`, `geometry` columns.
- `export_species_config(output_path)` — SPECIES_CONFIG → species_config.json (sets serialized to lists)
- `export_all(data_dir, output_dir)` — orchestrates all three for all species

**`scripts/export_country_aggregates.py`** ← NEW
Spatial join pipeline for the choropleth view:
- `load_countries(path)` — loads Natural Earth 110m country shapefile, keeps `NAME`, `ISO_A3`, `CONTINENT`, `geometry`
- `join_occurrences_to_countries(occurrences, countries)` — GeoPandas spatial join (within), left join so ocean points get null country
- `aggregate_by_country_year(joined)` — groups by NAME + ISO_A3 + year, counts records, filters to Africa only
- `export_country_counts(scientific_name, data_dir, output_dir, countries_path)` — orchestrates load → join → aggregate → add_trends → write JSON
- `export_all_country_counts(data_dir, output_dir, countries_path)` — loops all species in SPECIES_CONFIG

Output format: `[{NAME, ISO_A3, year, count, slope, r2, trend}, ...]` — trends baked in at export time.

TODO Phase 2: When GBIF data goes live on a schedule, wrap export scripts in GitHub Actions cron job. Frontend requires zero changes.

**`apps/streamlit/streamlit_app.py`**
Main Streamlit app. Intentionally thin — orchestrates components only.
Now includes:
- `load_water_layer_simplified()` — loads browser-optimized water layer
- `load_gbif_data(species, year)` — loads GBIF cache for any species in SPECIES_CONFIG
- `render_sidebar()` — species selector + year slider + stats, returns `(selected_species, selected_year)`
- `build_water_layer()` / `build_occurrences_layer(icon_path)` / `build_deck()` — PyDeck map
- `st.bar_chart(get_year_counts(all_occurrences))` — year distribution chart
- Stats row: Species Records, Total Records, Water Sources Mapped
- Data quality note + citations
- Dark theme + hero banner (elephants_waterhole.jpeg)
- `st.session_state` for species selection persistence across reruns

**`apps/mapbox/index.html`** ← NEW
Single-file Mapbox GL JS app. Dark aesthetic (Bebas Neue + DM Sans fonts, cyan accent on near-black).
Features:
- ⬤ POINTS view — circle layers with glow effect, year slider, autoplay (▶/⏸, Slow/Med/Fast)
- ▦ COUNTRIES view — choropleth using Natural Earth GeoJSON from GitHub CDN. Intensity interpolated 0→1 per year. Country click → trend chart slide-up panel.
- Trend chart — pure Canvas 2D API (no library). Draws raw data line (cyan), trend line (dashed, color-coded by trend classification), grid lines, axis labels.
- Tooltip — updates on mousemove across country borders (not just mouseenter), so switching from Tanzania to Kenya updates immediately.
- Fly-to-Africa on species switch — `map.flyTo({center:[20,0], zoom:3, duration:1200})`
- COVID-19 annotation panel — appears only when year === 2020
- Loading overlay with animated progress bar

### Current Data Sources
| Layer | File | Source | Format | Notes |
|---|---|---|---|---|
| Rivers | ne_10m_rivers_lake_centerlines_scale_rank.shp | Natural Earth | Shapefile | Line geometries — kept for distance calc accuracy |
| Countries | ne_110m_admin_0_countries.shp | Natural Earth | Shapefile | 110m scale, Africa filter in aggregate step |
| GLWD v2 | GLWD_v2_0_main_class.tif | HydroSHEDS | GeoTIFF | 33 classes, 500m resolution |
| JRC GSW | occurrence_*_v1_4_2021.tif | JRC / Google | GeoTIFF tiles | Africa tiles downloading |
| Species occurrences | GBIF API (live) | GBIF | API / GeoDataFrame | All species in SPECIES_CONFIG |

Natural Earth lakes retired — replaced by GLWD class 1 (freshwater lake).

### GBIF Credibility — Pinned Answer
**Why GBIF?** GBIF — the Global Biodiversity Information Facility — is government-funded intergovernmental infrastructure (same tier as UN). IUCN publishes Red List data through GBIF — our occurrence data and their Endangered/Vulnerable classifications come from the same ecosystem. More than 6 peer-reviewed papers per day cite GBIF data.

**The honest caveat (important for interviews):** Record counts increase over time not because animal populations are booming, but because data collection has grown. Spatial clustering bias persists even after cleaning — only 6.74% of the globe has been sampled, with disproportionately poor tropical coverage. Our platform treats data gaps as insights: the COVID-19 dip in 2020, funding cycles, and field access limits are all visible signals worth surfacing, not hiding. The r² value in the trend chart makes this bias explicit — r²=0.26 means year explains only 26% of the variance; the rest is observation effort.

**Interview talking point:** "We chose GBIF because it's the same data source IUCN uses for Red List assessments. But we're explicit about its limitations — record counts increase over time not because animal populations are booming, but because data collection has grown. Our platform treats data gaps as insights, not errors."

### GLWD v2 Class Map
The full 33-class schema. Classes used by the pipeline:

| Class | Name | water_type | mechanism | permanence | reliability | months_water |
|---|---|---|---|---|---|---|
| 1 | Freshwater lake | lake | PERMANENT_SURFACE | permanent | 1.0 | 12 |
| 2 | Saline lake | saline_lake | PERMANENT_SURFACE | permanent | 0.4 | 12 |
| 4 | Large river | river | PERMANENT_SURFACE | permanent | 1.0 | 12 |
| 6 | Other permanent waterbody | permanent_water | PERMANENT_SURFACE | permanent | 0.9 | 12 |
| 8 | Lacustrine, forested | wetland | SEASONAL_SURFACE | seasonal | 0.7 | 8 |
| 9 | Lacustrine, non-forested | wetland | SEASONAL_SURFACE | seasonal | 0.6 | 6 |
| 10 | Riverine, regularly flooded, forested | floodplain | SEASONAL_SURFACE | seasonal | 0.8 | 8 |
| 11 | Riverine, regularly flooded, non-forested | floodplain | SEASONAL_SURFACE | seasonal | 0.8 | 8 |
| 12 | Riverine, seasonally flooded, forested | floodplain | SEASONAL_SURFACE | seasonal | 0.7 | 6 |
| 13 | Riverine, seasonally flooded, non-forested | floodplain | SEASONAL_SURFACE | seasonal | 0.7 | 6 |
| 16 | Palustrine, regularly flooded, forested | wetland | SEASONAL_SURFACE | seasonal | 0.7 | 8 |
| 17 | Palustrine, regularly flooded, non-forested | wetland | SEASONAL_SURFACE | seasonal | 0.7 | 8 |
| 18 | Palustrine, seasonally saturated, forested | wetland | SEASONAL_SURFACE | seasonal | 0.5 | 4 |
| 19 | Palustrine, seasonally saturated, non-forested | wetland | SEASONAL_SURFACE | seasonal | 0.5 | 4 |
| 21 | Ephemeral, non-forested | pan | SEASONAL_SURFACE | ephemeral | 0.3 | 2 |
| 32 | Salt pan, saline/brackish wetland | pan | SEASONAL_SURFACE | seasonal | 0.5 | 4 |

Default water classes for elephants: `{2, 6, 8, 9, 10, 11, 12, 13, 16, 17, 18, 19, 21, 32}`
Classes 1 and 4 excluded from defaults — covered by Natural Earth with better geometry types.

### Current Test Coverage
**299 unit tests, 100% coverage**
**16 Playwright E2E tests — 16 passing, 0 pending** ✅
TDD strictly enforced — tests written before implementation on every change.

Test files:
- `test_species_config.py` — registry structure, field constraints, validation error branches
- `test_water_sources.py` — vector source classes, load_all_water, convenience functions
- `test_water_sources_raster.py` — GLWDWetlands and JRCGlobalSurfaceWater, all 16 GLWD classes
- `test_accessible_water.py` — filter_accessible_water, get_water_type_weights
- `test_overlap.py`, `test_scoring.py`, `test_apply.py`, `test_spatial.py` — analytics layer
- `test_gbif.py`, `test_water.py` — ingest layer
- `test_cache.py` — dynamic species caching, _cache_dir injection pattern
- `test_map.py` — IconLayer type, icon_data embedded in records, water layers
- `test_sidebar.py` — pure data functions (get_year_range, get_record_count, get_year_counts)
- `test_stats.py` — get_water_threshold_display()
- `test_trends.py` — compute_linear_regression, classify_trend, get_country_time_series, add_trends_to_country_counts (14 tests)
- `test_export_mapbox_data.py` — export_water, export_occurrences, export_species_config, export_all (12 tests)
- `test_export_country_aggregates.py` — load_countries, join_occurrences_to_countries, aggregate_by_country_year, export_country_counts, export_all_country_counts (9 tests)
- `test_water_real_data.py` — integration test, hits real filesystem, keep separated from CI fast runs

### Current Species Registry
All species in `SPECIES_CONFIG` with GBIF cache files:

| Species | Common Name | Emoji | Threshold | Dependency | Cache File | Records |
|---|---|---|---|---|---|---|
| Loxodonta africana | African Elephant | 🐘 | 300km | high | gbif_loxodonta_africana.gpkg | ~21,900 |
| Equus quagga | Plains Zebra | 🦓 | 150km | high | gbif_equus_quagga.gpkg | 22,235 |
| Giraffa camelopardalis | Giraffe | 🦒 | 80km | moderate | gbif_giraffa_camelopardalis.gpkg | 5,549 |
| Panthera leo | Lion | 🦁 | 200km | moderate | gbif_panthera_leo.gpkg | ~15,000 |
| Acinonyx jubatus | Cheetah | 🐆 | 250km | low | gbif_acinonyx_jubatus.gpkg | 8,508 |
| Crocodylus niloticus | Nile Crocodile | 🐊 | 10km | high | gbif_crocodylus_niloticus.gpkg | 9,134 |
| Phoenicopterus roseus | Greater Flamingo | 🦩 | 50km | high | gbif_phoenicopterus_roseus.gpkg | 99,900 |
| Hyperolius marmoratus | Painted Reed Frog | 🐸 | 2km | high | gbif_hyperolius_marmoratus.gpkg | ~TBC |
| Xenopus laevis | African Clawed Frog | 🐸 | 5km | high | gbif_xenopus_laevis.gpkg | ~TBC |

### What the Mapbox App Shows Right Now
- Dark Mapbox basemap (dark-v11)
- ⬤ POINTS view: Blue occurrence dots with glow, year slider (autoplay ▶/⏸), species selector
- ▦ COUNTRIES view: Choropleth (cyan intensity by record count), year slider updates choropleth
- Trend chart: Click country → slide-up panel with Canvas 2D line chart, trend line, slope/r²/classification badge
- Fly-to-Africa animation on species switch
- COVID-19 annotation (year 2020 only)
- Water network: rivers (lines) + wetlands/lakes/pans (polygons) from GLWD v2 + Natural Earth

### Mapbox App — Deployed URLs
- **GitHub Pages (live):** https://mtgiguere.github.io/wildlife-water-stress-atlas/
- **Local dev:** `cd apps/mapbox && python -m http.server 3000` → http://localhost:3000
- **Mapbox token:** URL-restricted to GitHub Pages + localhost. Public scopes only (no secret scopes). Safe to commit — URL restriction means token is useless outside those two origins.

---

## 4. Known Bugs and Gaps

### Bug: Phantom Thirst — FIXED ✅
GLWD v2 integrated. Etosha Pan (class 2), Makgadikgadi/Sua Pan (class 32) now captured.

### Bug: Playwright Chart Tests — FIXED ✅
Tests moved inside `test.describe` block so they receive the `beforeEach` navigation hook.

### Gap: Performance — Raster Vectorization is Slow
Caching implemented. `@st.cache_data` working.

### Gap: Icon Clustering at Low Zoom
When zoomed out to full Africa, dense occurrence clusters overlap. Mapbox GL JS has built-in clustering support — `cluster: true` on the GeoJSON source. Next feature to implement.

### Gap: Playwright E2E Tests Need Update for Mapbox App
No Playwright tests exist for the Mapbox app yet. The Streamlit tests cover the Streamlit app only.

### Gap: JRC GSW Multi-Tile Loading
JRCTileDirectory source class planned for multiple 10-degree tiles.

### Gap: export scripts lack `if __name__ == "__main__"` blocks
`export_mapbox_data.py` and `export_country_aggregates.py` are currently run via `python -c` one-liners. Should add main blocks so they're runnable as `python scripts/export_mapbox_data.py` directly.

---

## 5. Planned Refactoring / Next Steps

### Non-Negotiable Development Rules
- **Strict TDD**: tests written before code, always
- **CI/CD pipeline**: unit tests + linting + vulnerability scans minimum on every push
- **Never hardcode species names** anywhere in library code

1. **Icon clustering** — `cluster: true` on Mapbox occurrences source, cluster circle styling
2. **Add `__main__` blocks** to export scripts
3. **Playwright E2E for Mapbox app** — species switch, view toggle, year slider, country click
4. **Auto-play in COUNTRIES view** — currently stops autoplay when switching to countries view; could animate choropleth
5. **Multi-species overlay** — "Compare All Species" mode
6. **Add Hippo + Buffalo** — find icons, add to SPECIES_CONFIG
7. **JRC GSW multi-tile support** — `JRCTileDirectory` source class
8. **Data confidence layer** — `record_count` + `coordinate_precision` per grid cell
9. **Additional water sources** — springs, reservoirs, boreholes
10. **Human pressure layer** — roads, fences, settlements (Pressure Type 2)
11. **Phase 2 — Predict**: CHIRPS rainfall as reliability modifier; CMIP6 climate projections; monthly water layer (JRC GSW monthly recurrence)
12. **Phase 3 — Prescribe**: WDPA protected areas; intervention zones; refuge viability

---

## 6. Data Sources — Full Inventory

### Currently Ingested
| Dataset | Type | Coverage | Key Use |
|---|---|---|---|
| Natural Earth rivers | Shapefile | Global | River network (line geometries) |
| Natural Earth countries | Shapefile | Global | Country boundaries for choropleth |
| GLWD v2 | GeoTIFF | Global | Wetlands, pans, floodplains, saline lakes |
| JRC Global Surface Water | GeoTIFF tiles | Global | Seasonal/ephemeral surface water |
| GBIF API | REST API | Global | Species occurrences — 9 species cached |

### Planned — Water Layers
| Dataset | Type | Coverage | Key Use | URL |
|---|---|---|---|---|
| Africa Groundwater Atlas | Shapefile | Africa | Springs, aquifer zones | africagroundwateratlas.org |
| Global Dam Watch (GDW) | Shapefile | Global | Reservoirs, dams | globaldamwatch.org |
| HydroRIVERS | Shapefile | Global | Improved river network | hydrosheds.org |
| OpenStreetMap | API / extract | Global | Boreholes, waterholes | overpass-api.de |

---

## 11. Notes for Future Claude Sessions

- The developer uses **strict TDD** — always write tests before implementation. Non-negotiable.
- **Never hardcode species names** in library code. Always use `SPECIES_CONFIG` from `config/species.py`.
- The project is in **Python 3.12**, packaged with `pyproject.toml`, installed as editable (`pip install -e .`).
- Data files live in `data/raw/` and are **not committed to git** (too large). Exception: `apps/mapbox/data/*.geojson` ARE committed (small enough, needed for GitHub Pages).
- `scripts/plot_elephants.py` is a **developer visualization script**, not part of the library.
- `test_water_real_data.py` hits the **real filesystem** — keep separated from unit tests in CI.
- **The phantom thirst bug is fixed** — GLWD v2 with correct class mapping now captures Etosha Pan (class 2, saline lake), Makgadikgadi/Sua Pan (class 32, salt pan).
- **GLWD v2 has 33 classes**, not 12. The old v1 mapping `{4, 7, 9}` is wrong.
- **Water type column is `water_type`**, not `type`.
- **Natural Earth lakes are retired** — replaced by GLWD class 1. Natural Earth rivers kept for lines. Natural Earth countries added for choropleth.
- **Data quality gaps are intentional insights**, not bugs to fix.
- **`month` parameter** exists on all source classes by design — not yet implemented. Phase 2.
- **`RAINFALL_DERIVED`** in `WaterMechanism` enum — placeholder for Phase 2.
- **Streamlit deployed URL** — `https://wildlife-water-stress-atlas-ngvdrwg2yhzekplfeq6nvd.streamlit.app`
- **Mapbox app deployed URL** — `https://mtgiguere.github.io/wildlife-water-stress-atlas/`
- **Git LFS** — tracking `data/processed/*.gpkg`. `apps/mapbox/data/*.geojson` are regular git (small enough).
- **`requirements.txt`** — minimal runtime deps only, no pinned versions for rasterio.
- **`sys.path` insert** in `streamlit_app.py` — required for Streamlit Cloud.
- **`runtime.txt`** — contains `3.12`, no `python-` prefix.
- **Standalone PowerShell** for Playwright (Node v22), VS Code terminal for everything else.
- **`st.session_state`** used for species selection persistence in `streamlit_app.py`.
- **`_cache_dir` parameter** in `load_gbif_data()` — underscore prefix tells `@st.cache_data` not to hash it.
- **`icon_static_path`** in SPECIES_CONFIG — served from Streamlit static folder. Same-origin, no CORS.
- **`gbif_cache_file`** in SPECIES_CONFIG — format `gbif_{genus}_{species}.gpkg`.
- **Mapbox token** — public scopes only, URL-restricted to GitHub Pages + localhost. Safe to commit.
- **`pyproject.toml` setuptools config** — `package-dir = {"" = "src", "apps" = "apps", "scripts" = "scripts"}`, `packages.find where = ["src"]`. The `conftest.py` at root adds scripts to sys.path for pytest.
- **`conftest.py`** at repo root — adds project root to `sys.path` so `scripts` package is importable in tests.
- **`STABLE_THRESHOLD = 0.5`** in `trends.py` — heuristic, ecological validation needed in Phase 2.
- **Country choropleth** uses Natural Earth GeoJSON fetched from GitHub CDN (`nvkelso/natural-earth-vector`) at runtime. The country count data (`country_counts_gbif_*.geojson`) is pre-exported and committed.
- **Trend chart** is pure Canvas 2D API — no chart library dependency. Draws raw data line, trend line (dashed, color-coded), grid, axis labels.
- **Flamingo has 99,900 GBIF records** — global distribution including Europe (escaped lab specimens). Intentionally preserved as data quality story.
- **Mali desert elephants** (~17°N in Niger/Mali) appear in GBIF data — real, not data errors. World's northernmost elephant population.
- **Giraffe records are sparse** (~5,549) — scientifically meaningful (Vulnerable IUCN, population -40% in 30 years).
- **Two frog species share the same Streamlit icon** — tooltip distinguishes them.
- **Developer is planning a decade of digital nomad travel** — Africa leg includes Chobe National Park (highest elephant concentration on Earth). Full circle with this project. 🐘
- **Job interview context** — interviewing for Mapbox SDE II, Boundaries team. The Mapbox app was built specifically to demo their product. Key talking points: Streamlit payload limits → Mapbox migration; Natural Earth spatial join mirrors Boundaries pipeline patterns; TDD throughout; GBIF credibility answer (see pinned answer above).

### Session End State (May 14, 2026)
- 299 unit tests, 100% coverage ✅
- 16 Playwright E2E tests (Streamlit only) ✅
- Mapbox app live on GitHub Pages ✅
- Country choropleth + trend chart live ✅
- Linear regression in core analytics library ✅
- All 9 species exported and working ✅

Next session priorities:
1. Icon clustering on points view
2. `__main__` blocks for export scripts
3. Playwright E2E for Mapbox app
4. Interview prep / rehearsal
