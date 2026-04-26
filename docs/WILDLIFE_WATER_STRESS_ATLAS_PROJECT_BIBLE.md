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

### Current Data Sources
| Layer | File | Source | Format | Notes |
|---|---|---|---|---|
| Rivers | ne_10m_rivers_lake_centerlines_scale_rank.shp | Natural Earth | Shapefile | Line geometries — kept for distance calc accuracy |
| GLWD v2 | GLWD_v2_0_main_class.tif | HydroSHEDS | GeoTIFF | 33 classes, 500m resolution |
| JRC GSW | occurrence_*_v1_4_2021.tif | JRC / Google | GeoTIFF tiles | Africa tiles downloading |
| Elephant occurrences | GBIF API (live) | GBIF | API / GeoDataFrame | |

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
166 tests, 100% coverage across all modules. TDD strictly enforced — tests written before implementation on every change.

Test files:
- `test_species_config.py` — registry structure, field constraints, validation error branches
- `test_water_sources.py` — vector source classes, load_all_water, convenience functions
- `test_water_sources_raster.py` — GLWDWetlands and JRCGlobalSurfaceWater, all 16 GLWD classes
- `test_accessible_water.py` — filter_accessible_water, get_water_type_weights
- `test_overlap.py`, `test_scoring.py`, `test_apply.py`, `test_spatial.py` — analytics layer
- `test_gbif.py`, `test_water.py` — ingest layer
- `test_water_real_data.py` — integration test, hits real filesystem, keep separated from CI fast runs

### What the Map Shows Right Now
- Blue water network: rivers (Natural Earth lines) + GLWD wetlands, pans, floodplains, saline lakes
- High-stress grid cells (50km) where mean water stress score > threshold
- Score range with current data: 0.000 – 0.195 (max stress ~19.5%)
- The Etosha Pan area and Botswana pans now correctly show as water sources — phantom thirst bug is fixed

---

## 4. Known Bugs and Gaps

### Bug: Phantom Thirst — FIXED ✅
**Was**: Elephants near Etosha Pan (Namibia), Makgadikgadi/Sua Pan (Botswana) appeared high-stress because those water sources didn't exist in the data.  
**Fix**: GLWD v2 integrated. Classes 2 (saline lake), 21 (ephemeral), 32 (salt pan) now capture these features. `water_access.py` and `SPECIES_CONFIG` updated to include all new water types.  
**Note**: Etosha Pan is GLWD class 2 (saline lake) — the pan itself is too saline to drink but supports freshwater springs around its edges. The 0.4 reliability weight reflects this.

### Gap: Performance — Raster Vectorization is Slow
GLWD vectorization takes several minutes on a laptop even with bbox windowing. The global raster is large and `rasterio.features.shapes()` is CPU-intensive.  
**Planned fix**: Cache vectorized output to `data/processed/` as GeoPackage files. Load from cache on subsequent runs. Streamlit's `@st.cache_data` decorator will handle this elegantly when the web app is built.  
**Impact**: Only affects developer experience for now. Not a blocker.

### Gap: Data Quality as a Story
GBIF occurrence records include museum specimens, historical sightings, zoo/captive animals, and records with imprecise coordinates alongside wild observations. For example, elephant records appear in the Niger desert — these may be the real Mali desert elephants (northernmost elephant population in Africa, genuinely remarkable) or artifacts of imprecise coordinate recording.

**Intentional design decision**: We do NOT filter these out. Imprecise or anomalous records are a story in themselves:
- They surface data gaps that drive funding for better field data collection
- They highlight understudied populations (Mali desert elephants need attention)
- They demonstrate the need for better captive/wild tagging in GBIF

Future Prescribe layer should expose `record_count` and `coordinate_precision` per grid cell so viewers can distinguish "high stress, high confidence" from "high stress, low confidence — needs field verification." Data confidence is a first-class output, not a filter.

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

### Gap: GBIF Pagination
`fetch_occurrences` is capped at the limit parameter with no pagination. Need offset-based pagination loop for full coverage.

### Gap: No Temporal Dimension Yet
All analysis is static. `load_all_water()` and all source classes accept a `month` parameter (1–12) by design — the interface is future-ready. JRC GSW has a monthly recurrence layer that will be the first implementation. CHIRPS rainfall data will be a reliability modifier on existing sources (Phase 2), not a source class.

### Gap: No Human Pressure Layer
Fences, roads, settlements, and farmland block animal movement to water.

### Gap: Water Quality Not Modeled
Toxic algae, high salinity, bacterial contamination make water physically present but functionally inaccessible. Salinity is partially addressed via `water_type_weights` (saline_lake weight = 0.4 for elephants) but not modeled explicitly.

---

## 5. Planned Refactoring / Next Steps

### Non-Negotiable Development Rules
- **Strict TDD**: tests written before code, always
- **CI/CD pipeline**: unit tests + linting + vulnerability scans minimum on every push
- **Never hardcode species names** anywhere in library code

### Priority 1: JRC GSW Multi-Tile Support ← NEXT
Add `JRCTileDirectory` source class or GDAL pre-merge workflow so Africa JRC tiles can be loaded. This completes the core water layer.

### Priority 2: Streamlit App Scaffold
Thin wrapper over existing pipeline. ~10 lines to wire up. Deploy to Streamlit Community Cloud (free, GitHub-connected, auto-deploy). Use `@st.cache_data` to cache GLWD and JRC vectorization — fixes the performance gap at the same time.

### Priority 3: GBIF Pagination
Add offset-based loop to `fetch_occurrences`. Currently capped at 300 records per request.

