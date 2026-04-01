import geopandas as gpd
import matplotlib.pyplot as plt


def plot_occurrences_with_water(elephants, rivers):
    fig, ax = plt.subplots(figsize=(10, 6))

    rivers.plot(ax=ax, linewidth=0.5)
    elephants.plot(ax=ax, markersize=5)

    ax.set_title("Elephants and Freshwater")

    plt.show()