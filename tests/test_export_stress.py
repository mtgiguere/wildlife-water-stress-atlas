"""
test_export_stress.py

Phase C2: compute_species_stress composes the overlap layer (distance from each
occurrence to each stressor's features) + the generic engine to produce, per
occurrence, a per-stressor score breakdown AND the cumulative aggregate.

This is the engine's first real consumer over geospatial data. The golden guard
cross-checks it against the LEGACY per-stressor pipelines over the same fixtures:
the generic road/settlement/water columns must match road_threat_score /
settlement_threat_score / water_stress_score exactly.
"""

import json
from pathlib import Path
from unittest.mock import patch

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point

from scripts.export_road_threats import compute_road_threats
from scripts.export_settlement_threats import compute_settlement_threats
from scripts.export_stress import compute_species_stress
from tests._scoring_oracle import water_stress_score
from wildlife_water_stress_atlas.analytics.overlap import add_distance_to_water
from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG

_FROG = "Hyperolius marmoratus"


@pytest.fixture
def occurrences():
    return gpd.GeoDataFrame(
        {"species": [_FROG, _FROG, _FROG], "year": [2019, 2020, 2021]},
        geometry=[Point(0.05, 0), Point(0.5, 0.2), Point(1.0, 1.0)],
        crs="EPSG:4326",
    )


@pytest.fixture
def water():
    return gpd.GeoDataFrame({"type": ["river"]}, geometry=[LineString([(0, -1), (0, 1)])], crs="EPSG:4326")


@pytest.fixture
def roads():
    return gpd.GeoDataFrame(
        {"road_class": ["motorway", "primary"], "source_id": ["r0", "r1"], "region": ["africa", "africa"]},
        geometry=[LineString([(0.1, -1), (0.1, 1)]), LineString([(0.6, -1), (0.6, 1)])],
        crs="EPSG:4326",
    )


@pytest.fixture
def settlements():
    return gpd.GeoDataFrame(
        {"settlement_class": ["city", "town"], "source_id": ["s0", "s1"], "region": ["africa", "africa"]},
        geometry=[Point(0.2, 0), Point(0.8, 0.5)],
        crs="EPSG:4326",
    )


def _stress(occ, water, roads, settlements):
    return compute_species_stress(occ, water=water, roads=roads, settlements=settlements, species=_FROG)


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------


def test_produces_per_stressor_and_aggregate_columns(occurrences, water, roads, settlements):
    result = _stress(occurrences, water, roads, settlements)
    for col in ("stress_water", "stress_roads", "stress_settlements", "stress_aggregate"):
        assert col in result.columns
    assert len(result) == len(occurrences)


def test_aggregate_in_unit_interval(occurrences, water, roads, settlements):
    result = _stress(occurrences, water, roads, settlements)
    assert result["stress_aggregate"].between(0.0, 1.0).all()


# ---------------------------------------------------------------------------
# GOLDEN — generic columns reproduce the legacy per-stressor pipelines
# ---------------------------------------------------------------------------


def test_roads_column_matches_legacy_road_threats(occurrences, water, roads, settlements):
    generic = _stress(occurrences, water, roads, settlements)
    legacy = compute_road_threats(occurrences, roads, _FROG)
    assert list(generic["stress_roads"].round(9)) == list(legacy["road_threat_score"].round(9))


def test_settlements_column_matches_legacy_settlement_threats(occurrences, water, roads, settlements):
    generic = _stress(occurrences, water, roads, settlements)
    legacy = compute_settlement_threats(occurrences, settlements, _FROG)
    assert list(generic["stress_settlements"].round(9)) == list(legacy["settlement_threat_score"].round(9))


def test_water_column_matches_legacy_water_stress(occurrences, water, roads, settlements):
    generic = _stress(occurrences, water, roads, settlements)
    legacy = add_distance_to_water(occurrences, water)
    expected = [water_stress_score(d, _FROG) for d in legacy["distance_to_water"]]
    assert list(generic["stress_water"].round(9)) == [round(e, 9) for e in expected]


def test_aggregate_is_noisy_or_of_the_three(occurrences, water, roads, settlements):
    result = _stress(occurrences, water, roads, settlements)
    for _, row in result.iterrows():
        expected = 1 - (1 - row["stress_water"]) * (1 - row["stress_roads"]) * (1 - row["stress_settlements"])
        assert row["stress_aggregate"] == pytest.approx(expected)


