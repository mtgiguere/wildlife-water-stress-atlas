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

**`scripts/plot_elephants.py`**  
Main pipeline entry point. Uses `load_all_water()` with `WATER_CONFIG` dict. Species name in single `SPECIES` constant at top of file. Africa bbox `(-20, -40, 55, 40)` passed to all water sources.

**`scripts/prefetch_gbif.py`**  
Bulk GBIF prefetch script. Loops through all species in `SPECIES_CONFIG` and pre-populates cache files in `data/processed/`. Run once after adding new species. Supports `--species` flag for single species fetch and `--force` flag to re-fetch existing cache files.

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

### Current Data Sources
| Layer | File | Source | Format | Notes |
|---|---|---|---|---|
| Rivers | ne_10m_rivers_lake_centerlines_scale_rank.shp | Natural Earth | Shapefile | Line geometries — kept for distance calc accuracy |
| GLWD v2 | GLWD_v2_0_main_class.tif | HydroSHEDS | GeoTIFF | 33 classes, 500m resolution |
| JRC GSW | occurrence_*_v1_4_2021.tif | JRC / Google | GeoTIFF tiles | Africa tiles downloading |
| Species occurrences | GBIF API (live) | GBIF | API / GeoDataFrame | All species in SPECIES_CONFIG |

Natural Earth lakes retired — replaced by GLWD class 1 (freshwater lake).

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
**246 unit tests, 100% coverage**
**16 Playwright E2E tests — 16 passing, 0 pending** ✅
TDD strictly enforced — tests written before implementation on every change.

Test files:
- `test_species_config.py` — registry structure, field constraints, validation error branches (includes new fields: icon_static_path, gbif_cache_file, emoji)
- `test_water_sources.py` — vector source classes, load_all_water, convenience functions
- `test_water_sources_raster.py` — GLWDWetlands and JRCGlobalSurfaceWater, all 16 GLWD classes
- `test_accessible_water.py` — filter_accessible_water, get_water_type_weights
- `test_overlap.py`, `test_scoring.py`, `test_apply.py`, `test_spatial.py` — analytics layer
- `test_gbif.py`, `test_water.py` — ingest layer
- `test_cache.py` — dynamic species caching, _cache_dir injection pattern
- `test_map.py` — IconLayer type, icon_data embedded in records, water layers
- `test_sidebar.py` — pure data functions (get_year_range, get_record_count, get_year_counts)
- `test_water_real_data.py` — integration test, hits real filesystem, keep separated from CI fast runs

### Current Species Registry
All species in `SPECIES_CONFIG` with GBIF cache files:

| Species | Common Name | Emoji | Threshold | Dependency | Cache File | Records |
|---|---|---|---|---|---|---|
| Loxodonta africana | African Elephant | 🐘 | 300km | high | gbif_loxodonta_africana.gpkg | ~21,900 |
| Equus quagga | Plains Zebra | 🦓 | 150km | high | gbif_equus_quagga.gpkg | 22,235 |
| Giraffa camelopardalis | Giraffe | 🦒 | 80km | moderate | gbif_giraffa_camelopardalis.gpkg | 5,549 |
| Panthera leo | Lion | 🦁 | 200km | moderate | gbif_panthera_leo.gpkg | TBC |
| Acinonyx jubatus | Cheetah | 🐆 | 250km | low | gbif_acinonyx_jubatus.gpkg | 8,508 |
| Crocodylus niloticus | Nile Crocodile | 🐊 | 10km | high | gbif_crocodylus_niloticus.gpkg | 9,134 |
| Phoenicopterus roseus | Greater Flamingo | 🦩 | 50km | high | gbif_phoenicopterus_roseus.gpkg | TBC |
| Hyperolius marmoratus | Painted Reed Frog | 🐸 | 2km | high | gbif_hyperolius_marmoratus.gpkg | TBC |
| Xenopus laevis | African Clawed Frog | 🐸 | 5km | high | gbif_xenopus_laevis.gpkg | TBC |

