"""
spatial.py

Spatial aggregation utilities for stress modeling.
"""

import geopandas as gpd
from shapely.geometry import box


def aggregate_stress_to_grid(
    gdf: gpd.GeoDataFrame,
    cell_size_meters: int = 50_000,
) -> gpd.GeoDataFrame:
    """
    Aggregate point-level water stress scores into fixed-size grid cells.

    Args:
        gdf: GeoDataFrame in EPSG:4326 with a water_stress_score column.
        cell_size_meters: Grid cell size in meters.

    Returns:
        GeoDataFrame of grid cells in EPSG:4326 with mean water_stress_score.
    """
    projected = gdf.to_crs(epsg=3857).copy()

    projected["x_bin"] = (projected.geometry.x // cell_size_meters) * cell_size_meters
    projected["y_bin"] = (projected.geometry.y // cell_size_meters) * cell_size_meters

    grouped = (
        projected.groupby(["x_bin", "y_bin"])
        .agg(
            water_stress_score=("water_stress_score", "mean"),
            high_stress_count=("stress_level", lambda x: (x == "high").sum()),
            total=("stress_level", "count"),
        )
        .reset_index()
    )

    grouped["high_stress_pct"] = grouped["high_stress_count"] / grouped["total"]

    grouped["geometry"] = grouped.apply(
        lambda row: box(
            row["x_bin"],
            row["y_bin"],
            row["x_bin"] + cell_size_meters,
            row["y_bin"] + cell_size_meters,
        ),
        axis=1,
    )

    return gpd.GeoDataFrame(
        grouped,
        geometry="geometry",
        crs="EPSG:3857",
    ).to_crs(epsg=4326)
