"""
test_export_road_threats.py

Tests for scripts/export_road_threats.py

TESTING STRATEGY:
-----------------
compute_road_threats() accepts GeoDataFrames directly — tested with real fixtures,
no mocking needed (it is pure spatial computation over small test data).

export_road_threat() and export_all_road_threats() do file I/O — gpd.read_file
and load_all_threats are mocked so tests run without real data on disk.

FUNCTION COVERAGE:
------------------
- compute_road_threats(occurrences, roads, scientific_name)
- export_road_threat(occurrences_path, roads_path, output_path, scientific_name)
- export_all_road_threats(data_dir, roads_path, output_dir)
- main()
"""

import json
from pathlib import Path
from unittest.mock import patch

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point

from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_occurrences():
    return gpd.GeoDataFrame(
        {"species": ["Hyperolius marmoratus"], "year": [2020]},
        geometry=[Point(1, 0)],
        crs="EPSG:4326",
    )


@pytest.fixture
def mock_roads():
    """Normalized roads GDF as OSMRoads.load() produces."""
    return gpd.GeoDataFrame(
        {
            "road_class": ["primary"],
            "source_id": ["road_0"],
            "region": ["africa"],
        },
        geometry=[LineString([(0, -1), (0, 1)])],
        crs="EPSG:4326",
    )


@pytest.fixture
def mock_result_gdf():
    """Pre-computed result GDF — used when mocking compute_road_threats."""
    return gpd.GeoDataFrame(
        {
            "species": ["Hyperolius marmoratus"],
            "year": [2020],
            "distance_to_road_m": [500.0],
            "road_class": ["primary"],
            "road_threat_score": [0.4],
        },
        geometry=[Point(1, 0)],
        crs="EPSG:4326",
    )


# ---------------------------------------------------------------------------
# compute_road_threats — pure computation, no mocking
# ---------------------------------------------------------------------------


def test_compute_road_threats_returns_geodataframe(mock_occurrences, mock_roads):
    from scripts.export_road_threats import compute_road_threats

    result = compute_road_threats(mock_occurrences, mock_roads, "Hyperolius marmoratus")

    assert isinstance(result, gpd.GeoDataFrame)


def test_compute_road_threats_adds_road_threat_score(mock_occurrences, mock_roads):
    from scripts.export_road_threats import compute_road_threats

    result = compute_road_threats(mock_occurrences, mock_roads, "Hyperolius marmoratus")

    assert "road_threat_score" in result.columns


def test_compute_road_threats_score_is_in_valid_range(mock_occurrences, mock_roads):
    from scripts.export_road_threats import compute_road_threats

    result = compute_road_threats(mock_occurrences, mock_roads, "Hyperolius marmoratus")

    assert result["road_threat_score"].between(0.0, 1.0).all()


def test_compute_road_threats_adds_distance_and_class_columns(mock_occurrences, mock_roads):
    from scripts.export_road_threats import compute_road_threats

    result = compute_road_threats(mock_occurrences, mock_roads, "Hyperolius marmoratus")

    assert "distance_to_road_m" in result.columns
    assert "road_class" in result.columns


def test_compute_road_threats_flamingo_score_is_zero(mock_roads):
    """Flamingos fly — road_sensitivity=0.0, so all scores must be 0.0."""
    from scripts.export_road_threats import compute_road_threats

    occurrences = gpd.GeoDataFrame(
        {"species": ["Phoenicopterus roseus"], "year": [2020]},
        geometry=[Point(1, 0)],
        crs="EPSG:4326",
    )

    result = compute_road_threats(occurrences, mock_roads, "Phoenicopterus roseus")

    assert (result["road_threat_score"] == 0.0).all()


def test_compute_road_threats_frog_score_exceeds_elephant_score(mock_roads):
    """Reed frogs are more road-sensitive than elephants — scores must reflect that."""
    from scripts.export_road_threats import compute_road_threats

    occ = gpd.GeoDataFrame(
        {"species": ["placeholder"], "year": [2020]},
        geometry=[Point(0.001, 0)],
        crs="EPSG:4326",
    )

    frog_result = compute_road_threats(occ.assign(species="Hyperolius marmoratus"), mock_roads, "Hyperolius marmoratus")
    elephant_result = compute_road_threats(occ.assign(species="Loxodonta africana"), mock_roads, "Loxodonta africana")

    assert frog_result.iloc[0]["road_threat_score"] > elephant_result.iloc[0]["road_threat_score"]


def test_compute_road_threats_works_for_all_species(mock_roads):
    """Every species in SPECIES_CONFIG must produce a valid result — no KeyErrors."""
    from scripts.export_road_threats import compute_road_threats

    for scientific_name in SPECIES_CONFIG:
        occurrences = gpd.GeoDataFrame(
            {"species": [scientific_name], "year": [2020]},
            geometry=[Point(1, 0)],
            crs="EPSG:4326",
        )
        result = compute_road_threats(occurrences, mock_roads, scientific_name)
        assert result["road_threat_score"].between(0.0, 1.0).all()


# ---------------------------------------------------------------------------
# export_road_threat — file I/O mocked
# ---------------------------------------------------------------------------


def test_export_road_threat_writes_output_file(tmp_path, mock_occurrences, mock_roads, mock_result_gdf):
    from scripts.export_road_threats import export_road_threat

    output_path = tmp_path / "road_threats_gbif_hyperolius_marmoratus.geojson"

    with (
        patch("scripts.export_road_threats.gpd.read_file", return_value=mock_occurrences),
        patch("scripts.export_road_threats.load_all_threats", return_value=mock_roads),
        patch("scripts.export_road_threats.compute_road_threats", return_value=mock_result_gdf),
    ):
        export_road_threat(
            occurrences_path=tmp_path / "gbif.gpkg",
            roads_path=tmp_path / "roads.gpkg",
            output_path=output_path,
            scientific_name="Hyperolius marmoratus",
        )

    assert output_path.exists()


