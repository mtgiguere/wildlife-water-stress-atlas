from wildlife_water_stress_atlas.ingest.gbif import (
    fetch_occurrences,
    occurrences_to_gdf,
)
from wildlife_water_stress_atlas.visualization.maps import plot_occurrences


def main():
    records = fetch_occurrences("Loxodonta africana", limit=200)

    gdf = occurrences_to_gdf(records)

    plot_occurrences(gdf)


if __name__ == "__main__":
    main()