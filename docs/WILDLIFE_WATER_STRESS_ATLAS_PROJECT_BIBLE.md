# Wildlife Water Stress Atlas — Project Bible
> Last updated: April 2026  
> Purpose: Onboarding document for new Claude sessions and project reference for the developer.  
> Read this before touching any code.

---

## 1. What This Project Is

A **geospatial decision-support platform** that models wildlife survival risk as a function of freshwater access and other environmental pressures. The ultimate goal is a three-phase system:

1. **Describe** — current state of water stress for a given species, visualized on a map
2. **Predict** — how water systems will change over years/decades due to climate change and human activity
3. **Prescribe** — identify conservation intervention zones, habitat protection priorities, and in worst-case scenarios, viable relocation areas

This is a personal/fun project by a single developer (mtgiguere), built with genuine conservation intent. The audience right now is the developer — "I want to see it on a map." Future audiences could include conservation organizations, policymakers, or researchers. Design for that possibility but don't over-engineer for it now.

---

## 2. The Vision — Species and Pressure Ladder

### Species (in planned order)
1. African elephants (*Loxodonta africana*) — current focus
2. Zebras, wildebeest, antelopes — large herbivores
3. Large carnivores (lions, wild dogs) — depend on herbivore populations
4. Amphibians — highly water-dependent, excellent stress indicators

### Pressures (in planned order)
1. **Freshwater access** — current focus (distance, quality, type, seasonality)
2. **Human pressure** — fences, roads, habitat conversion, water extraction, pollution, conflict
3. **Vegetation/food** — indirect water via plants, rainfall proxy
4. Future: predation pressure at water points, disease, climate-forced habitat shifts

### Core architectural principle
**Species and pressure type are ALWAYS first-class parameters — never hardcoded.**  
Adding a new species = adding one config entry.  
Adding a new pressure = adding one new scoring module.  
Nothing else should change.

---

## 3. Current State (What's Been Built)

### Repository
`https://github.com/mtgiguere/wildlife-water-stress-atlas`  
Branch: `vis_v1`  
Language: Python 3.12  
Package manager: pip + pyproject.toml

### Directory Structure
```
wildlife-water-stress-atlas/
├── data/
│   ├── raw/
│   │   └── water/
│   │       ├── lakes/        # ne_10m_lakes.shp (Natural Earth)
│   │       └── rivers/       # ne_10m_rivers_lake_centerlines_scale_rank.shp
│   ├── interim/              # empty
│   └── processed/            # empty
├── scripts/
│   ├── plot_elephants.py     # main entry point / "warm fuzzy" visualization script
│   └── load_data.py          # data loading helper (not yet reviewed)
├── src/
│   └── wildlife_water_stress_atlas/
│       ├── ingest/
│       │   ├── gbif.py       # GBIF API fetch → GeoDataFrame
│       │   └── water.py      # shapefile loading + combining
│       ├── analytics/
│       │   ├── apply.py      # applies scoring function across GeoDataFrame
│       │   ├── overlap.py    # distance-to-water calculation
│       │   ├── scoring.py    # stress score + classify functions
│       │   ├── spatial.py    # grid aggregation
│       │   └── water_access.py  # species-specific water type filtering
│       └── visualization/
│           └── maps.py       # matplotlib plotting utilities
└── tests/
    ├── test_apply.py
    ├── test_gbif.py
    ├── test_overlap.py
    ├── test_scoring.py
    ├── test_spatial.py
    ├── test_water.py
    ├── test_water_real_data.py   # hits real filesystem — integration test
    └── test_accessible_water.py
```

### What Each File Does

**`ingest/gbif.py`**  
Fetches species occurrence records from GBIF API. Clean and well-structured.  
- `fetch_occurrences(scientific_name, limit)` → list of dicts  
- `occurrences_to_gdf(records)` → GeoDataFrame (WGS84 points)  
- Known gap: capped at 300 records per request, no pagination yet. Needs `offset` loop for full coverage.

**`ingest/water.py`**  
Loads water shapefiles. Currently only knows about rivers and lakes.  
- `load_rivers(filepath)` → GeoDataFrame  
- `load_lakes(filepath)` → GeoDataFrame  
- `combine_water_layers(*layers)` → GeoDataFrame  
- Known gap: format-coupled to shapefiles only, no normalized schema, no mechanism/permanence metadata. Refactor planned (see Section 5).

