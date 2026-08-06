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


def test_add_distance_to_water_picks_the_nearest_of_several():
    # With several water features, the distance must be to the NEAREST one — the
    # whole point of the indexed nearest-join (and unchanged from brute-force).
    occurrences = gpd.GeoDataFrame(
        {"species": ["X"]},
        geometry=[Point(0, 0)],
        crs="EPSG:4326",
    )
    water = gpd.GeoDataFrame(
        {"type": ["far_lake", "near_river"]},
        geometry=[
            Polygon([(5, 5), (5, 6), (6, 6), (6, 5)]),  # far (~5 deg away)
            LineString([(0.1, -1), (0.1, 1)]),  # near (~0.1 deg = ~11 km east)
        ],
        crs="EPSG:4326",
    )

    result = add_distance_to_water(occurrences, water)
    d = result.loc[0, "distance_to_water"]
    assert 8_000 < d < 15_000, f"expected the ~11km river, got {d}m (picked the far lake?)"
    assert len(result) == 1  # nearest-join must not duplicate the occurrence


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


# ---------------------------------------------------------------------------
# within_layer_extent — is a measurement against this layer meaningful at all?
#
# WHY: distance-to-nearest-feature always returns a number, even when the layer
# does not cover the point. That number is not a measurement, it is an artifact
# of where the data happens to stop. The shipped flamingo layer scored records
# in Spain against Africa-only hydrography: 2,163km to the "nearest" river read
# as near-maximum water stress (mean stress_aggregate 0.660 outside Africa vs
# 0.045 inside). The settlements layer is a regional subset, so the same hole
# exists for West African occurrences of every species.
# ---------------------------------------------------------------------------


def test_point_inside_the_layer_extent_is_covered():
    from wildlife_water_stress_atlas.analytics.overlap import within_layer_extent

    points = gpd.GeoDataFrame(geometry=[Point(0.5, 0.5)], crs="EPSG:4326")
    layer = gpd.GeoDataFrame(geometry=[LineString([(0, 0), (1, 1)])], crs="EPSG:4326")

    assert list(within_layer_extent(points, layer)) == [True]


def test_point_outside_the_layer_extent_is_not_covered():
    from wildlife_water_stress_atlas.analytics.overlap import within_layer_extent

    points = gpd.GeoDataFrame(geometry=[Point(50.0, 40.0)], crs="EPSG:4326")
    layer = gpd.GeoDataFrame(geometry=[LineString([(0, 0), (1, 1)])], crs="EPSG:4326")

    assert list(within_layer_extent(points, layer)) == [False]


def test_point_exactly_on_the_extent_boundary_is_covered():
    """Boundary case stated explicitly: the edge is inside. An off-by-one here
    would strip coverage from occurrences at the very edge of a regional
    subset — precisely the records the caller most needs to reason about."""
    from wildlife_water_stress_atlas.analytics.overlap import within_layer_extent

    points = gpd.GeoDataFrame(geometry=[Point(1.0, 1.0)], crs="EPSG:4326")
    layer = gpd.GeoDataFrame(geometry=[LineString([(0, 0), (1, 1)])], crs="EPSG:4326")

    assert list(within_layer_extent(points, layer)) == [True]


def test_mixed_points_are_classified_independently():
    from wildlife_water_stress_atlas.analytics.overlap import within_layer_extent

    points = gpd.GeoDataFrame(
        geometry=[Point(0.5, 0.5), Point(50.0, 40.0), Point(0.1, 0.9)],
        crs="EPSG:4326",
    )
    layer = gpd.GeoDataFrame(geometry=[LineString([(0, 0), (1, 1)])], crs="EPSG:4326")

    assert list(within_layer_extent(points, layer)) == [True, False, True]


def test_an_empty_layer_covers_nothing():
    """A layer that failed to load must not silently certify every point as
    covered — that would turn a missing file into universal zero stress."""
    from wildlife_water_stress_atlas.analytics.overlap import within_layer_extent

    points = gpd.GeoDataFrame(geometry=[Point(0.5, 0.5), Point(2, 2)], crs="EPSG:4326")
    layer = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    assert list(within_layer_extent(points, layer)) == [False, False]


def test_no_points_yields_no_verdicts():
    from wildlife_water_stress_atlas.analytics.overlap import within_layer_extent

    points = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    layer = gpd.GeoDataFrame(geometry=[LineString([(0, 0), (1, 1)])], crs="EPSG:4326")

    assert len(within_layer_extent(points, layer)) == 0


def test_verdicts_are_aligned_to_the_input_index():
    """The caller uses this to select rows, so a reset index would silently
    misattribute coverage to the wrong occurrences."""
    from wildlife_water_stress_atlas.analytics.overlap import within_layer_extent

    points = gpd.GeoDataFrame(geometry=[Point(0.5, 0.5), Point(50.0, 40.0)], crs="EPSG:4326", index=[7, 9])
    layer = gpd.GeoDataFrame(geometry=[LineString([(0, 0), (1, 1)])], crs="EPSG:4326")

    result = within_layer_extent(points, layer)

    assert list(result.index) == [7, 9]
    assert result.loc[7]
    assert not result.loc[9]