# ---------------------------------------------------------------------------
# export_species_stress — file writing
# ---------------------------------------------------------------------------


def test_export_species_stress_writes_geojson_with_aggregate(tmp_path, occurrences, water, roads, settlements):
    from scripts.export_stress import export_species_stress

    out = tmp_path / "stress.geojson"
    with patch("scripts.export_stress.gpd.read_file", return_value=occurrences):
        export_species_stress(tmp_path / "occ.gpkg", out, _FROG, water=water, roads=roads, settlements=settlements)

    assert out.exists()
    data = json.load(open(out))
    assert data["type"] == "FeatureCollection"
    props = data["features"][0]["properties"]
    for key in ("species", "stress_water", "stress_roads", "stress_settlements", "stress_aggregate"):
        assert key in props


def test_export_species_stress_creates_output_directory(tmp_path, occurrences, water, roads, settlements):
    from scripts.export_stress import export_species_stress

    out = tmp_path / "deep" / "nested" / "stress.geojson"
    with patch("scripts.export_stress.gpd.read_file", return_value=occurrences):
        export_species_stress(tmp_path / "occ.gpkg", out, _FROG, water=water, roads=roads, settlements=settlements)

    assert out.exists()


# ---------------------------------------------------------------------------
# export_all_stress — one file per species, loaders reused
# ---------------------------------------------------------------------------


def test_export_all_stress_one_file_per_species(tmp_path):
    from scripts.export_stress import export_all_stress

    with (
        patch("scripts.export_stress.export_species_stress") as mock_export,
        patch("scripts.export_stress.gpd.read_file"),
        patch("scripts.export_stress.load_all_threats"),
    ):
        export_all_stress(
            data_dir=tmp_path / "data",
            water_path=tmp_path / "w.gpkg",
            roads_path=tmp_path / "r.gpkg",
            settlements_path=tmp_path / "s.gpkg",
            output_dir=tmp_path / "out",
        )

    assert mock_export.call_count == len(SPECIES_CONFIG)


def test_export_all_stress_correct_output_names(tmp_path):
    from scripts.export_stress import export_all_stress

    with (
        patch("scripts.export_stress.export_species_stress") as mock_export,
        patch("scripts.export_stress.gpd.read_file"),
        patch("scripts.export_stress.load_all_threats"),
    ):
        export_all_stress(
            data_dir=tmp_path / "data",
            water_path=tmp_path / "w.gpkg",
            roads_path=tmp_path / "r.gpkg",
            settlements_path=tmp_path / "s.gpkg",
            output_dir=tmp_path / "out",
        )

    names = [call.args[1].name for call in mock_export.call_args_list]
    for scientific_name in SPECIES_CONFIG:
        slug = scientific_name.lower().replace(" ", "_")
        assert f"stress_gbif_{slug}.geojson" in names


def test_export_all_stress_continues_on_species_error(tmp_path):
    from scripts.export_stress import export_all_stress

    calls = {"n": 0}
    error_species = next(iter(SPECIES_CONFIG))

    def flaky(occ_path, out_path, species, **kw):
        calls["n"] += 1
        if species == error_species:
            raise RuntimeError("boom")

    with (
        patch("scripts.export_stress.export_species_stress", side_effect=flaky),
        patch("scripts.export_stress.gpd.read_file"),
        patch("scripts.export_stress.load_all_threats"),
    ):
        export_all_stress(
            data_dir=tmp_path / "data",
            water_path=tmp_path / "w.gpkg",
            roads_path=tmp_path / "r.gpkg",
            settlements_path=tmp_path / "s.gpkg",
            output_dir=tmp_path / "out",
        )

    assert calls["n"] == len(SPECIES_CONFIG)


def test_main_calls_export_all_stress():
    from scripts.export_stress import main

    with patch("scripts.export_stress.export_all_stress") as mock_all:
        main()
        mock_all.assert_called_once()
        assert mock_all.call_args.kwargs["output_dir"] == Path("apps/mapbox/data")


# ---------------------------------------------------------------------------
# Fast aggregate builder — combine the already-computed per-stressor exports
# into the cumulative stress layer (noisy-OR), without recomputing distances.
# ---------------------------------------------------------------------------


