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

    # sjoin_nearest uses a spatial index (STRtree), so this is
    # ~O(points · log roads) rather than the O(points · roads) of a
    # per-point brute-force scan — essential for continental road networks.
    joined = gpd.sjoin_nearest(
        occurrences_projected,
        roads_projected[["road_class", "geometry"]],
        how="left",
        distance_col="distance_to_road_m",
    )

    # Equidistant roads produce duplicate rows for one occurrence — keep the
    # first match per original occurrence so the row count is preserved.
    joined = joined[~joined.index.duplicated(keep="first")]
    joined = joined.drop(columns="index_right", errors="ignore")

    return joined.to_crs(epsg=4326)


def add_distance_to_settlement(
    occurrences: gpd.GeoDataFrame,
    settlements: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """
    Add distance-to-nearest-settlement values and the nearest settlement's class.

    Mirrors add_distance_to_road for the settlement human-pressure layer.

    Args:
        occurrences: GeoDataFrame of species occurrence points (any species).
        settlements: Normalized settlements GeoDataFrame as produced by
                     OSMSettlements.load() — must carry a 'settlement_class' column.

    Returns:
        GeoDataFrame with two added columns:
            distance_to_settlement_m : meters to the nearest settlement
            settlement_class         : the class of that nearest settlement

    Note:
        Distance is computed in EPSG:3857 (Web Mercator) for metric accuracy,
        then re-projected back to EPSG:4326 — mirrors add_distance_to_road().
    """
    occurrences_projected = occurrences.to_crs(epsg=3857)
    settlements_projected = settlements.to_crs(epsg=3857)

    joined = gpd.sjoin_nearest(
        occurrences_projected,
        settlements_projected[["settlement_class", "geometry"]],
        how="left",
        distance_col="distance_to_settlement_m",
    )

    # Equidistant settlements produce duplicate rows for one occurrence — keep
    # the first match per original occurrence so the row count is preserved.
    joined = joined[~joined.index.duplicated(keep="first")]
    joined = joined.drop(columns="index_right", errors="ignore")

    return joined.to_crs(epsg=4326)