**`analytics/apply.py`**  
Clean dependency-injection pattern. Applies any scoring function across a GeoDataFrame.  
- `apply_water_stress_score(gdf, scoring_func)` → GeoDataFrame with `water_stress_score` column  
- Requires `distance_to_water` and `species` columns on input GDF. Raises `KeyError` if missing.  
- Well tested. No changes needed now.

**`analytics/overlap.py`**  
Computes distance from each animal occurrence to nearest water source.  
- `add_distance_to_water(elephants, rivers)` → GeoDataFrame with `distance_to_water` column  
- **Known bug**: parameter names hardcoded to `elephants` and `rivers`. Accepts any water GDF in practice but the naming causes confusion and the function only measures distance to whatever is passed — if only rivers are passed, pans and wetlands are invisible. This is the root cause of the "phantom thirst" problem on the map.

**`analytics/scoring.py`**  
Stress scoring logic. Well-documented with explicit acknowledgment that thresholds are placeholders.  
- `water_stress_score(distance_meters, species)` → float 0–1  
- `classify_stress_level(score)` → "low" | "moderate" | "high"  
- `SPECIES_WATER_THRESHOLDS` dict: currently only `Loxodonta africana: 300_000`  
- **Known gap**: species config is split across three files (see Section 5).

**`analytics/spatial.py`**  
Aggregates point-level stress scores into a grid for visualization.  
- `aggregate_stress_to_grid(gdf, cell_size_meters)` → GeoDataFrame of grid cells  
- Produces `water_stress_score` (mean), `high_stress_count`, `total`, `high_stress_pct` per cell.  
- This is what produces the red grid cells visible on the map.

**`analytics/water_access.py`**  
Species-specific water type filtering and weighting.  
- `filter_accessible_water(water, species)` → filtered GeoDataFrame  
- `get_water_type_weights(species)` → dict  
- `SPECIES_ACCESSIBLE_WATER_TYPES`: currently only `{"river", "lake"}` for elephants  
- `WATER_TYPE_WEIGHTS`: currently `river: 1.0, lake: 1.0` for elephants  
- **Known gap**: doesn't know about pans, wetlands, floodplains, groundwater. This + overlap.py together cause the phantom thirst bug.

**`visualization/maps.py`**  
Static matplotlib plots. Function names hardcoded to elephants/rivers.  
- `plot_elephants_and_rivers(elephants, water)`  
- `plot_water_stress(gdf, accessible_water, high_stress)`  
- Will be replaced/supplemented by Folium or PyDeck for interactive Streamlit maps.

