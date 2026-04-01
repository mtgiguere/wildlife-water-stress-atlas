"""
maps.py

Simple plotting utilities for geospatial layers.
"""

import geopandas as gpd
import matplotlib.pyplot as plt


def plot_elephants_and_rivers(elephants, water):
    fig, ax = plt.subplots(figsize=(12, 8))

    # Plot water (lakes + rivers)
    water.plot(ax=ax, color="blue", linewidth=0.5, alpha=0.5)

    # Plot elephants colored by distance
    elephants.plot(
        ax=ax,
        column="distance_to_water",
        markersize=10,
        legend=True,
    )

    ax.set_title("Elephants and Water (Rivers + Lakes)")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")

    plt.show()