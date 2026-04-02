'''load_data.py'''

import matplotlib.pyplot as plt

from wildlife_water_stress_atlas.analytics.overlap import add_distance_to_water
from wildlife_water_stress_atlas.ingest.gbif import (
    fetch_occurrences,
    occurrences_to_gdf,
)
from wildlife_water_stress_atlas.ingest.water import (
    combine_water_layers,
    load_lakes,
    load_rivers,
)
from wildlife_water_stress_atlas.visualization.maps import plot_elephants_and_rivers


def main():
    records = fetch_occurrences("Loxodonta africana", limit=200)
    elephants = occurrences_to_gdf(records)

    #load rivers and lakes
    rivers = load_rivers("data/raw/water/rivers/ne_10m_rivers_lake_centerlines_scale_rank.shp")
    lakes = load_lakes("data/raw/water/lakes/ne_10m_lakes.shp")
    #then combine them

    water_layers = {
        "rivers": rivers,
        "lakes": lakes,
    }

    accessible_water = combine_water_layers(*water_layers.values())

    elephants_with_distance = add_distance_to_water(elephants, accessible_water)

    print(elephants_with_distance["distance_to_water"].describe())
    print(f"Mean distance to water: {elephants_with_distance['distance_to_water'].mean() / 1000:.2f} km")
    print(f"Median distance to water: {elephants_with_distance['distance_to_water'].median() / 1000:.2f} km")
    print(f"Max distance to water: {elephants_with_distance['distance_to_water'].max() / 1000:.2f} km")

    plot_elephants_and_rivers(elephants_with_distance, accessible_water)
    elephants_with_distance["distance_to_water"].hist(bins=20)

    plt.title("Distance to Water Distribution (meters)")
    plt.xlabel("Distance (m)")
    plt.ylabel("Count")

    plt.show()


if __name__ == "__main__":
    main()