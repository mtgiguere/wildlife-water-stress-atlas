import geopandas as gpd
from shapely.geometry import LineString, Point

from wildlife_water_stress_atlas.analytics.overlap import add_distance_to_water


def test_add_distance_to_water_adds_distance_column():
    elephants = gpd.GeoDataFrame(
        {"species": ["Loxodonta africana"]},
        geometry=[Point(1, 1)],
        crs="EPSG:4326",
    )

    rivers = gpd.GeoDataFrame(
        {"name": ["Test River"]},
        geometry=[LineString([(0, 0), (0, 2)])],
        crs="EPSG:4326",
    )

    result = add_distance_to_water(elephants, rivers)

    assert "distance_to_water" in result.columns
    assert len(result) == 1
    assert result.loc[0, "distance_to_water"] >= 0