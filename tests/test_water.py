import geopandas as gpd
from shapely.geometry import LineString, Polygon

from wildlife_water_stress_atlas.ingest.water import combine_water_layers, load_lakes, load_rivers


def test_load_lakes_from_natural_earth_file():
    gdf = load_lakes("data/raw/water/lakes/ne_10m_lakes.shp")

    assert len(gdf) > 0
    assert gdf.crs is not None
    assert gdf.crs.to_string() == "EPSG:4326"

def test_load_lakes_sets_crs_when_missing(monkeypatch):
    mock_gdf = gpd.GeoDataFrame(
        {"name": ["Test Lake"]},
        geometry=[LineString([(0, 0), (1, 1)])],
        crs=None,
    )

    monkeypatch.setattr(gpd, "read_file", lambda _: mock_gdf)

    result = load_lakes("dummy/path.shp")

    assert result.crs is not None
    assert result.crs.to_string() == "EPSG:4326"

def test_load_rivers_returns_gdf():
    gdf = load_rivers("data/raw/water/rivers/ne_10m_rivers_lake_centerlines_scale_rank.shp")

    assert len(gdf) > 0
    assert gdf.crs.to_string() == "EPSG:4326"

def test_load_rivers_sets_crs_when_missing(monkeypatch):
    mock_gdf = gpd.GeoDataFrame(
        {"name": ["Test River"]},
        geometry=[LineString([(0, 0), (1, 1)])],
        crs=None,
    )

    monkeypatch.setattr(gpd, "read_file", lambda _: mock_gdf)

    result = load_rivers("dummy/path.shp")

    assert result.crs is not None
    assert result.crs.to_string() == "EPSG:4326"

def test_load_lakes_and_rivers_converts_existing_crs_to_wgs84(monkeypatch):
    ## First test Lakes
    mock_gdf = gpd.GeoDataFrame(
        {"name": ["Test Lake"]},
        geometry=[Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])],
        crs="EPSG:3857",
    )

    monkeypatch.setattr(gpd, "read_file", lambda _: mock_gdf)

    result = load_lakes("dummy/path.shp")

    assert result.crs is not None
    assert result.crs.to_string() == "EPSG:4326"
    ## Then Test Rivers
    mock_gdf = gpd.GeoDataFrame(
        {"name": ["Test River"]},
        geometry=[LineString([(0, 0), (1, 1)])],
        crs="EPSG:3857",
    )
    
    monkeypatch.setattr(gpd, "read_file", lambda _: mock_gdf)

    result = load_rivers("dummy/path.shp")

    assert result.crs is not None
    assert result.crs.to_string() == "EPSG:4326"

def test_combine_water_layers_merges_rivers_and_lakes():
    rivers = gpd.GeoDataFrame(
        geometry=[LineString([(0, 0), (1, 1)])],
        crs="EPSG:4326",
    )

    lakes = gpd.GeoDataFrame(
        geometry=[Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])],
        crs="EPSG:4326",
    )

    combined = combine_water_layers(rivers, lakes)

    assert len(combined) == 2
    assert combined.crs.to_string() == "EPSG:4326"

def test_combine_water_layers_preserves_water_type_column():
    from wildlife_water_stress_atlas.ingest.water import combine_water_layers

    rivers = gpd.GeoDataFrame(
        {"type": ["river"]},
        geometry=[LineString([(0, 0), (1, 1)])],
        crs="EPSG:4326",
    )

    lakes = gpd.GeoDataFrame(
        {"type": ["lake"]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        crs="EPSG:4326",
    )

    result = combine_water_layers(rivers, lakes)

    assert "type" in result.columns
    assert set(result["type"]) == {"river", "lake"}

def test_get_water_type_weights_returns_species_specific_weights():
    from wildlife_water_stress_atlas.analytics.water_access import (
        get_water_type_weights,
    )

    result = get_water_type_weights("Loxodonta africana")

    assert result["river"] == 1.0
    assert result["lake"] == 1.0