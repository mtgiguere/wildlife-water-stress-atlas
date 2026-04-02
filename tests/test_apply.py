import geopandas as gpd
import pytest
from shapely.geometry import Point


@pytest.fixture
def sample_gdf():
    return gpd.GeoDataFrame(
        {
            "species": ["elephant", "elephant"],
            "distance_to_water": [1.0, 10.0],
        },
        geometry=[Point(0, 0), Point(1, 1)],
        crs="EPSG:4326",
    )

def test_apply_water_stress_score_adds_column(sample_gdf):
    from wildlife_water_stress_atlas.analytics.apply import apply_water_stress_score

    def fake_score(distance, species):
        return 0.5

    result = apply_water_stress_score(sample_gdf, fake_score)

    assert "water_stress_score" in result.columns

def test_apply_water_stress_score_uses_scoring_function(sample_gdf):
    from wildlife_water_stress_atlas.analytics.apply import apply_water_stress_score

    def fake_score(distance, species):
        return distance * 0.1  # deterministic + depends on input

    result = apply_water_stress_score(sample_gdf, fake_score)

    expected = sample_gdf["distance_to_water"] * 0.1

    assert all(result["water_stress_score"] == expected)

def test_apply_water_stress_score_returns_copy(sample_gdf):
    from wildlife_water_stress_atlas.analytics.apply import apply_water_stress_score

    def fake_score(distance, species):
        return 0.5

    result = apply_water_stress_score(sample_gdf, fake_score)

    assert "water_stress_score" not in sample_gdf.columns
    assert "water_stress_score" in result.columns
    assert result is not sample_gdf



def test_apply_water_stress_score_raises_for_missing_species(sample_gdf):
    from wildlife_water_stress_atlas.analytics.apply import apply_water_stress_score

    bad_gdf = sample_gdf.drop(columns=["species"])

    def fake_score(distance, species):
        return 0.5

    with pytest.raises(KeyError):
        apply_water_stress_score(bad_gdf, fake_score)

def test_apply_water_stress_score_raises_for_missing_distance_to_water(sample_gdf):
    from wildlife_water_stress_atlas.analytics.apply import apply_water_stress_score

    bad_gdf = sample_gdf.drop(columns=["distance_to_water"])

    def fake_score(distance, species):
        return 0.5

    with pytest.raises(KeyError):
        apply_water_stress_score(bad_gdf, fake_score)

def test_apply_water_stress_score_handles_nan_distance(sample_gdf):
    import numpy as np

    from wildlife_water_stress_atlas.analytics.apply import apply_water_stress_score

    gdf = sample_gdf.copy()
    gdf.loc[0, "distance_to_water"] = np.nan

    def fake_score(distance, species):
        if distance != distance:  # NaN check
            return 0.0
        return 0.5

    result = apply_water_stress_score(gdf, fake_score)

    assert result.loc[0, "water_stress_score"] == 0.0

def test_apply_water_stress_score_propagates_scoring_errors(sample_gdf):
    from wildlife_water_stress_atlas.analytics.apply import apply_water_stress_score

    def bad_score(distance, species):
        raise ValueError("bad input")

    with pytest.raises(ValueError):
        apply_water_stress_score(sample_gdf, bad_score)

def test_apply_water_stress_score_with_real_scoring():
    import geopandas as gpd
    from shapely.geometry import Point

    from wildlife_water_stress_atlas.analytics.apply import apply_water_stress_score
    from wildlife_water_stress_atlas.analytics.scoring import water_stress_score

    gdf = gpd.GeoDataFrame(
        {
            "species": ["Loxodonta africana", "Loxodonta africana"],
            "distance_to_water": [1.0, 10.0],
        },
        geometry=[Point(0, 0), Point(1, 1)],
        crs="EPSG:4326",
    )

    result = apply_water_stress_score(gdf, water_stress_score)

    assert "water_stress_score" in result.columns
    assert result["water_stress_score"].between(0, 1).all()