### Priority 4: Additional Water Sources
Springs, aquifer zones, reservoirs, boreholes. See gap table above.

### Priority 5: CI/CD Pipeline
GitHub Actions: unit tests + linting (ruff) + vulnerability scan on every push. Separate fast unit tests from integration tests (`test_water_real_data.py`).

### Priority 6: Human Pressure Layer
Fences, roads, settlements. Second pressure type after freshwater access.

### Priority 7: Data Confidence Layer
Per grid cell: `record_count`, `mean_coordinate_precision`, `confidence_tier`. Exposes data quality as insight rather than hiding it. See Section 4 Gap: Data Quality as a Story.

---

## 6. Data Sources — Full Inventory

### Currently Ingested
| Dataset | Type | Coverage | Key Use |
|---|---|---|---|
| Natural Earth rivers | Shapefile | Global | River network (line geometries) |
| GLWD v2 | GeoTIFF | Global | Wetlands, pans, floodplains, saline lakes |
| JRC Global Surface Water | GeoTIFF tiles | Global | Seasonal/ephemeral surface water |
| GBIF API | REST API | Global | Species occurrences |

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
│  (name, threshold, water types, weights, range...)   │
└──────────────────────┬──────────────────────────────┘
│
┌────────────┴────────────┐
▼                         ▼
┌─────────────────┐      ┌──────────────────────┐
│  Occurrence     │      │   Water Sources       │
│  Data (GBIF /   │      │   WaterSource ABC     │
│  Movebank)      │      │   normalized schema   │
│                 │      │   load_all_water()    │
│                 │      │   bbox + month params │
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
│   + Folium/PyDeck   │
│   @st.cache_data    │
│   Interactive Map   │
└─────────────────────┘

### Planned Tech Stack
| Layer | Technology | Notes |
|---|---|---|
| Core library | Python 3.12 | Existing |
| Geospatial | GeoPandas, Shapely, Rasterio | All installed |
| Data fetch | Requests (GBIF), standard file I/O | |
| Visualization | Folium or PyDeck (interactive) | Replaces matplotlib |
| Web app | Streamlit | ~10 lines to wrap existing pipeline |
| Hosting (now) | Streamlit Community Cloud | Free, GitHub-connected, auto-deploy |
| Hosting (future) | AWS | When scheduled jobs or DB needed |
| Testing | pytest | Strict TDD, 100% coverage maintained |
| CI/CD | GitHub Actions | Planned — unit tests + ruff + vuln scan |

---

## 8. The Three Phases in Detail

### Phase 1 — Describe (Current Focus)
**Goal**: Accurate picture of current water stress for African elephants.  
**Status**: Core pipeline working. Map renders. Phantom thirst bug fixed.  
**Remaining for Phase 1 completion**:
- JRC GSW multi-tile loading
- Streamlit app scaffold + caching
- GBIF pagination
- Additional water sources (springs, reservoirs, boreholes)
- Data confidence layer per grid cell

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

- **Predation pressure at water points** — lions controlling access
- **Water quality modeling** — toxic algae, bacterial contamination (salinity partially addressed via weights)
- **Survivorship bias in occurrence data** — animals that died of thirst aren't in GBIF
- **Social hierarchy at water points** — dominant bulls blocking access
- **Mineral licks** — animals travel for minerals, not just water
- **Fog/atmospheric water** — real in Namib/Atacama, no global dataset
- **Animal-created water sources** — elephant-dug wells (proxy via aquifer zones planned)
- **Captive/wild distinction in GBIF** — intentionally not filtered (see Section 4)

---

## 10. Immediate Next Steps (Prioritized)

1. **JRC GSW multi-tile support** — `JRCTileDirectory` source class or GDAL pre-merge
2. **Streamlit app scaffold** — thin wrapper, `@st.cache_data` for raster vectorization
3. **GBIF pagination** — offset loop in `fetch_occurrences`
4. **CI/CD pipeline** — GitHub Actions, fast unit tests separate from integration tests
5. **Data confidence layer** — `record_count` + `coordinate_precision` per grid cell
6. **Additional water sources** — springs, reservoirs, boreholes
7. **Human pressure layer** — roads, fences, settlements (Pressure Type 2)

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
- **Raster vectorization is slow** — GLWD takes several minutes even with bbox windowing. Cache to `data/processed/` is the planned fix. Don't be alarmed by runtime.
- **Data quality gaps are intentional insights**, not bugs to fix. Imprecise GBIF records surface funding needs and understudied populations. Surface them in the Prescribe layer as data confidence scores.
- **`month` parameter** exists on all source classes and `load_all_water()` by design. Currently accepted but not implemented — JRC GSW monthly recurrence layer will be the first use in Phase 2.
- **`RAINFALL_DERIVED`** is in the `WaterMechanism` enum as a placeholder. Rainfall is a reliability modifier on existing sources (Phase 2), not a source class.
- When discussing water sources, think in **mechanisms** (permanent surface, seasonal surface, groundwater, artificial, derived, rainfall-derived) not just types.
- The eventual deployment target is **Streamlit Community Cloud** (free tier) with a possible future move to AWS when scheduled jobs are needed.
- The developer wants to eventually reach out to **conservation organizations** (Save the Elephants, IUCN African Elephant Specialist Group) for ecological validation of stress model parameters. Future step.
- **All reliability and threshold values are heuristic placeholders** — honest about being estimates. Ecological validation is a future step.
- The **Mali desert elephants** (northernmost elephant population, ~17°N in Niger/Mali) appear in GBIF data. They are real and remarkable — genuinely the world's northernmost elephant population making long seasonal migrations. Not a data error.