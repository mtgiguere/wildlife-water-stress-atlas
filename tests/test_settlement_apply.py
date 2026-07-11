"""
test_settlement_apply.py

Tests for apply_settlement_threat_score in
src/wildlife_water_stress_atlas/analytics/apply.py

Mirrors apply_road_threat_score: maps a (distance_m, settlement_class, species)
scoring function across a GeoDataFrame into a settlement_threat_score column.
"""

import geopandas as gpd
import pytest
from shapely.geometry import Point

from wildlife_water_stress_atlas.analytics.apply import apply_settlement_threat_score


@pytest.fixture
def sample_gdf():
    return gpd.GeoDataFrame(
        {
            "species": ["Panthera leo", "Panthera leo"],
            "distance_to_settlement_m": [100.0, 5_000.0],
            "settlement_class": ["city", "village"],
        },
        geometry=[Point(0, 0), Point(1, 1)],
        crs="EPSG:4326",
    )


def test_apply_settlement_threat_score_adds_column(sample_gdf):
    result = apply_settlement_threat_score(sample_gdf, lambda d, c, s: 0.5)
    assert "settlement_threat_score" in result.columns


def test_apply_settlement_threat_score_uses_scoring_function(sample_gdf):
    def fake_score(distance, settlement_class, species):
        return distance * 0.001  # deterministic, depends on input

    result = apply_settlement_threat_score(sample_gdf, fake_score)
    expected = sample_gdf["distance_to_settlement_m"] * 0.001
    assert all(result["settlement_threat_score"] == expected)


def test_apply_settlement_threat_score_passes_class_and_species(sample_gdf):
    """The scoring function must receive settlement_class and species per row."""
    seen = []

    def spy(distance, settlement_class, species):
        seen.append((settlement_class, species))
        return 0.0

    apply_settlement_threat_score(sample_gdf, spy)
    assert seen == [("city", "Panthera leo"), ("village", "Panthera leo")]


def test_apply_settlement_threat_score_returns_copy(sample_gdf):
    result = apply_settlement_threat_score(sample_gdf, lambda d, c, s: 0.5)
    assert "settlement_threat_score" not in sample_gdf.columns
    assert result is not sample_gdf


def test_apply_settlement_threat_score_raises_for_missing_settlement_class(sample_gdf):
    bad = sample_gdf.drop(columns=["settlement_class"])
    with pytest.raises(KeyError):
        apply_settlement_threat_score(bad, lambda d, c, s: 0.5)


def test_apply_settlement_threat_score_raises_for_missing_distance(sample_gdf):
    bad = sample_gdf.drop(columns=["distance_to_settlement_m"])
    with pytest.raises(KeyError):
        apply_settlement_threat_score(bad, lambda d, c, s: 0.5)


def test_apply_settlement_threat_score_with_real_scoring(sample_gdf):
    from wildlife_water_stress_atlas.analytics.threat_scoring import settlement_threat_score

    result = apply_settlement_threat_score(sample_gdf, settlement_threat_score)
    assert result["settlement_threat_score"].between(0, 1).all()
