import geopandas as gpd
from shapely.geometry import LineString

from wildlife_water_stress_atlas.ingest.water import load_rivers


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

def test_load_rivers_returns_gdf():
    gdf = load_rivers("data/raw/water/ne_10m_rivers_lake_centerlines_scale_rank.shp")

    assert len(gdf) > 0
    assert gdf.crs.to_string() == "EPSG:4326"