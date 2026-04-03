import geopandas as gpd
from shapely.geometry import Point


def test_aggregate_stress_to_grid_returns_grid_gdf():
    from wildlife_water_stress_atlas.analytics.spatial import (
        aggregate_stress_to_grid,
    )

    gdf = gpd.GeoDataFrame(
        {
            "water_stress_score": [0.2, 0.8],
            "stress_level": ["low", "high"],
        },
        geometry=[
            Point(30.0, -20.0),
            Point(30.1, -20.1),
        ],
        crs="EPSG:4326",
    )

    result = aggregate_stress_to_grid(gdf, cell_size_meters=50_000)

    assert isinstance(result, gpd.GeoDataFrame)
    assert "water_stress_score" in result.columns
    assert result.crs.to_string() == "EPSG:4326"
    assert not result.empty


def test_aggregate_stress_to_grid_averages_scores_within_same_cell():
    from wildlife_water_stress_atlas.analytics.spatial import (
        aggregate_stress_to_grid,
    )

    gdf = gpd.GeoDataFrame(
        {
            "water_stress_score": [0.2, 0.8],
            "stress_level": ["low", "high"],
        },
        geometry=[
            Point(30.0000, -20.0000),
            Point(30.0001, -20.0001),
        ],
        crs="EPSG:4326",
    )

    result = aggregate_stress_to_grid(gdf, cell_size_meters=50_000)

    assert len(result) == 1
    assert result.iloc[0]["water_stress_score"] == 0.5


def test_aggregate_stress_to_grid_includes_high_stress_percentage():
    from wildlife_water_stress_atlas.analytics.spatial import (
        aggregate_stress_to_grid,
    )

    gdf = gpd.GeoDataFrame(
        {
            "water_stress_score": [0.9, 0.85, 0.2, 0.3],
            "stress_level": ["high", "high", "low", "low"],
        },
        geometry=[
            Point(0, 0),
            Point(0.01, 0.01),
            Point(1, 1),
            Point(1.01, 1.01),
        ],
        crs="EPSG:4326",
    )

    result = aggregate_stress_to_grid(gdf, cell_size_meters=100_000)

    assert "high_stress_pct" in result.columns