"""
plot_elephants.py

Fetch elephant occurrences, score water stress, aggregate to a grid,
and visualize higher-risk water stress zones.
"""

import matplotlib.pyplot as plt

from wildlife_water_stress_atlas.analytics.apply import apply_water_stress_score
from wildlife_water_stress_atlas.analytics.overlap import add_distance_to_water
from wildlife_water_stress_atlas.analytics.scoring import water_stress_score, classify_stress_level
from wildlife_water_stress_atlas.analytics.spatial import (
    aggregate_stress_to_grid,
)
from wildlife_water_stress_atlas.ingest.gbif import (
    fetch_occurrences,
    occurrences_to_gdf,
)
from wildlife_water_stress_atlas.ingest.water import (
    combine_water_layers,
    load_lakes,
    load_rivers,
)
from wildlife_water_stress_atlas.analytics.water_access import (
    filter_accessible_water,
)

CELL_SIZE_METERS = 50_000
HIGH_RISK_THRESHOLD = 0.6


def main():
    records = fetch_occurrences("Loxodonta africana", limit=200)
    occurrences = occurrences_to_gdf(records)

    rivers = load_rivers(
        "data/raw/water/rivers/ne_10m_rivers_lake_centerlines_scale_rank.shp"
    )
    lakes = load_lakes("data/raw/water/lakes/ne_10m_lakes.shp")

    rivers["type"] = "river"
    lakes["type"] = "lake"
    water_layers = {
        "rivers": rivers,
        "lakes": lakes,
    }
    all_water = combine_water_layers(*water_layers.values())

    accessible_water = filter_accessible_water(
        all_water,
        species="Loxodonta africana",
    )

    occurrences = add_distance_to_water(occurrences, accessible_water)
    occurrences = apply_water_stress_score(occurrences, water_stress_score)
    occurrences["stress_level"] = occurrences["water_stress_score"].apply(
        classify_stress_level
    )

    grid_gdf = aggregate_stress_to_grid(
        occurrences,
        cell_size_meters=CELL_SIZE_METERS,
    )

    high_risk_grid = grid_gdf[grid_gdf["water_stress_score"] > HIGH_RISK_THRESHOLD]

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

    ax.set_title("High-Risk Water Stress Grid")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")

    plt.show()


if __name__ == "__main__":
    main()