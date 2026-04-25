"""
plot_elephants.py

Fetch elephant occurrences, score water stress, aggregate to a grid,
and visualize higher-risk water stress zones.

WHAT CHANGED FROM THE PREVIOUS VERSION:
----------------------------------------
- load_rivers() / load_lakes() / combine_water_layers() replaced by
  load_all_water() — the new registry-based pipeline that includes
  GLWD wetlands/pans and JRC Global Surface Water alongside rivers and lakes.
- Manual "type" column assignment removed — source classes now set water_type
  as part of the normalized schema automatically.
- Africa bbox added to load_all_water() — prevents loading global datasets
  into memory and satisfies the bbox warning.
- Species name moved to a single constant — SPECIES at the top of the file.
  Previously hardcoded in two places.
"""

import matplotlib.pyplot as plt

from wildlife_water_stress_atlas.analytics.apply import apply_water_stress_score
from wildlife_water_stress_atlas.analytics.overlap import add_distance_to_water
from wildlife_water_stress_atlas.analytics.scoring import classify_stress_level, water_stress_score
from wildlife_water_stress_atlas.analytics.spatial import aggregate_stress_to_grid
from wildlife_water_stress_atlas.analytics.water_access import filter_accessible_water
from wildlife_water_stress_atlas.ingest.gbif import fetch_occurrences, occurrences_to_gdf
from wildlife_water_stress_atlas.ingest.water import load_all_water

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Single place to change the species — never hardcoded below this line
SPECIES = "Loxodonta africana"

CELL_SIZE_METERS  = 50_000
HIGH_RISK_THRESHOLD = 0.1

# Africa bounding box (min_lon, min_lat, max_lon, max_lat)
# Covers the full continent with a small buffer
AFRICA_BBOX = (-20, -40, 55, 40)

# Water source config — add new sources here as data becomes available
WATER_CONFIG = {
    "sources": {
        "rivers": {
            "path":   "data/raw/water/rivers/ne_10m_rivers_lake_centerlines_scale_rank.shp",
            "region": "africa",
        },
        "lakes": {
            "path":   "data/raw/water/lakes/ne_10m_lakes.shp",
            "region": "africa",
        },
        "glwd": {
            "path":   "data/raw/water/glwd/GLWD_v2_0_main_class.tif",
            "region": "africa",
            # water_classes defaults to {4, 7, 9} — floodplains, pans, wetlands
        },
        # "jrc_gsw": {
        #     "path":           "data/raw/water/jrc_gsw/",
        #     "region":         "africa",
        #     "min_occurrence": 10,
        # },
    }
}


def main():
    # ------------------------------------------------------------------
    # 1. Fetch species occurrences from GBIF
    # ------------------------------------------------------------------
    records     = fetch_occurrences(SPECIES, limit=200)
    occurrences = occurrences_to_gdf(records)

    # ------------------------------------------------------------------
    # 2. Load all water sources via the registry
    #
    # load_all_water() instantiates the appropriate source class for each
    # entry in WATER_CONFIG, normalizes them to the same schema, and
    # combines them into a single GeoDataFrame. The bbox clips all sources
    # to Africa so global rasters don't load into memory in full.
    # ------------------------------------------------------------------
    all_water = load_all_water(WATER_CONFIG, bbox=AFRICA_BBOX)

    # ------------------------------------------------------------------
    # 3. Filter to water types accessible to this species
    #
    # filter_accessible_water() reads accessible_water_types from
    # SPECIES_CONFIG — now includes pans, wetlands, floodplains, and
    # surface_water in addition to rivers and lakes.
    # This is what fixes the phantom thirst bug.
    # ------------------------------------------------------------------
    accessible_water = filter_accessible_water(all_water, species=SPECIES)

    # ------------------------------------------------------------------
    # 4. Score water stress per occurrence
    # ------------------------------------------------------------------
    occurrences = add_distance_to_water(occurrences, accessible_water)
    occurrences = apply_water_stress_score(occurrences, water_stress_score)
    occurrences["stress_level"] = occurrences["water_stress_score"].apply(
        classify_stress_level
    )

    # ------------------------------------------------------------------
    # 5. Aggregate to grid and extract high-risk cells
    # ------------------------------------------------------------------
    grid_gdf = aggregate_stress_to_grid(
        occurrences,
        cell_size_meters=CELL_SIZE_METERS,
    )

    high_risk_grid = grid_gdf[grid_gdf["water_stress_score"] > HIGH_RISK_THRESHOLD]


    print(f"Occurrences scored: {len(occurrences)}")
    print(f"Grid cells: {len(grid_gdf)}")
    print(f"High risk cells: {len(high_risk_grid)}")
    print(f"Score range: {occurrences['water_stress_score'].min():.3f} – {occurrences['water_stress_score'].max():.3f}")

    # ------------------------------------------------------------------
    # 6. Plot
    # ------------------------------------------------------------------

    if high_risk_grid.empty:
        print("No high-risk grid cells found — try lowering HIGH_RISK_THRESHOLD")
        # Plot just the water layer so we can still see something
        fig, ax = plt.subplots(figsize=(12, 8))
        accessible_water.plot(ax=ax, color="blue", linewidth=0.5, alpha=0.4)
        ax.set_title(f"Water Sources — {SPECIES} (no high-risk cells found)")
        plt.show()
        return

    fig, ax = plt.subplots(figsize=(12, 8))

    accessible_water.plot(ax=ax, color="blue", linewidth=0.5, alpha=0.4)

    high_risk_grid.plot(
        ax=ax,
        column="high_stress_pct",
        cmap="Reds",
        legend=True,
        alpha=0.8,
        edgecolor="black",
        linewidth=0.3,
    )

    ax.set_title(f"High-Risk Water Stress Grid — {SPECIES}")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")

    
    plt.show()


if __name__ == "__main__":
    main()