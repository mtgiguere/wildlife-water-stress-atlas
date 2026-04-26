# Wildlife Water Stress Atlas

A geospatial decision-support platform that models wildlife survival risk
as a function of freshwater access and environmental pressure.

---

## What It Does

Maps water stress for wildlife populations by computing the distance from
species occurrence records to the nearest accessible water source, scoring
that distance against species-specific thresholds, and visualizing the
results on a grid map.

The current focus is African elephants (*Loxodonta africana*) across the
African continent, using a multi-source water layer that includes rivers,
wetlands, pans, floodplains, saline lakes, and seasonal surface water.

This is Phase 1 of a three-phase system:
1. **Describe** — current water stress (working)
2. **Predict** — how water availability changes with climate (planned)
3. **Prescribe** — conservation intervention zones and refuge viability (planned)

---

## The Map

The pipeline produces a 50km grid map of Africa showing relative water
stress for elephant occurrence records. Blue features are water sources.
Grid cells are colored by stress score where data exists.

Current score range: 0.000 – 0.195 — no elephant in the current GBIF
sample is more than ~58km from a mapped water source. This is a significant
improvement over the previous pipeline which falsely showed elephants near
Etosha Pan and the Botswana pans as highly stressed — those water sources
are now correctly captured in the data layer.

---

## Water Data Sources

| Source | Type | What It Adds |
|---|---|---|
| Natural Earth rivers | Shapefile (lines) | River network — kept as lines for distance calc accuracy |
| GLWD v2 | GeoTIFF (raster) | Wetlands, pans, floodplains, saline lakes, ephemeral water |
| JRC Global Surface Water | GeoTIFF tiles | Seasonal and ephemeral surface water by occurrence frequency |
| GBIF API | REST API | Species occurrence records (live fetch) |

GLWD v2 is the Global Lakes and Wetlands Database version 2 (Lehner et al.,
2025), distributed under Creative Commons Attribution 4.0. It classifies
inland water into 33 types at 500m resolution. Key classes used here include
saline lakes (Etosha), salt pans (Makgadikgadi, Sua), floodplains, and
seasonal wetlands.

---

## Architecture

The pipeline is built around three core principles:

**Species config is a single source of truth.**
`config/species.py` holds all species-specific parameters — water distance
thresholds, accessible water types, reliability weights, daily range. Adding
a new species means adding one dict entry. No other code changes.

**Water sources share a normalized schema.**
Every source class produces the same columns: `geometry`, `source_id`,
`water_type`, `mechanism`, `permanence`, `reliability`, `months_water`,
`region`. Rivers, lakes, raster wetlands, and future groundwater sources
are all interchangeable downstream.

**Data gaps are insights, not failures.**
GBIF records include imprecise coordinates, historical specimens, and
potentially captive animals. These are intentionally preserved — they
surface funding needs, highlight understudied populations (the Mali desert
elephants are real and remarkable), and demonstrate the need for better
field data collection. The Prescribe phase will expose data confidence
scores per grid cell explicitly.

---

## Running the Pipeline

```bash
# Install dependencies
pip install -e .

# Run the visualization script
python scripts/plot_elephants.py
```

Data files are not committed to git (too large). Required files:
- `data/raw/water/rivers/ne_10m_rivers_lake_centerlines_scale_rank.shp` — Natural Earth
- `data/raw/water/glwd/GLWD_v2_0_main_class.tif` — HydroSHEDS GLWD v2
- `data/raw/water/jrc_gsw/` — JRC Global Surface Water tiles (Africa)

---

## Development

Strict TDD — tests written before implementation, always.

```bash
# Run tests
pytest

# Lint
ruff check . --fix
ruff format .
```

Current test coverage: **166 tests, 100% coverage**.

---

## Project Status

| Component | Status |
|---|---|
| Species config registry | ✅ Done |
| Water source class architecture | ✅ Done |
| GLWD v2 integration (wetlands, pans, floodplains) | ✅ Done |
| JRC Global Surface Water (single tile) | ✅ Done |
| Phantom thirst bug (Etosha, Botswana pans) | ✅ Fixed |
| JRC multi-tile loading | 🔧 In progress |
| GBIF pagination | 📋 Planned |
| Streamlit web app | 📋 Planned |
| CI/CD pipeline (GitHub Actions) | 📋 Planned |
| Data confidence layer | 📋 Planned |
| Human pressure layer (roads, fences) | 📋 Planned |
| Phase 2 — Predict (climate modeling) | 📋 Future |
| Phase 3 — Prescribe (intervention zones) | 📋 Future |

---

## Citation

If using GLWD v2 data, please cite:

Lehner, B., et al. (2025). Mapping the world's inland surface waters: an
upgrade to the Global Lakes and Wetlands Database (GLWD v2). Earth System
Science Data. https://doi.org/10.6084/m9.figshare.28519994