**`scripts/plot_elephants.py`**  
The main pipeline entry point. Not part of the package — lives in scripts/.  
Orchestrates: fetch GBIF → load water → filter accessible → distance → score → classify → grid → plot.  
Hardcodes `"Loxodonta africana"` in two places. Constants `CELL_SIZE_METERS = 50_000` and `HIGH_RISK_THRESHOLD = 0.6`.  
Not tested directly (it's a script). Core library functions it calls are tested.

### Current Data Sources
| Layer | File | Source | Format |
|---|---|---|---|
| Rivers | ne_10m_rivers_lake_centerlines_scale_rank.shp | Natural Earth | Shapefile |
| Lakes | ne_10m_lakes.shp | Natural Earth | Shapefile |
| Elephant occurrences | GBIF API (live) | GBIF | API / GeoDataFrame |

### What the Map Shows Right Now
- Blue lines: rivers and lakes from Natural Earth
- Red grid cells: 50km grid cells where elephant stress score > 0.6
- The red dots around lat -20, lon 13–15 (Namibia) are elephants appearing "thirsty" because the Etosha Pan and surrounding water sources are not in the water layer yet — this is the known phantom thirst bug.

---

## 4. Known Bugs and Gaps

### Bug: Phantom Thirst (Priority Fix)
**Symptom**: Elephants near Etosha Pan (Namibia), Nwetwe Pan, Sua Pan (Botswana), and the Niger/Chad/Nigeria floodplain region appear high-stress because those water sources don't exist in the current data.  
**Root cause**: `water_access.py` only knows `river` and `lake`. `overlap.py` only measures distance to whatever is passed in. Pans, wetlands, floodplains, and seasonal water are completely invisible.  
**Fix**: Add new water source layers (GLWD, JRC GSW) + register new water types in `water_access.py`.

### Gap: Missing Water Source Types
The following water types exist in the real world and affect elephant behavior but are not in the data:

| Type | Why it matters | Dataset |
|---|---|---|
| Pans / playas | Etosha, Makgadikgadi, Sua — elephants use these | GLWD v2 class 7 |
| Floodplains | Niger/Chad basin, Zambezi, Okavango | GLWD v2 class 4 |
| Intermittent wetlands | Seasonal fill after rain | GLWD v2 class 9 / JRC GSW |
| Seasonal surface water | Water present <75% of year | JRC GSW occurrence layer |
| Springs & seeps | Groundwater at surface, critical in dry season | Africa Groundwater Atlas |
| Aquifer zones | Subsurface water elephants dig for | Africa Groundwater Atlas |
| Reservoirs & dams | Man-made impoundments | Global Dam Watch (GDW) |
| Boreholes / waterholes | Park management water (Hwange, Kruger, Etosha) | OpenStreetMap / park data |

### Gap: Species Config Split Across Three Files
`SPECIES_WATER_THRESHOLDS` in `scoring.py`, `SPECIES_ACCESSIBLE_WATER_TYPES` and `WATER_TYPE_WEIGHTS` in `water_access.py`. Adding a new species requires editing multiple files. Needs a single species config registry.

### Gap: GBIF Pagination
`fetch_occurrences` is capped at the limit parameter with no pagination. GBIF returns max 300 per request. Need offset-based pagination loop for full coverage.

### Gap: `overlap.py` Parameter Naming
`add_distance_to_water(elephants, rivers)` — naming implies it only works with elephants and rivers. Rename to `add_distance_to_water(occurrences, water)` and ensure all water types are passed in.

### Gap: No Temporal Dimension Yet
All analysis is static. Seasonal variation in water availability, historical trends, and future predictions are not yet modeled.

### Gap: No Human Pressure Layer
Fences, roads, settlements, and farmland block animal movement to water. This is arguably more immediately impactful than climate change for many African elephant populations and is the planned second pressure type.

### Gap: Water Quality Not Modeled
Toxic algae, high salinity, bacterial contamination make water physically present but functionally inaccessible. No quality layer exists yet.

---

## 5. Planned Refactoring

### Non-Negotiable Development Rules
- **Strict TDD**: tests written before code, always
- **CI/CD pipeline**: unit tests + linting + vulnerability scans minimum on every push
- **Never hardcode species names** anywhere in library code

### Priority 1: Species Config Registry
Create a single source of truth for species configuration. All modules read from it.

```python
# src/wildlife_water_stress_atlas/config/species.py
SPECIES_CONFIG = {
    "Loxodonta africana": {
        "common_name": "African elephant",
        "water_threshold_m": 300_000,
        "accessible_water_types": {"river", "lake", "pan", "wetland", "floodplain"},
        "water_type_weights": {"river": 1.0, "lake": 1.0, "pan": 0.8, ...},
        "daily_range_m": 50_000,
        "water_dependency": "high",
    }
}
```

`scoring.py` and `water_access.py` both import from here. Adding a species = one dict entry.

### Priority 2: Fix overlap.py Parameter Names
Rename `elephants` → `occurrences`, `rivers` → `water`. Logic unchanged, naming fixed.

### Priority 3: water.py Refactor — Source Class Pattern
Transform `water.py` from format-coupled load functions into a normalized schema-driven registry.

Every water source produces the same columns:
```
geometry, source_id, mechanism, water_type, permanence, 
reliability, months_water, region
```

New source classes (all inherit from `WaterSource` ABC):
- `ShapefileRivers` — wraps existing load_rivers
- `ShapefileLakes` — wraps existing load_lakes
- `GLWDWetlands` — raster, vectorizes wetland class pixels
- `JRCGlobalSurfaceWater` — raster, vectorizes by occurrence threshold
- `AfricaGroundwaterAtlas` — shapefile, aquifer zones
- `GDWReservoirs` — shapefile, dams and reservoirs

Registry pattern:
```python
config = {
    "region": "africa",
    "sources": {
        "rivers":  {"path": "data/raw/..."},
        "lakes":   {"path": "data/raw/..."},
        "glwd":    {"path": "data/raw/..."},
        "jrc_gsw": {"path": "data/raw/...", "min_occurrence": 10},
    }
}
water = load_all_water(config, bbox=(lon_min, lat_min, lon_max, lat_max))
```

Legacy shims kept for backward compatibility during transition.

### Priority 4: water_access.py — Register New Water Types
Once new source classes exist, register pans, wetlands, floodplains as accessible to elephants. This directly fixes the phantom thirst bug.

### Priority 5: New Dependency
Add `rasterio` to `requirements.txt` and `pyproject.toml` for raster source classes.

---

## 6. Data Sources — Full Inventory

### Currently Ingested
| Dataset | Type | Coverage | Key Use |
|---|---|---|---|
| Natural Earth rivers | Shapefile | Global | River network |
| Natural Earth lakes | Shapefile | Global | Lake polygons |
| GBIF API | REST API | Global | Species occurrences |

### Planned — Water Layers
| Dataset | Type | Coverage | Key Use | URL |
|---|---|---|---|---|
| GLWD v2 | Raster (GeoTIFF) | Global | Pans, wetlands, floodplains | hydrosheds.org/products/glwd |
| JRC Global Surface Water | Raster (GeoTIFF) | Global | Seasonal/ephemeral water | global-surface-water.appspot.com |
| Africa Groundwater Atlas | Shapefile | Africa | Springs, aquifer zones | africagroundwateratlas.org |
| Global Dam Watch (GDW) | Shapefile | Global | Reservoirs, dams | globaldamwatch.org |
| HydroLAKES | Shapefile | Global | Improved lake coverage | hydrosheds.org |
| HydroRIVERS | Shapefile | Global | Improved river network | hydrosheds.org |
| OpenStreetMap | API / extract | Global | Boreholes, waterholes | overpass-api.de |

### Planned — Climate & Environmental
| Dataset | Type | Coverage | Key Use |
|---|---|---|---|
| CHIRPS rainfall | Raster | Global (50°S–50°N) | Rainfall proxy for vegetation water, seasonal patterns, backtesting |
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

```
┌─────────────────────────────────────────────────────┐
│                   Species Config                     │
│  (name, threshold, water types, weights, range...)   │
└──────────────────────┬──────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
┌─────────────────┐      ┌──────────────────────┐
│  Occurrence     │      │   Water Sources       │
│  Data (GBIF /   │      │   (all mechanisms,    │
│  Movebank)      │      │    unified schema)    │
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
         └──────────┬──────────┘
                    ▼
    ┌───────────────┼───────────────┐
    ▼               ▼               ▼
Describe         Predict         Prescribe
(now)         (future climate  (intervention
              + human change)   zones, refuge
                                 viability)
                    │
                    ▼
         ┌─────────────────────┐
         │   Streamlit App     │
         │   + Folium/PyDeck   │
         │   Interactive Map   │
         └─────────────────────┘
```

### Planned Tech Stack
| Layer | Technology | Notes |
|---|---|---|
| Core library | Python 3.12 | Existing |
| Geospatial | GeoPandas, Shapely, Rasterio | Rasterio to be added |
| Data fetch | Requests (GBIF), standard file I/O | |
| Visualization | Folium or PyDeck (interactive) | Replaces/supplements matplotlib |
| Web app | Streamlit | ~10 lines to wrap existing pipeline |
| Hosting (now) | Streamlit Community Cloud | Free, GitHub-connected, auto-deploy |
| Hosting (future) | AWS | When scheduled jobs or DB needed |
| Testing | pytest | Existing, strict TDD |
| CI/CD | GitHub Actions | Unit tests + linting + vuln scan |

---

## 8. The Three Phases in Detail

### Phase 1 — Describe (Current Focus)
**Goal**: Accurate picture of current water stress for African elephants.  
**Definition of done**:
- All major water source types ingested (rivers, lakes, pans, wetlands, floodplains, seasonal water)
- Phantom thirst bug fixed
- Distance-to-nearest-water accurate for all source types
- Stress score computed per occurrence
- Visualized on interactive map in Streamlit
- Species config extensible (add zebra without touching library code)

### Phase 2 — Predict
**Goal**: Forecast how water availability will change over 10/20/50 years.  
**Key challenges**:
- Requires climate model outputs (CMIP6 scenarios — hard but achievable)
- Temporal dimension must be first-class in the data model
- Validation strategy: backtest using JRC GSW 1984–2021 history + CHIRPS rainfall
- Potential collaborators: IUCN, WWF climate teams, academic institutions
- CHIRPS gives rainfall back to 1981 — this is the backtest foundation

### Phase 3 — Prescribe
**Goal**: Identify where conservation intervention will be most effective.  
**Outputs**:
- High-impact intervention zones (protect water here → save population)
- Viable refuge areas (if current habitat becomes untenable)
- Human-wildlife conflict zones to flag (not recommend)
**Required additional data**:
- WDPA protected area boundaries
- Human settlement density
- Movement corridor analysis
**Important caveats**:
- Relocation recommendations need domain expert validation
- Community/indigenous land rights must be incorporated
- Frame as "refuge viability assessment" not "move elephants here"

---

## 9. What We Knowingly Omit (For Now)

These are real ecological factors we acknowledge but are consciously deferring:

- **Predation pressure at water points** — lions controlling access to water holes
- **Water quality modeling** — toxic algae, salinity, bacterial contamination (acknowledged, no data yet)
- **Survivorship bias in occurrence data** — animals that died of thirst aren't in GBIF
- **Social hierarchy at water points** — dominant bulls blocking access for others
- **Mineral licks** — animals travel for minerals, not just water, may confound movement data
- **Fog/atmospheric water** — real in Namib/Atacama, no global dataset exists yet
- **Animal-created water sources** — elephant-dug wells (infer from aquifer zones as proxy)

---

## 10. Immediate Next Steps (Prioritized)

1. **Add `rasterio` to requirements** and pyproject.toml
2. **Create `config/species.py`** — species registry, tests first
3. **Rename `overlap.py` parameters** — `elephants`→`occurrences`, `rivers`→`water`, update tests
4. **Refactor `water.py`** — source class pattern with normalized schema, legacy shims, tests first
5. **Update `water_access.py`** — register new water types for elephants
6. **Download GLWD v2 and JRC GSW** — add to `data/raw/water/`
7. **Add new source classes** — `GLWDWetlands`, `JRCGlobalSurfaceWater`, tests first
8. **Verify phantom thirst fix** on map — Namibian elephants should show lower stress
9. **Add GBIF pagination** to `gbif.py`
10. **Begin Streamlit app scaffold** — thin wrapper over existing pipeline

---

## 11. Notes for Future Claude Sessions

- The developer uses **strict TDD** — always write tests before implementation. This is non-negotiable.
- **Never hardcode species names** in library code. Always use the species config registry.
- The project is in **Python 3.12**, packaged with `pyproject.toml`, installed as editable (`pip install -e .`).
- Data files live in `data/raw/` and are **not committed to git** (too large). Scripts fetch or reference them locally.
- `scripts/plot_elephants.py` is a **developer visualization script**, not part of the library. Don't add tests for `main()` — test the library functions it calls.
- `test_water_real_data.py` hits the **real filesystem** — it's an integration test. Keep it separated from unit tests in CI so it doesn't block fast runs.
- The **phantom thirst bug** (elephants near Etosha appearing high-stress) is the current priority fix. Root cause: `water_access.py` only knows rivers and lakes; pans and wetlands are invisible.
- When discussing water sources, think in **mechanisms** (permanent surface, seasonal surface, groundwater, artificial, derived) not just types. This is how the architecture scales globally.
- The eventual deployment target is **Streamlit Community Cloud** (free tier) with a possible future move to AWS when scheduled jobs are needed.
- The developer wants to eventually reach out to **conservation organizations** (Save the Elephants, IUCN African Elephant Specialist Group) for ecological validation of stress model parameters. This is a future step, not current.