Species tiers for narrative storytelling:
- **Tier 1 — Megafauna Water Anchors**: Elephant
- **Tier 2 — Large Herbivore Complexity**: Zebra, Giraffe
- **Tier 3 — Carnivores (Circle of Life)**: Lion, Cheetah
- **Tier 4 — Sensitive Indicator Species**: Crocodile, Flamingo, Reed Frog, Clawed Frog

Planned additions (icons needed): Hippo (*Hippopotamus amphibius*), African Buffalo (*Syncerus caffer*)

### SPECIES_CONFIG Fields
Each species entry requires these fields (validated at import time):
- `common_name` — display name
- `water_threshold_m` — distance at which stress score = 1.0
- `accessible_water_types` — set of water types the species can use
- `water_type_weights` — reliability weights per water type (must match accessible_water_types)
- `daily_range_m` — typical daily movement range
- `water_dependency` — "low" | "moderate" | "high"
- `icon_url` — legacy Twemoji CDN URL (kept for reference, not used for rendering)
- `icon_static_path` — path for PyDeck IconLayer, format: "app/static/{filename}"
- `gbif_cache_file` — GeoPackage filename, format: "gbif_{genus}_{species}.gpkg"
- `emoji` — used in UI labels, chart titles, sidebar stats

### What the Map Shows Right Now
- Dark CARTO basemap (dark-matter-gl-style)
- Blue water network: rivers (Natural Earth lines) + GLWD wetlands, pans, floodplains, saline lakes
- Species occurrence icons from Creative-Tail animal icon set (served from static/)
- Species selector dropdown in sidebar — switches icons, chart, and stats dynamically
- Year slider — filters occurrences by year, instant in-memory filtering
- Hero banner — elephants_waterhole.jpeg with dark gradient overlay
- Stats row: Species Records for selected year, Total Records, Water Sources Mapped
- Year distribution bar chart — COVID dip 2020 visible

---

## 4. Known Bugs and Gaps

### Bug: Phantom Thirst — FIXED ✅
**Was**: Elephants near Etosha Pan (Namibia), Makgadikgadi/Sua Pan (Botswana) appeared high-stress because those water sources didn't exist in the data.  
**Fix**: GLWD v2 integrated. Classes 2 (saline lake), 21 (ephemeral), 32 (salt pan) now capture these features. `water_access.py` and `SPECIES_CONFIG` updated to include all new water types.  
**Note**: Etosha Pan is GLWD class 2 (saline lake) — the pan itself is too saline to drink but supports freshwater springs around its edges. The 0.4 reliability weight reflects this.

### Bug: Playwright Chart Tests — FIXED ✅
**Was**: Two chart tests timing out — chart loaded after slow water layer.
**Fix**: Tests moved inside `test.describe` block so they receive the `beforeEach` navigation hook. Root cause was incorrect indentation placing tests outside the describe block entirely — they were running against a blank page.

### Gap: Performance — Raster Vectorization is Slow
GLWD vectorization takes several minutes on a laptop even with bbox windowing. The global raster is large and `rasterio.features.shapes()` is CPU-intensive.  
**Planned fix**: Cache vectorized output to `data/processed/` as GeoPackage files. Load from cache on subsequent runs. Streamlit's `@st.cache_data` decorator handles this.
**Status**: Caching implemented. `@st.cache_data` working. Performance acceptable (~20s cold load on Streamlit Cloud).

### Gap: Data Quality as a Story
GBIF occurrence records include museum specimens, historical sightings, zoo/captive animals, and records with imprecise coordinates alongside wild observations. For example, elephant records appear in the Niger desert — these may be the real Mali desert elephants (northernmost elephant population in Africa, genuinely remarkable) or artifacts of imprecise coordinate recording.

**Intentional design decision**: We do NOT filter these out. Imprecise or anomalous records are a story in themselves:
- They surface data gaps that drive funding for better field data collection
- They highlight understudied populations (Mali desert elephants need attention)
- They demonstrate the need for better captive/wild tagging in GBIF

