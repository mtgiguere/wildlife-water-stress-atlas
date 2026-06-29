"""
overlap.py

Spatial analytics for species and water relationships.
"""

import geopandas as gpd


def add_distance_to_water(
    occurrences: gpd.GeoDataFrame,
    water: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """
    Add distance-to-nearest-water values for each occurrence point.

    Args:
        occurrences: GeoDataFrame of species occurrence points (any species).
        water: GeoDataFrame of water source geometries (any type — rivers,
               lakes, pans, wetlands, floodplains, etc.). The caller is
               responsible for passing all relevant water types combined,
               typically via combine_water_layers() from ingest/water.py.

    Returns:
        GeoDataFrame with a distance_to_water column (meters, EPSG:4326).

    Note:
        Distance is computed in EPSG:3857 (Web Mercator) for metric accuracy,
        then the result is re-projected back to EPSG:4326 for consistency
        with the rest of the pipeline.
    """
    occurrences_projected = occurrences.to_crs(epsg=3857)
    water_projected = water.to_crs(epsg=3857)

    result = occurrences_projected.copy()
    result["distance_to_water"] = result.geometry.apply(lambda point: water_projected.distance(point).min())

    return result.to_crs(epsg=4326)


def add_distance_to_road(
    occurrences: gpd.GeoDataFrame,
    roads: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """
    Add distance-to-nearest-road values and the nearest road's class.

    Args:
        occurrences: GeoDataFrame of species occurrence points (any species).
        roads: Normalized roads GeoDataFrame as produced by OSMRoads.load() —
               must carry a 'road_class' column.

    Returns:
        GeoDataFrame with two added columns:
            distance_to_road_m : meters to the nearest road
            road_class         : the class of that nearest road

    Note:
        Distance is computed in EPSG:3857 (Web Mercator) for metric accuracy,
        then the result is re-projected back to EPSG:4326 for consistency
        with the rest of the pipeline — mirrors add_distance_to_water().
    """
    occurrences_projected = occurrences.to_crs(epsg=3857)
    roads_projected = roads.to_crs(epsg=3857)

    def nearest(point):
        distances = roads_projected.distance(point)
        nearest_idx = distances.idxmin()
        return distances.loc[nearest_idx], roads_projected.loc[nearest_idx, "road_class"]

    result = occurrences_projected.copy()
    nearest_pairs = [nearest(point) for point in result.geometry]
    result["distance_to_road_m"] = [pair[0] for pair in nearest_pairs]
    result["road_class"] = [pair[1] for pair in nearest_pairs]

    return result.to_crs(epsg=4326)
