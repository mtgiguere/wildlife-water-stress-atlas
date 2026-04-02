"""
plot_elephants.py

Fetch elephant occurrences, score water stress, aggregate to a grid,
and visualize higher-risk water stress zones.
"""

import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import box

from wildlife_water_stress_atlas.analytics.apply import apply_water_stress_score
from wildlife_water_stress_atlas.analytics.overlap import add_distance_to_water
from wildlife_water_stress_atlas.analytics.scoring import water_stress_score
from wildlife_water_stress_atlas.ingest.gbif import (
    fetch_occurrences,
    occurrences_to_gdf,
)
from wildlife_water_stress_atlas.ingest.water import (
    combine_water_layers,
    load_lakes,
    load_rivers,
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

    water_layers = {
        "rivers": rivers,
        "lakes": lakes,
    }
    accessible_water = combine_water_layers(*water_layers.values())

    occurrences = add_distance_to_water(occurrences, accessible_water)
    occurrences = apply_water_stress_score(occurrences, water_stress_score)

    occurrences_projected = occurrences.to_crs(epsg=3857)
    occurrences_projected["x_bin"] = (
        occurrences_projected.geometry.x // CELL_SIZE_METERS
    ) * CELL_SIZE_METERS
    occurrences_projected["y_bin"] = (
        occurrences_projected.geometry.y // CELL_SIZE_METERS
    ) * CELL_SIZE_METERS

    grouped = (
        occurrences_projected.groupby(["x_bin", "y_bin"])["water_stress_score"]
        .mean()
        .reset_index()
    )

    grouped["geometry"] = grouped.apply(
        lambda row: box(
            row["x_bin"],
            row["y_bin"],
            row["x_bin"] + CELL_SIZE_METERS,
            row["y_bin"] + CELL_SIZE_METERS,
        ),
        axis=1,
    )

    grid_gdf = gpd.GeoDataFrame(
        grouped,
        geometry="geometry",
        crs="EPSG:3857",
    ).to_crs(epsg=4326)

    high_risk_grid = grid_gdf[grid_gdf["water_stress_score"] > HIGH_RISK_THRESHOLD]

    fig, ax = plt.subplots(figsize=(12, 8))

    accessible_water.plot(ax=ax, color="blue", linewidth=0.5, alpha=0.4)

    high_risk_grid.plot(
        ax=ax,
        column="water_stress_score",
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