Future Prescribe layer should expose `record_count` and `coordinate_precision` per grid cell so viewers can distinguish "high stress, high confidence" from "high stress, low confidence — needs field verification." Data confidence is a first-class output, not a filter.

### Gap: Giraffe Records are Sparse
Only 5,549 GBIF records for Giraffa camelopardalis across all of Africa. Giraffes are Vulnerable on the IUCN Red List — population has declined ~40% in 30 years. Low GBIF records = low field observation coverage. This is not a data bug — it's the story. The Prescribe layer should flag giraffe grid cells as high-priority for field data collection funding.

### Gap: JRC GSW Multi-Tile Loading
JRC GSW data comes as multiple 10-degree tiles per region. `JRCGlobalSurfaceWater` currently expects a single file path. Africa requires ~40-60 tiles.  
**Planned fix**: Add a `JRCTileDirectory` source class that handles a folder of tiles, merges with `rasterio.merge`, then vectorizes. Alternatively, pre-merge tiles to a single Africa GeoTIFF using GDAL.

### Gap: Missing Water Source Types
Still not in the pipeline:

| Type | Why it matters | Dataset | Status |
|---|---|---|---|
| Springs & seeps | Groundwater at surface, critical in dry season | Africa Groundwater Atlas | Not started |
| Aquifer zones | Subsurface water elephants dig for | Africa Groundwater Atlas | Not started |
| Reservoirs & dams | Man-made impoundments | Global Dam Watch (GDW) | Not started |
| Boreholes / waterholes | Park management water (Hwange, Kruger, Etosha) | OpenStreetMap / park data | Not started |

### Gap: Species Config Split — FIXED ✅
Previously `SPECIES_WATER_THRESHOLDS` in `scoring.py` and `SPECIES_ACCESSIBLE_WATER_TYPES` / `WATER_TYPE_WEIGHTS` in `water_access.py`. Now consolidated in `config/species.py`.

### Gap: GBIF Pagination — FIXED ✅
`fetch_occurrences` now uses offset-based pagination loop for full coverage. `prefetch_gbif.py` script handles bulk pre-fetching for all species.

### Gap: No Temporal Dimension Yet
All analysis is static. `load_all_water()` and all source classes accept a `month` parameter (1–12) by design — the interface is future-ready. JRC GSW has a monthly recurrence layer that will be the first implementation. CHIRPS rainfall data will be a reliability modifier on existing sources (Phase 2), not a source class.

### Gap: No Human Pressure Layer
Fences, roads, settlements, and farmland block animal movement to water.

### Gap: Water Quality Not Modeled
Toxic algae, high salinity, bacterial contamination make water physically present but functionally inaccessible. Salinity is partially addressed via `water_type_weights` (saline_lake weight = 0.4 for elephants) but not modeled explicitly.

### Gap: Icon Clustering at Low Zoom
When zoomed out to full Africa, dense occurrence clusters overlap badly. PyDeck's `HeatmapLayer` or client-side clustering could solve this. Implement when species count > 2 or when demo feedback requests it.

### Gap: Multi-Species Overlay
Users will ask to see all species simultaneously. Requires combining GeoDataFrames with a `species` column and building one IconLayer per species. UI: "Compare All Species" button or multi-select checkbox. Scientifically compelling — elephant vs reed frog distribution contrast tells the water stress story instantly.

### Gap: Xenopus laevis Invasive Records
African Clawed Frog GBIF records include European and American populations from escaped laboratory specimens. These are intentionally preserved — they are a data quality story. The Prescribe layer should flag non-African records as low-confidence.

### Gap: Playwright E2E Tests Need Update for Species Selector
Species selector (`st.selectbox`) added to sidebar. E2E tests not yet updated to cover species switching. Add tests for: selector visible, switching species changes map title, switching species changes chart title.

---

## 5. Planned Refactoring / Next Steps

### Non-Negotiable Development Rules
- **Strict TDD**: tests written before code, always
- **CI/CD pipeline**: unit tests + linting + vulnerability scans minimum on every push
- **Never hardcode species names** anywhere in library code

