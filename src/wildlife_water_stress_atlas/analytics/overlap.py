"""
overlap.py

Spatial analytics for species and water relationships.
"""

import geopandas as gpd


def add_distance_to_water(
    elephants: gpd.GeoDataFrame,
    rivers: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """
    Add distance-to-water values for each elephant occurrence.

    Args:
        elephants: GeoDataFrame of elephant occurrence points.
        rivers: GeoDataFrame of river geometries.

    Returns:
        GeoDataFrame with a distance_to_water column.
    """
    elephants_projected = elephants.to_crs(epsg=3857)
    rivers_projected = rivers.to_crs(epsg=3857)

    result = elephants_projected.copy()
    result["distance_to_water"] = result.geometry.apply(
        lambda point: rivers_projected.distance(point).min()
    )

    return result.to_crs(epsg=4326)