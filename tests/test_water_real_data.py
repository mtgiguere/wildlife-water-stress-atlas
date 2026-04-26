from wildlife_water_stress_atlas.ingest.water import load_rivers
import pytest

@pytest.mark.integration
def test_load_rivers_from_natural_earth_file():
    gdf = load_rivers("data/raw/water/rivers/ne_10m_rivers_lake_centerlines_scale_rank.shp")

    assert len(gdf) > 0
    assert gdf.crs is not None
    assert gdf.crs.to_string() == "EPSG:4326"