1. **Update Playwright E2E tests** — add species selector tests, update existing tests that reference "Elephant Records" hardcoded text

2. **Deploy to Streamlit Cloud** — push current state including:
   - Dark theme + hero banner
   - Species selector
   - All GBIF cache files via Git LFS
   - New `config.toml` with `enableStaticServing = true`
   - All Creative-Tail animal icons in `static/`

3. **Fetch remaining GBIF data** — flamingo, reed frog, clawed frog still TBC

4. **Auto-play animation** — year slider advances automatically
   - `▶ Auto-play` button in sidebar
   - `st.session_state` + `st.empty()` + `time.sleep()`
   - Speed options: slow/medium/fast
   - Loop back to start when reaching 2026

5. **Icon clustering** — at zoom 3 dense clusters overlap badly. Implement when demo feedback requests it.

6. **Multi-species overlay** — "Compare All Species" mode

7. **Add Hippo + Buffalo** — find matching icons from Creative-Tail set or similar. Scientific justification: hippo = permanent water obligate, buffalo = tight 15km water range.

8. **JRC GSW multi-tile support** — `JRCTileDirectory` source class or GDAL pre-merge

9. **CI/CD pipeline** — GitHub Actions, fast unit tests separate from integration tests

10. **Data confidence layer** — `record_count` + `coordinate_precision` per grid cell

11. **Additional water sources** — springs, reservoirs, boreholes

12. **Human pressure layer** — roads, fences, settlements (Pressure Type 2)

---

## 6. Data Sources — Full Inventory

### Currently Ingested
| Dataset | Type | Coverage | Key Use |
|---|---|---|---|
| Natural Earth rivers | Shapefile | Global | River network (line geometries) |
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

### Planned — Climate & Environmental
| Dataset | Type | Coverage | Key Use |
|---|---|---|---|
| CHIRPS rainfall | Raster | Global (50°S–50°N) | Reliability modifier on water sources (Phase 2), seasonal patterns, backtesting |
| CMIP6 climate projections | Raster | Global | Predictive modeling of future water availability |
| ESA Land Cover | Raster | Global | Human pressure, habitat conversion |
| NDVI (Sentinel-2 / MODIS) | Raster | Global | Vegetation water content, riparian corridor detection |

### Planned — Human Pressure
| Dataset | Type | Coverage | Key Use |
|---|---|---|---|
| OpenStreetMap roads/fences | Vector | Global | Movement barriers |
| WDPA (Protected Areas) | Shapefile | Global | Conservation area boundaries — essential for prescription layer |
| GPW / WorldPop | Raster | Global | Human settlement density |
| FAO AQUASTAT | Tabular/Vector | Global | Irrigation water extraction |

### Planned — Species Movement
| Dataset | Type | Coverage | Key Use |
|---|---|---|---|
| Movebank | API | Global | GPS tracking data — can infer water sources from movement clusters |

---

## 7. Architecture — Full System Vision

┌─────────────────────────────────────────────────────┐
│                   Species Config                     │
│  config/species.py — single source of truth          │
│  (name, threshold, water types, weights, range,      │
│   icon_static_path, gbif_cache_file, emoji)          │
└──────────────────────┬──────────────────────────────┘
                       │
           ┌────────────┴────────────┐
           ▼                         ▼
