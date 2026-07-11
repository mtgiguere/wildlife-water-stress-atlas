"""
test_export_settlement_threats.py

Tests for scripts/export_settlement_threats.py

Mirrors test_export_road_threats.py. compute_settlement_threats() is pure
spatial computation (tested with real small fixtures); the file-I/O functions
mock gpd.read_file and load_all_threats.
"""

import json
from pathlib import Path
from unittest.mock import patch

import geopandas as gpd
import pytest
from shapely.geometry import Point

from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG


@pytest.fixture
def mock_occurrences():
    return gpd.GeoDataFrame(
        {"species": ["Hyperolius marmoratus"], "year": [2020]},
        geometry=[Point(1, 0)],
        crs="EPSG:4326",
    )


@pytest.fixture
def mock_settlements():
    """Normalized settlements GDF as OSMSettlements.load() produces."""
    return gpd.GeoDataFrame(
        {
            "settlement_class": ["city", "village"],
            "source_id": ["settlement_0", "settlement_1"],
            "region": ["africa", "africa"],
        },
        geometry=[Point(0, 0), Point(0.5, 0)],
        crs="EPSG:4326",
    )


@pytest.fixture
def mock_result_gdf():
    return gpd.GeoDataFrame(
        {
            "species": ["Hyperolius marmoratus"],
            "year": [2020],
            "distance_to_settlement_m": [500.0],
            "settlement_class": ["city"],
            "settlement_threat_score": [0.4],
        },
        geometry=[Point(1, 0)],
        crs="EPSG:4326",
    )


# ---------------------------------------------------------------------------
# compute_settlement_threats — pure computation
# ---------------------------------------------------------------------------


def test_compute_settlement_threats_adds_score(mock_occurrences, mock_settlements):
    from scripts.export_settlement_threats import compute_settlement_threats

    result = compute_settlement_threats(mock_occurrences, mock_settlements, "Hyperolius marmoratus")
    assert "settlement_threat_score" in result.columns


def test_compute_settlement_threats_score_in_range(mock_occurrences, mock_settlements):
    from scripts.export_settlement_threats import compute_settlement_threats

    result = compute_settlement_threats(mock_occurrences, mock_settlements, "Hyperolius marmoratus")
    assert result["settlement_threat_score"].between(0.0, 1.0).all()


def test_compute_settlement_threats_adds_distance_and_class(mock_occurrences, mock_settlements):
    from scripts.export_settlement_threats import compute_settlement_threats

    result = compute_settlement_threats(mock_occurrences, mock_settlements, "Hyperolius marmoratus")
    assert "distance_to_settlement_m" in result.columns
    assert "settlement_class" in result.columns


def test_compute_settlement_threats_flamingo_score_is_zero(mock_settlements):
    """Flamingos are immune to ground human pressure — settlement_sensitivity=0.0."""
    from scripts.export_settlement_threats import compute_settlement_threats

    occ = gpd.GeoDataFrame(
        {"species": ["Phoenicopterus roseus"], "year": [2020]},
        geometry=[Point(0.001, 0)],
        crs="EPSG:4326",
    )
    result = compute_settlement_threats(occ, mock_settlements, "Phoenicopterus roseus")
    assert (result["settlement_threat_score"] == 0.0).all()


def test_compute_settlement_threats_works_for_all_species(mock_settlements):
    from scripts.export_settlement_threats import compute_settlement_threats

    for scientific_name in SPECIES_CONFIG:
        occ = gpd.GeoDataFrame(
            {"species": [scientific_name], "year": [2020]},
            geometry=[Point(0.001, 0)],
            crs="EPSG:4326",
        )
        result = compute_settlement_threats(occ, mock_settlements, scientific_name)
        assert result["settlement_threat_score"].between(0.0, 1.0).all()


# ---------------------------------------------------------------------------
# build_settlement_points — display layer (larger classes only)
# ---------------------------------------------------------------------------


@pytest.fixture
def mixed_class_settlements():
    return gpd.GeoDataFrame(
        {"settlement_class": ["city", "town", "village", "hamlet"]},
        geometry=[Point(i, 0) for i in range(4)],
        crs="EPSG:4326",
    )


def test_build_settlement_points_keeps_only_display_classes(mixed_class_settlements):
    """Only city/town are shown on the map — village/hamlet would clutter it."""
    from scripts.export_settlement_threats import build_settlement_points

    result = build_settlement_points(mixed_class_settlements)
    assert set(result["settlement_class"]) == {"city", "town"}


def test_build_settlement_points_keeps_class_column(mixed_class_settlements):
    from scripts.export_settlement_threats import build_settlement_points

    assert "settlement_class" in build_settlement_points(mixed_class_settlements).columns


def test_export_settlement_points_writes_geojson(tmp_path, mixed_class_settlements):
    from scripts.export_settlement_threats import export_settlement_points

    out = tmp_path / "settlements_points.geojson"
    with patch("scripts.export_settlement_threats.load_all_threats", return_value=mixed_class_settlements):
        export_settlement_points(settlements_path=tmp_path / "s.gpkg", output_path=out)

    assert out.exists()
    data = json.load(open(out))
    assert data["type"] == "FeatureCollection"
    assert {f["properties"]["settlement_class"] for f in data["features"]} == {"city", "town"}


