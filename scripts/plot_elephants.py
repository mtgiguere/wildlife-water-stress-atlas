from wildlife_water_stress_atlas.ingest.gbif import (
    fetch_occurrences,
    occurrences_to_gdf,
)
from wildlife_water_stress_atlas.analytics.overlap import add_distance_to_water
from wildlife_water_stress_atlas.analytics.apply import apply_water_stress_score
from wildlife_water_stress_atlas.analytics.scoring import water_stress_score
from wildlife_water_stress_atlas.visualization.maps import plot_water_stress
import geopandas as gpd


def main():
    records = fetch_occurrences("Loxodonta africana", limit=200)

    gdf = occurrences_to_gdf(records)

    # load rivers (adjust path if needed)
    rivers = gpd.read_file("data/raw/water/rivers/ne_10m_rivers_lake_centerlines_scale_rank.shp")

    # compute distance
    gdf = add_distance_to_water(gdf, rivers)

    # compute stress
    gdf = apply_water_stress_score(gdf, water_stress_score)

    # TEMP: verify
    print(gdf[["species", "distance_to_water", "water_stress_score"]].head())

    plot_water_stress(gdf, rivers)

if __name__ == "__main__":
    main()