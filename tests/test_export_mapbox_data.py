"""
test_export_mapbox_data.py

Tests for scripts/export_mapbox_data.py

TESTING STRATEGY:
-----------------
Export script reads .gpkg files and writes GeoJSON + JSON.
Unit tests mock all file I/O — no real data files needed.
Integration tests (marked) hit real filesystem.

FUNCTION COVERAGE:
------------------
- export_water(input_path, output_path)        — water.geojson
- export_occurrences(input_path, output_path)  — occurrences_{species}.geojson
- export_species_config(output_path)           — species_config.json
- export_all(data_dir, output_dir)             — orchestrates all three
"""

import json
from unittest.mock import patch

import geopandas as gpd
from shapely.geometry import LineString, Point

# ---------------------------------------------------------------------------
# export_water()
# ---------------------------------------------------------------------------


def test_export_water_reads_input_gpkg(tmp_path):
    """export_water() reads the input GeoPackage."""
    input_path = tmp_path / "water_africa_simplified.gpkg"
    output_path = tmp_path / "water.geojson"

    mock_gdf = gpd.GeoDataFrame(
        {"water_type": ["river"], "permanence": ["permanent"]},
        geometry=[LineString([(20, -10), (25, -10)])],
        crs="EPSG:4326",
    )

    with patch("scripts.export_mapbox_data.gpd.read_file", return_value=mock_gdf) as mock_read:
        from scripts.export_mapbox_data import export_water

        export_water(input_path, output_path)
        mock_read.assert_called_once_with(input_path)


def test_export_water_writes_output_geojson(tmp_path):
    """export_water() writes the GeoDataFrame to the output path as GeoJSON."""
    input_path = tmp_path / "water_africa_simplified.gpkg"
    output_path = tmp_path / "water.geojson"

    mock_gdf = gpd.GeoDataFrame(
        {"water_type": ["river"], "permanence": ["permanent"]},
        geometry=[LineString([(20, -10), (25, -10)])],
        crs="EPSG:4326",
    )

    with patch("scripts.export_mapbox_data.gpd.read_file", return_value=mock_gdf):
        from scripts.export_mapbox_data import export_water

        export_water(input_path, output_path)

    assert output_path.exists()


def test_export_water_output_is_valid_geojson(tmp_path):
    """export_water() output is valid GeoJSON with a FeatureCollection."""
    input_path = tmp_path / "water_africa_simplified.gpkg"
    output_path = tmp_path / "water.geojson"

    mock_gdf = gpd.GeoDataFrame(
        {"water_type": ["river"], "permanence": ["permanent"]},
        geometry=[LineString([(20, -10), (25, -10)])],
        crs="EPSG:4326",
    )

    with patch("scripts.export_mapbox_data.gpd.read_file", return_value=mock_gdf):
        from scripts.export_mapbox_data import export_water

        export_water(input_path, output_path)

    with open(output_path) as f:
        data = json.load(f)

    assert data["type"] == "FeatureCollection"
    assert "features" in data


def test_export_water_creates_output_directory(tmp_path):
    """export_water() creates the output directory if it doesn't exist."""
    input_path = tmp_path / "water_africa_simplified.gpkg"
    output_path = tmp_path / "apps" / "mapbox" / "data" / "water.geojson"

    mock_gdf = gpd.GeoDataFrame(
        {"water_type": ["river"], "permanence": ["permanent"]},
        geometry=[LineString([(20, -10), (25, -10)])],
        crs="EPSG:4326",
    )

    with patch("scripts.export_mapbox_data.gpd.read_file", return_value=mock_gdf):
        from scripts.export_mapbox_data import export_water

        export_water(input_path, output_path)

    assert output_path.exists()


def test_export_occurrences_reads_input_gpkg(tmp_path):
    """export_occurrences() reads the input GeoPackage."""
    input_path = tmp_path / "gbif_loxodonta_africana.gpkg"
    output_path = tmp_path / "occurrences_loxodonta_africana.geojson"

    mock_gdf = gpd.GeoDataFrame(
        {"species": ["Loxodonta africana"], "year": [2020]},
        geometry=[Point(20, -10)],
        crs="EPSG:4326",
    )

    with patch("scripts.export_mapbox_data.gpd.read_file", return_value=mock_gdf) as mock_read:
        from scripts.export_mapbox_data import export_occurrences

        export_occurrences(input_path, output_path)
        mock_read.assert_called_once_with(input_path)


