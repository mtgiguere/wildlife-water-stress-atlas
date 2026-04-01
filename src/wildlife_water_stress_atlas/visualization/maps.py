"""
maps.py

Simple plotting utilities for geospatial layers.
"""

import geopandas as gpd
import matplotlib.pyplot as plt


def plot_elephants_and_rivers(elephants: gpd.GeoDataFrame, rivers: gpd.GeoDataFrame) -> None:
    """
    Plot elephant occurrence points over river centerlines.
    """
    fig, ax = plt.subplots(figsize=(12, 8))

    rivers.plot(ax=ax, linewidth=0.4, color="blue")
    elephants.plot(ax=ax, markersize=10, color="red")

    ax.set_title("Elephant Occurrences and Rivers")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")

    plt.show()