def test_build_stress_from_scores_matches_engine_noisy_or():
    from scripts.export_stress import build_stress_from_scores
    from wildlife_water_stress_atlas.analytics.stressors import Score, aggregate_stress

    pts = [Point(0, 0), Point(1, 1), Point(2, 2)]
    triples = [(0.0, 0.2, 0.1), (0.5, 0.0, 0.4), (1.0, 0.3, 0.0)]
    water = gpd.GeoDataFrame({"species": ["X"] * 3, "year": [2019, 2020, 2021], "stress_score": [t[0] for t in triples]}, geometry=pts, crs="EPSG:4326")
    roads = gpd.GeoDataFrame({"species": ["X"] * 3, "year": [2019, 2020, 2021], "road_threat_score": [t[1] for t in triples]}, geometry=pts, crs="EPSG:4326")
    setts = gpd.GeoDataFrame({"species": ["X"] * 3, "year": [2019, 2020, 2021], "settlement_threat_score": [t[2] for t in triples]}, geometry=pts, crs="EPSG:4326")

    out = build_stress_from_scores(water, roads, setts)

    assert list(out.columns) == ["species", "year", "stress_water", "stress_roads", "stress_settlements", "stress_aggregate", "geometry"]
    for i, (w, r, s) in enumerate(triples):
        expected = aggregate_stress([Score(w, True), Score(r, True), Score(s, True)]).value
        assert out["stress_aggregate"].iloc[i] == pytest.approx(expected)
        assert out["stress_water"].iloc[i] == pytest.approx(w)
        assert out["stress_roads"].iloc[i] == pytest.approx(r)
        assert out["stress_settlements"].iloc[i] == pytest.approx(s)


def test_build_stress_from_scores_rejects_misaligned_inputs():
    from scripts.export_stress import build_stress_from_scores

    one = gpd.GeoDataFrame({"species": ["X"], "year": [2020], "stress_score": [0.1]}, geometry=[Point(0, 0)], crs="EPSG:4326")
    two = gpd.GeoDataFrame(
        {"species": ["X", "X"], "year": [2020, 2021], "road_threat_score": [0.1, 0.2], "settlement_threat_score": [0.1, 0.2]},
        geometry=[Point(0, 0), Point(1, 1)],
        crs="EPSG:4326",
    )
    with pytest.raises(ValueError):
        build_stress_from_scores(one, two, two)


# ---------------------------------------------------------------------------
# rescore_water_with_added_source — fold an ADDITIONAL accessible water source
# (e.g. HydroRIVERS) into an existing per-occurrence water-stress table.
# ---------------------------------------------------------------------------


def test_rescore_water_with_added_source_takes_nearer_distance_and_rescores():
    from scripts.export_stress import rescore_water_with_added_source
    from tests._scoring_oracle import water_stress_score
    from wildlife_water_stress_atlas.analytics.scoring import classify_stress_level

    sci = "Hippopotamus amphibius"
    pts = [Point(0, 0), Point(1, 1), Point(2, 2)]
    stress = gpd.GeoDataFrame(
        {"species": [sci] * 3, "year": [2019, 2020, 2021], "distance_m": [500.0, 20_000.0, 8_000.0], "stress_score": [0.0, 0.0, 0.0], "stress_level": ["x"] * 3},
        geometry=pts,
        crs="EPSG:4326",
    )
    added = [100_000.0, 3_000.0, 50_000.0]  # a nearer river only at index 1

    out = rescore_water_with_added_source(stress, added, sci)

    # nearer of the two distances, elementwise
    assert list(out["distance_m"]) == [500.0, 3_000.0, 8_000.0]
    # stress + level recomputed from the new distance, matching the engine/oracle
    for i, d in enumerate([500.0, 3_000.0, 8_000.0]):
        assert out["stress_score"].iloc[i] == pytest.approx(water_stress_score(d, sci))
        assert out["stress_level"].iloc[i] == classify_stress_level(water_stress_score(d, sci))
    # row-aligned + schema preserved
    assert len(out) == 3
    assert list(out.columns) == ["species", "year", "distance_m", "stress_score", "stress_level", "geometry"]


def test_rescore_water_with_added_source_rejects_length_mismatch():
    from scripts.export_stress import rescore_water_with_added_source

    stress = gpd.GeoDataFrame(
        {"species": ["X"], "year": [2020], "distance_m": [1.0], "stress_score": [0.0], "stress_level": ["low"]},
        geometry=[Point(0, 0)],
        crs="EPSG:4326",
    )
    with pytest.raises(ValueError):
        rescore_water_with_added_source(stress, [1.0, 2.0], "X")