def test_export_occurrences_writes_output_geojson(tmp_path):
    """export_occurrences() writes the GeoDataFrame to the output path as GeoJSON."""
    input_path = tmp_path / "gbif_loxodonta_africana.gpkg"
    output_path = tmp_path / "occurrences_loxodonta_africana.geojson"

    mock_gdf = gpd.GeoDataFrame(
        {"species": ["Loxodonta africana"], "year": [2020]},
        geometry=[Point(20, -10)],
        crs="EPSG:4326",
    )

    with patch("scripts.export_mapbox_data.gpd.read_file", return_value=mock_gdf):
        from scripts.export_mapbox_data import export_occurrences

        export_occurrences(input_path, output_path)

    assert output_path.exists()


def test_export_occurrences_only_keeps_required_columns(tmp_path):
    """export_occurrences() only exports year, species, and geometry columns."""
    input_path = tmp_path / "gbif_loxodonta_africana.gpkg"
    output_path = tmp_path / "occurrences_loxodonta_africana.geojson"

    mock_gdf = gpd.GeoDataFrame(
        {
            "species": ["Loxodonta africana"],
            "year": [2020],
            "extra_column": ["should_be_dropped"],
            "another_extra": [42],
        },
        geometry=[Point(20, -10)],
        crs="EPSG:4326",
    )

    with patch("scripts.export_mapbox_data.gpd.read_file", return_value=mock_gdf):
        from scripts.export_mapbox_data import export_occurrences

        export_occurrences(input_path, output_path)

    with open(output_path) as f:
        data = json.load(f)

    feature_props = data["features"][0]["properties"]
    assert "year" in feature_props
    assert "species" in feature_props
    assert "extra_column" not in feature_props
    assert "another_extra" not in feature_props


def test_export_species_config_writes_json_file(tmp_path):
    """export_species_config() writes a JSON file to the output path."""
    output_path = tmp_path / "species_config.json"

    from scripts.export_mapbox_data import export_species_config

    export_species_config(output_path)

    assert output_path.exists()


def test_export_species_config_contains_all_species(tmp_path):
    """export_species_config() contains an entry for every species in SPECIES_CONFIG."""
    output_path = tmp_path / "species_config.json"

    from scripts.export_mapbox_data import export_species_config

    export_species_config(output_path)

    with open(output_path) as f:
        data = json.load(f)

    from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG

    for scientific_name in SPECIES_CONFIG:
        assert scientific_name in data


def test_export_species_config_has_required_fields(tmp_path):
    """Each species entry has the fields the frontend needs."""
    output_path = tmp_path / "species_config.json"

    from scripts.export_mapbox_data import export_species_config

    export_species_config(output_path)

    with open(output_path) as f:
        data = json.load(f)

    required_fields = ["common_name", "emoji", "water_threshold_m", "water_dependency", "icon_static_path"]

    for scientific_name, cfg in data.items():
        for field in required_fields:
            assert field in cfg, f"{scientific_name} missing field: {field}"


def test_export_all_calls_all_three_exporters(tmp_path):
    """export_all() calls export_water, export_occurrences for each species, and export_species_config."""
    data_dir = tmp_path / "data" / "processed"
    output_dir = tmp_path / "apps" / "mapbox" / "data"

    with (
        patch("scripts.export_mapbox_data.export_water") as mock_water,
        patch("scripts.export_mapbox_data.export_occurrences") as mock_occurrences,
        patch("scripts.export_mapbox_data.export_species_config") as mock_config,
    ):
        from scripts.export_mapbox_data import export_all

        export_all(data_dir, output_dir)

        mock_water.assert_called_once()
        mock_config.assert_called_once()

        from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG

        assert mock_occurrences.call_count == len(SPECIES_CONFIG)


def test_export_all_passes_correct_output_paths(tmp_path):
    """export_all() passes correctly named output paths for each species."""
    data_dir = tmp_path / "data" / "processed"
    output_dir = tmp_path / "apps" / "mapbox" / "data"

    with patch("scripts.export_mapbox_data.export_water"), patch("scripts.export_mapbox_data.export_occurrences") as mock_occurrences, patch("scripts.export_mapbox_data.export_species_config"):
        from scripts.export_mapbox_data import export_all

        export_all(data_dir, output_dir)

        from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG

        output_paths = [call.args[1] for call in mock_occurrences.call_args_list]
        output_names = [p.name for p in output_paths]

        for scientific_name, cfg in SPECIES_CONFIG.items():
            expected = cfg["gbif_cache_file"].replace(".gpkg", ".geojson")
            assert f"occurrences_{expected}" in output_names, f"Missing output file for {scientific_name}"

def test_export_mapbox_data_main_calls_export_all():
    """main() calls export_all with the correct default paths."""
    from pathlib import Path
    with patch("scripts.export_mapbox_data.export_all") as mock_export:
        from scripts.export_mapbox_data import main
        main()
        mock_export.assert_called_once_with(
            data_dir=Path("data/processed"),
            output_dir=Path("apps/mapbox/data"),
        )