def test_export_settlement_points_uses_preloaded_settlements(tmp_path, mixed_class_settlements):
    from scripts.export_settlement_threats import export_settlement_points

    out = tmp_path / "sp.geojson"
    with patch("scripts.export_settlement_threats.load_all_threats") as mock_load:
        export_settlement_points(settlements_path=tmp_path / "s.gpkg", output_path=out, settlements=mixed_class_settlements)
        mock_load.assert_not_called()
    assert out.exists()


# ---------------------------------------------------------------------------
# export_settlement_threat — file I/O mocked
# ---------------------------------------------------------------------------


def test_export_settlement_threat_output_has_required_properties(tmp_path, mock_result_gdf):
    from scripts.export_settlement_threats import export_settlement_threat

    output_path = tmp_path / "settlement_threats.geojson"
    with (
        patch("scripts.export_settlement_threats.gpd.read_file", return_value=mock_result_gdf),
        patch("scripts.export_settlement_threats.load_all_threats", return_value=mock_result_gdf),
        patch("scripts.export_settlement_threats.compute_settlement_threats", return_value=mock_result_gdf),
    ):
        export_settlement_threat(
            occurrences_path=tmp_path / "gbif.gpkg",
            settlements_path=tmp_path / "s.gpkg",
            output_path=output_path,
            scientific_name="Hyperolius marmoratus",
        )

    data = json.load(open(output_path))
    assert data["type"] == "FeatureCollection"
    props = data["features"][0]["properties"]
    assert "settlement_threat_score" in props
    assert "settlement_class" in props
    assert "distance_to_settlement_m" in props
    assert "species" in props
    assert "year" in props


def test_export_settlement_threat_creates_output_directory(tmp_path, mock_result_gdf):
    from scripts.export_settlement_threats import export_settlement_threat

    output_path = tmp_path / "deep" / "nested" / "settlement_threats.geojson"
    with (
        patch("scripts.export_settlement_threats.gpd.read_file", return_value=mock_result_gdf),
        patch("scripts.export_settlement_threats.load_all_threats", return_value=mock_result_gdf),
        patch("scripts.export_settlement_threats.compute_settlement_threats", return_value=mock_result_gdf),
    ):
        export_settlement_threat(
            occurrences_path=tmp_path / "gbif.gpkg",
            settlements_path=tmp_path / "s.gpkg",
            output_path=output_path,
            scientific_name="Hyperolius marmoratus",
        )

    assert output_path.exists()


# ---------------------------------------------------------------------------
# export_all_settlement_threats
# ---------------------------------------------------------------------------


def test_export_all_settlement_threats_one_file_per_species(tmp_path):
    from scripts.export_settlement_threats import export_all_settlement_threats

    with patch("scripts.export_settlement_threats.export_settlement_threat") as mock_export, patch("scripts.export_settlement_threats.load_all_threats"):
        export_all_settlement_threats(
            data_dir=tmp_path / "data",
            settlements_path=tmp_path / "s.gpkg",
            output_dir=tmp_path / "output",
        )

    assert mock_export.call_count == len(SPECIES_CONFIG)


def test_export_all_settlement_threats_correct_output_names(tmp_path):
    from scripts.export_settlement_threats import export_all_settlement_threats

    with patch("scripts.export_settlement_threats.export_settlement_threat") as mock_export, patch("scripts.export_settlement_threats.load_all_threats"):
        export_all_settlement_threats(
            data_dir=tmp_path / "data",
            settlements_path=tmp_path / "s.gpkg",
            output_dir=tmp_path / "output",
        )

    names = [call.kwargs["output_path"].name for call in mock_export.call_args_list]
    for scientific_name in SPECIES_CONFIG:
        slug = scientific_name.lower().replace(" ", "_")
        assert f"settlement_threats_gbif_{slug}.geojson" in names


def test_export_all_settlement_threats_continues_on_error(tmp_path):
    from scripts.export_settlement_threats import export_all_settlement_threats

    call_count = {"n": 0}
    error_species = list(SPECIES_CONFIG.keys())[0]

    def flaky(**kwargs):
        call_count["n"] += 1
        if kwargs["scientific_name"] == error_species:
            raise RuntimeError("boom")

    with patch("scripts.export_settlement_threats.export_settlement_threat", side_effect=flaky), patch("scripts.export_settlement_threats.load_all_threats"):
        export_all_settlement_threats(
            data_dir=tmp_path / "data",
            settlements_path=tmp_path / "s.gpkg",
            output_dir=tmp_path / "output",
        )

    assert call_count["n"] == len(SPECIES_CONFIG)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def test_main_calls_export_all_and_points():
    from scripts.export_settlement_threats import main

    with (
        patch("scripts.export_settlement_threats.export_all_settlement_threats") as mock_all,
        patch("scripts.export_settlement_threats.export_settlement_points") as mock_points,
    ):
        main()
        mock_all.assert_called_once()
        assert mock_all.call_args.kwargs["settlements_path"] == Path("data/raw/threats/africa_settlements.gpkg")
        assert mock_all.call_args.kwargs["output_dir"] == Path("apps/mapbox/data")
        mock_points.assert_called_once()
        assert mock_points.call_args.kwargs["output_path"] == Path("apps/mapbox/data/settlements_points.geojson")