┌─────────────────┐      ┌──────────────────────┐
│  Occurrence     │      │   Water Sources       │
│  Data (GBIF /   │      │   WaterSource ABC     │
│  Movebank)      │      │   normalized schema   │
│  9 species      │      │   load_all_water()    │
│  cached         │      │   bbox + month params │
└────────┬────────┘      └──────────┬───────────┘
         │                          │
         └──────────┬───────────────┘
                    ▼
          ┌─────────────────────┐
          │   Pressure Scoring   │
          │   (Water: distance,  │
          │    quality, type,    │
          │    seasonality)      │
          │   (Human: barriers,  │
          │    extraction, etc.) │
          └──────────┬──────────┘
                     ▼
          ┌─────────────────────┐
          │  Composite Stress   │
          │  Score per point    │
          │  per time period    │
          └──────────┬──────────┘
                     ▼
          ┌─────────────────────┐
          │  Grid Aggregation   │
          │  (spatial.py)       │
          │  + Data Confidence  │
          │  (record_count,     │
          │   coord_precision)  │
          └──────────┬──────────┘
                     ▼
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
    Describe         Predict         Prescribe
   (Phase 1,     (Phase 2 —      (Phase 3 —
   working)      climate +        intervention
                 CHIRPS)          zones, refuge
                                  viability,
                                  data gaps)
                                      │
                                      ▼
                        ┌─────────────────────┐
                        │   Streamlit App     │
                        │   Dark theme        │
                        │   Hero banner       │
                        │   Species selector  │
                        │   Year slider       │
                        │   PyDeck map        │
                        │   @st.cache_data    │
                        └─────────────────────┘

### Planned Tech Stack
| Layer | Technology | Notes |
|---|---|---|
| Core library | Python 3.12 | Existing |
| Geospatial | GeoPandas, Shapely, Rasterio | All installed |
| Data fetch | Requests (GBIF), standard file I/O | |
| Visualization | PyDeck (WebGL) | Dark CARTO basemap, IconLayer |
| Web app | Streamlit | Species selector, year slider, dark theme |
| Hosting (now) | Streamlit Community Cloud | Free, GitHub-connected, auto-deploy |
| Hosting (future) | AWS | When scheduled jobs or DB needed |
| Testing | pytest | Strict TDD, 100% coverage maintained |
| CI/CD | GitHub Actions | Planned — unit tests + ruff + vuln scan |

---

## 8. The Three Phases in Detail

### Phase 1 — Describe (Current Focus)
**Goal**: Accurate picture of current water stress for African wildlife.  
**Status**: Core pipeline working. Map renders. 9 species in config. Species selector live.  
**Remaining for Phase 1 completion**:
- JRC GSW multi-tile loading
- GBIF pagination ✅ (done)
- Additional water sources (springs, reservoirs, boreholes)
- Data confidence layer per grid cell
- CI/CD pipeline
- Playwright E2E tests for species selector

### Phase 2 — Predict
**Goal**: Forecast how water availability will change over 10/20/50 years.  
**Key challenges**:
- Requires climate model outputs (CMIP6 scenarios)
- Temporal dimension is already designed in — `month` parameter exists on all source classes
- CHIRPS rainfall = reliability modifier on existing sources, not a new source class
- Validation strategy: backtest using JRC GSW 1984–2021 history + CHIRPS rainfall back to 1981
- Potential collaborators: IUCN, WWF climate teams, academic institutions

### Phase 3 — Prescribe
**Goal**: Identify where conservation intervention will be most effective.  
**Outputs**:
- High-impact intervention zones (protect water here → save population)
- Viable refuge areas (if current habitat becomes untenable)
- Human-wildlife conflict zones to flag
- **Data gap zones** — grid cells with high stress but low data confidence, flagged for field verification and donor attention
**Required additional data**:
- WDPA protected area boundaries
- Human settlement density
- Movement corridor analysis
**Important caveats**:
- Relocation recommendations need domain expert validation
- Community/indigenous land rights must be incorporated
- Frame as "refuge viability assessment" not "move elephants here"
- Data gaps are insights, not failures — surface them explicitly

---

## 9. What We Knowingly Omit (For Now)

- **Predation pressure at water points** — lions controlling access to water (ironic given lions are now in the atlas)
- **Water quality modeling** — toxic algae, bacterial contamination (salinity partially addressed via weights)
- **Survivorship bias in occurrence data** — animals that died of thirst aren't in GBIF
- **Social hierarchy at water points** — dominant bulls blocking access
- **Mineral licks** — animals travel for minerals, not just water
- **Fog/atmospheric water** — real in Namib/Atacama, no global dataset
- **Animal-created water sources** — elephant-dug wells (proxy via aquifer zones planned)
- **Captive/wild distinction in GBIF** — intentionally not filtered (see Section 4)
- **Invasive species records** — Xenopus laevis in Europe/Americas intentionally preserved as data quality story