def test_export_road_threat_output_is_valid_geojson(tmp_path, mock_result_gdf):
    from scripts.export_road_threats import export_road_threat

    output_path = tmp_path / "road_threats.geojson"

    with (
        patch("scripts.export_road_threats.gpd.read_file", return_value=mock_result_gdf),
        patch("scripts.export_road_threats.load_all_threats", return_value=mock_result_gdf),
        patch("scripts.export_road_threats.compute_road_threats", return_value=mock_result_gdf),
    ):
        export_road_threat(
            occurrences_path=tmp_path / "gbif.gpkg",
            roads_path=tmp_path / "roads.gpkg",
            output_path=output_path,
            scientific_name="Hyperolius marmoratus",
        )

    with open(output_path) as f:
        data = json.load(f)

    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 1


def test_export_road_threat_output_has_required_properties(tmp_path, mock_result_gdf):
    from scripts.export_road_threats import export_road_threat

    output_path = tmp_path / "road_threats.geojson"

    with (
        patch("scripts.export_road_threats.gpd.read_file", return_value=mock_result_gdf),
        patch("scripts.export_road_threats.load_all_threats", return_value=mock_result_gdf),
        patch("scripts.export_road_threats.compute_road_threats", return_value=mock_result_gdf),
    ):
        export_road_threat(
            occurrences_path=tmp_path / "gbif.gpkg",
            roads_path=tmp_path / "roads.gpkg",
            output_path=output_path,
            scientific_name="Hyperolius marmoratus",
        )

    with open(output_path) as f:
        data = json.load(f)

    props = data["features"][0]["properties"]
    assert "road_threat_score" in props
    assert "road_class" in props
    assert "distance_to_road_m" in props
    assert "species" in props
    assert "year" in props


def test_export_road_threat_creates_output_directory(tmp_path, mock_result_gdf):
    from scripts.export_road_threats import export_road_threat

    output_path = tmp_path / "deep" / "nested" / "road_threats.geojson"

    with (
        patch("scripts.export_road_threats.gpd.read_file", return_value=mock_result_gdf),
        patch("scripts.export_road_threats.load_all_threats", return_value=mock_result_gdf),
        patch("scripts.export_road_threats.compute_road_threats", return_value=mock_result_gdf),
    ):
        export_road_threat(
            occurrences_path=tmp_path / "gbif.gpkg",
            roads_path=tmp_path / "roads.gpkg",
            output_path=output_path,
            scientific_name="Hyperolius marmoratus",
        )

    assert output_path.exists()


# ---------------------------------------------------------------------------
# export_all_road_threats
# ---------------------------------------------------------------------------


def test_export_all_road_threats_exports_one_file_per_species(tmp_path):
    from scripts.export_road_threats import export_all_road_threats

    with patch("scripts.export_road_threats.export_road_threat") as mock_export, patch("scripts.export_road_threats.load_all_threats"):
        export_all_road_threats(
            data_dir=tmp_path / "data",
            roads_path=tmp_path / "roads.gpkg",
            output_dir=tmp_path / "output",
        )

    assert mock_export.call_count == len(SPECIES_CONFIG)


def test_export_all_road_threats_passes_correct_output_paths(tmp_path):
    from scripts.export_road_threats import export_all_road_threats

    output_dir = tmp_path / "output"

    with patch("scripts.export_road_threats.export_road_threat") as mock_export, patch("scripts.export_road_threats.load_all_threats"):
        export_all_road_threats(
            data_dir=tmp_path / "data",
            roads_path=tmp_path / "roads.gpkg",
            output_dir=output_dir,
        )

    output_paths = [call.kwargs["output_path"] for call in mock_export.call_args_list]
    output_names = [p.name for p in output_paths]

    for scientific_name in SPECIES_CONFIG:
        slug = scientific_name.lower().replace(" ", "_")
        expected = f"road_threats_gbif_{slug}.geojson"
        assert expected in output_names, f"Missing output file for {scientific_name}"


def test_export_all_road_threats_continues_on_species_error(tmp_path):
    """One species failing must not abort the entire run."""
    from scripts.export_road_threats import export_all_road_threats

    call_count = {"n": 0}
    error_species = list(SPECIES_CONFIG.keys())[0]

    def flaky_export(**kwargs):
        call_count["n"] += 1
        if kwargs["scientific_name"] == error_species:
            raise RuntimeError("simulated export failure")

    with patch("scripts.export_road_threats.export_road_threat", side_effect=flaky_export), patch("scripts.export_road_threats.load_all_threats"):
        export_all_road_threats(
            data_dir=tmp_path / "data",
            roads_path=tmp_path / "roads.gpkg",
            output_dir=tmp_path / "output",
        )

    assert call_count["n"] == len(SPECIES_CONFIG)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def test_main_calls_export_all_road_threats():
    from scripts.export_road_threats import main

    with patch("scripts.export_road_threats.export_all_road_threats") as mock_export:
        main()
        mock_export.assert_called_once()
        call_kwargs = mock_export.call_args.kwargs
        assert call_kwargs["roads_path"] == Path("data/raw/threats/africa_roads.gpkg")
        assert call_kwargs["output_dir"] == Path("apps/mapbox/data")
