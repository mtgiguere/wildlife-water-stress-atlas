import geopandas as gpd
from shapely.geometry import LineString, Point, Polygon

from wildlife_water_stress_atlas.analytics.overlap import add_distance_to_water


def test_add_distance_to_water_adds_distance_column():
    # Renamed: elephants -> occurrences, rivers -> water
    # The function must work for any species and any water source type
    occurrences = gpd.GeoDataFrame(
        {"species": ["Loxodonta africana"]},
        geometry=[Point(1, 1)],
        crs="EPSG:4326",
    )

    water = gpd.GeoDataFrame(
        {"type": ["river"], "name": ["Test River"]},
        geometry=[LineString([(0, 0), (0, 2)])],
        crs="EPSG:4326",
    )

    result = add_distance_to_water(occurrences, water)

    assert "distance_to_water" in result.columns
    assert len(result) == 1
    assert result.loc[0, "distance_to_water"] >= 0


def test_add_distance_to_water_works_with_lake_geometry():
    # This test exists to prove the function is not river-specific.
    # Previously the parameter was named 'rivers' — this confirms a lake
    # polygon produces a valid distance just as a river linestring does.
    occurrences = gpd.GeoDataFrame(
        {"species": ["Loxodonta africana"]},
        geometry=[Point(5, 5)],
        crs="EPSG:4326",
    )

    water = gpd.GeoDataFrame(
        {"type": ["lake"], "name": ["Test Lake"]},
        geometry=[Polygon([(0, 0), (0, 2), (2, 2), (2, 0)])],
        crs="EPSG:4326",
    )

    result = add_distance_to_water(occurrences, water)

    assert "distance_to_water" in result.columns
    assert result.loc[0, "distance_to_water"] >= 0


def test_add_distance_to_water_works_with_combined_water_sources():
    # The real use case: a combined layer of rivers AND lakes passed together.
    # This is what the pipeline will do once pans and wetlands are added.
    occurrences = gpd.GeoDataFrame(
        {"species": ["Loxodonta africana"]},
        geometry=[Point(1, 1)],
        crs="EPSG:4326",
    )

    water = gpd.GeoDataFrame(
        {"type": ["river", "lake"]},
        geometry=[
            LineString([(0, 0), (0, 2)]),
            Polygon([(3, 3), (3, 4), (4, 4), (4, 3)]),
        ],
        crs="EPSG:4326",
    )

    result = add_distance_to_water(occurrences, water)

    assert "distance_to_water" in result.columns
    assert result.loc[0, "distance_to_water"] >= 0


def test_add_distance_to_water_empty_occurrences_returns_empty():
    """Empty occurrences GeoDataFrame produces an empty result — no crash."""
    occurrences = gpd.GeoDataFrame(
        {"species": []},
        geometry=[],
        crs="EPSG:4326",
    )

    water = gpd.GeoDataFrame(
        {"type": ["river"]},
        geometry=[LineString([(0, 0), (0, 2)])],
        crs="EPSG:4326",
    )

    result = add_distance_to_water(occurrences, water)

    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 0
    assert "distance_to_water" in result.columns


def test_add_distance_to_water_distance_is_in_meters():
    """Distances should be metric (meters in EPSG:3857), not degrees.

    One degree of longitude at the equator is ~111km. A point 1 degree
    away from a river should produce a distance in the tens-of-thousands
    range (meters), not a value close to 1.0 (which would indicate
    the computation stayed in degree-based coordinates).
    """
    occurrences = gpd.GeoDataFrame(
        {"species": ["Loxodonta africana"]},
        geometry=[Point(1, 0)],
        crs="EPSG:4326",
    )

    water = gpd.GeoDataFrame(
        {"type": ["river"]},
        geometry=[LineString([(0, -1), (0, 1)])],
        crs="EPSG:4326",
    )

    result = add_distance_to_water(occurrences, water)

    distance = result.loc[0, "distance_to_water"]
    assert distance > 10_000, f"Distance {distance}m looks like degrees, not meters"
    assert distance < 200_000, f"Distance {distance}m is implausibly large for a 1-degree separation"
