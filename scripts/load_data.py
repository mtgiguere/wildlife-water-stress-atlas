from wildlife_water_stress_atlas.ingest.gbif import (
    fetch_occurrences,
    occurrences_to_gdf,
)
from wildlife_water_stress_atlas.ingest.water import load_rivers
from wildlife_water_stress_atlas.visualization.maps import plot_elephants_and_rivers


def main():
    records = fetch_occurrences("Loxodonta africana", limit=200)
    elephants = occurrences_to_gdf(records)

    rivers = load_rivers("data/raw/water/ne_10m_rivers_lake_centerlines_scale_rank.shp")

    plot_elephants_and_rivers(elephants, rivers)


if __name__ == "__main__":
    main()