import geopandas as gpd

from wildlife_water_stress_atlas.ingest.gbif import fetch_occurrences, occurrences_to_gdf


def test_occurrences_to_gdf_returns_geodataframe():
    records = [
        {"decimalLatitude": -1.95, "decimalLongitude": 37.15, "species": "Loxodonta africana"},
        {"decimalLatitude": -19.0, "decimalLongitude": 23.5, "species": "Loxodonta africana"},
    ]

    gdf = occurrences_to_gdf(records)

    assert isinstance(gdf, gpd.GeoDataFrame)
    assert len(gdf) == 2
    assert "geometry" in gdf.columns


def test_occurrences_to_gdf_sets_wgs84_crs():
    records = [
        {"decimalLatitude": -1.95, "decimalLongitude": 37.15},
    ]

    gdf = occurrences_to_gdf(records)

    assert gdf.crs is not None
    assert gdf.crs.to_string() == "EPSG:4326"


def test_fetch_elephant_occurrences_returns_data():
    records = fetch_occurrences("Loxodonta africana", limit=10)

    assert isinstance(records, list)
    assert len(records) > 0


def test_fetch_elephant_occurrences_has_coordinates():
    records = fetch_occurrences("Loxodonta africana", limit=10)

    first = records[0]

    assert "decimalLatitude" in first
    assert "decimalLongitude" in first
