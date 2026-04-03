import geopandas as gpd
from shapely.geometry import LineString, Point

def test_filter_accessible_water_for_species():
    from wildlife_water_stress_atlas.analytics.water_access import (
        filter_accessible_water,
    )

    water = gpd.GeoDataFrame(
        {
            "type": ["river", "lake"],
        },
        geometry=[
            LineString([(0, 0), (1, 1)]),
            Point(5, 5),
        ],
        crs="EPSG:4326",
    )

    result = filter_accessible_water(water, species="Loxodonta africana")

    assert not result.empty
    assert all(result["type"].isin(["river", "lake"]))