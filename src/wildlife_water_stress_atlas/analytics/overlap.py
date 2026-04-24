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
    result["distance_to_water"] = result.geometry.apply(
        lambda point: water_projected.distance(point).min()
    )

    return result.to_crs(epsg=4326)