---

## 10. Immediate Next Steps (Prioritized)

1. **Fetch remaining GBIF species** — flamingo, reed frog, clawed frog still TBC
2. **Deploy to Streamlit Cloud** — push dark theme + species selector + all cache files
3. **Update Playwright E2E tests** — species selector coverage
4. **Auto-play animation** — year slider auto-advances
5. **CI/CD pipeline** — GitHub Actions, fast unit tests separate from integration tests
6. **Icon clustering** — dense clusters at zoom 3
7. **Multi-species overlay** — "Compare All Species" mode
8. **Add Hippo + Buffalo** — find icons, add to SPECIES_CONFIG
9. **JRC GSW multi-tile support** — `JRCTileDirectory` source class
10. **Data confidence layer** — `record_count` + `coordinate_precision` per grid cell
11. **Additional water sources** — springs, reservoirs, boreholes
12. **Human pressure layer** — roads, fences, settlements (Pressure Type 2)

---

## 11. Notes for Future Claude Sessions

- The developer uses **strict TDD** — always write tests before implementation. Non-negotiable.
- **Never hardcode species names** in library code. Always use `SPECIES_CONFIG` from `config/species.py`.
- The project is in **Python 3.12**, packaged with `pyproject.toml`, installed as editable (`pip install -e .`).
- Data files live in `data/raw/` and are **not committed to git** (too large).
- `scripts/plot_elephants.py` is a **developer visualization script**, not part of the library.
- `test_water_real_data.py` hits the **real filesystem** — keep separated from unit tests in CI.
- **The phantom thirst bug is fixed** — GLWD v2 with correct class mapping now captures Etosha Pan (class 2, saline lake), Makgadikgadi/Sua Pan (class 32, salt pan), and all major wetland/floodplain types.
- **GLWD v2 has 33 classes**, not 12. The old v1 mapping `{4, 7, 9}` is wrong and was replaced with the correct v2 mapping. See Section 3 GLWD Class Map table.
- **Water type column is `water_type`**, not `type`. This is the normalized schema column name throughout the pipeline.
- **Natural Earth lakes are retired** — replaced by GLWD class 1. Natural Earth rivers kept as line geometries for distance calculation accuracy.
- **Raster vectorization is slow** — GLWD takes several minutes even with bbox windowing. Cache to `data/processed/` is implemented. Don't be alarmed by runtime.
- **Data quality gaps are intentional insights**, not bugs to fix. Imprecise GBIF records surface funding needs and understudied populations. Surface them in the Prescribe layer as data confidence scores.
- **`month` parameter** exists on all source classes and `load_all_water()` by design. Currently accepted but not implemented — JRC GSW monthly recurrence layer will be the first use in Phase 2.
- **`RAINFALL_DERIVED`** is in the `WaterMechanism` enum as a placeholder. Rainfall is a reliability modifier on existing sources (Phase 2), not a source class.
- When discussing water sources, think in **mechanisms** (permanent surface, seasonal surface, groundwater, artificial, derived, rainfall-derived) not just types.
- The eventual deployment target is **Streamlit Community Cloud** (free tier) with a possible future move to AWS when scheduled jobs are needed.
- The developer wants to eventually reach out to **conservation organizations** (Save the Elephants, IUCN African Elephant Specialist Group, IUCN Equid Specialist Group) for ecological validation of stress model parameters. Future step.
- **All reliability and threshold values are heuristic placeholders** — honest about being estimates. Ecological validation is a future step.
- The **Mali desert elephants** (northernmost elephant population, ~17°N in Niger/Mali) appear in GBIF data. They are real and remarkable — genuinely the world's northernmost elephant population making long seasonal migrations. Not a data error.
- **Year distribution chart** — `st.bar_chart(get_year_counts(all_occurrences))` in `streamlit_app.py`. COVID dip 2020 clearly visible. Dynamic title from SPECIES_CONFIG emoji + common_name.
- **Playwright chart tests** — all 16 passing ✅. Fixed by moving chart tests inside `test.describe` block.
- **`getByText('Elephant Records —')`** — use the dash to avoid strict mode violation with chart subheader.
- **Deployed URL** — `https://wildlife-water-stress-atlas-ngvdrwg2yhzekplfeq6nvd.streamlit.app`
- **Git LFS** — tracking `data/processed/*.gpkg`. Files committed grow as species are added. Long-term: migrate to AWS S3.
- **`requirements.txt`** — minimal runtime deps only, no pinned versions for rasterio. No `packages.txt` needed — rasterio wheels bundle GDAL.
- **`sys.path` insert** in `streamlit_app.py` — required for Streamlit Cloud, must be first code in file before any imports.
- **`runtime.txt`** — contains `3.12`, no `python-` prefix.
- **Standalone PowerShell** for Playwright (Node v22), VS Code terminal for everything else. nvm auto-runs via PowerShell profile.
- **Global Nature Watch (DevSeed/WRI)** — comparable platform but focuses on land cover change not wildlife water stress. Our niche is species-first water stress modeling — they don't do this.
- **`st.session_state`** used for species selection persistence in `streamlit_app.py`. Without it, every Streamlit rerun resets the species selector to default.
- **`_cache_dir` parameter** in `load_gbif_data()` — underscore prefix tells `@st.cache_data` not to hash this parameter. Used for dependency injection in tests. Default is `Path("data/processed")`.
- **`icon_static_path`** in SPECIES_CONFIG — served from Streamlit static folder at `app/static/`. Same-origin serving avoids CORS issues with PyDeck IconLayer. Icons from Creative-Tail animal set.
- **`gbif_cache_file`** in SPECIES_CONFIG — GeoPackage filename, format `gbif_{genus}_{species}.gpkg`. Used by `load_gbif_data()` to find the right cache file without hardcoding.
- **`scripts/prefetch_gbif.py`** — run this after adding new species to pre-populate GBIF cache. Supports `--species "Scientific name"` for single species and `--force` to re-fetch.
- **Dark theme** — implemented via CSS injection in `st.markdown(unsafe_allow_html=True)`. Background `#0E1117`, sidebar `#161B22`.
- **Hero banner** — `elephants_waterhole.jpeg` in `apps/streamlit/static/`. Served via Streamlit static serving (`enableStaticServing = true` in `.streamlit/config.toml`).
- **`use_container_width` deprecation** — Streamlit warns to replace with `width='stretch'`. Fix before next Streamlit version upgrade.
- **Species narrative tiers** — Elephant (megafauna anchor) → Zebra/Giraffe (herbivore complexity) → Lion/Cheetah (circle of life) → Croc/Flamingo/Frogs (sensitive indicators). This progression is a funding conversation — shows where ecosystem is holding vs collapsing.
- **Giraffe records are sparse** (~5,549) — this is scientifically meaningful, not a data error. Giraffes are Vulnerable IUCN, population down ~40% in 30 years. Surface this in Prescribe layer.
- **Two frog species share the same icon** (`Creative-Tail-Animal-frog.svg.png`) — tooltip on hover distinguishes them. Acceptable for now.

Ran out of Session LIMIT --->

Where we stopped:

stats.py created with get_water_threshold_display() ✅
test_stats.py created with first passing test ✅
247 passing, 100% coverage ✅
Flamingo still fetching 🦩

Next TDD steps for stats.py:

test_get_water_threshold_display_reed_frog — "2 km"
test_get_water_threshold_display_raises_for_unknown_species
get_species_comparison() function — returns dict of species → record count
Wire both into streamlit_app.py

Also pending:

Flamingo fetch + commit + push
Deploy to Streamlit Cloud
Playwright E2E updates for species selector