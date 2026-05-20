"""
test_export_stress_scores.py

Tests for scripts/export_stress_scores.py

TESTING STRATEGY:
-----------------
Stress score export reads from PostGIS and writes GeoJSON.
Unit tests mock the database engine — no real PostGIS connection needed.
Integration tests (marked) hit real PostGIS.

FUNCTION COVERAGE:
------------------
- compute_stress_scores(engine, scientific_name)   — KNN query → GeoDataFrame with stress cols
- export_stress_scores(engine, scientific_name, output_path) — writes enriched GeoJSON
- export_all_stress_scores(engine, output_dir)     — orchestrates all species
- main()                                           — entry point
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import geopandas as gpd
from shapely.geometry import Point

from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG

# ---------------------------------------------------------------------------
# compute_stress_scores()
# ---------------------------------------------------------------------------


def make_mock_stress_gdf(n=3):
    """Helper — returns a minimal GeoDataFrame as PostGIS query would produce."""
    return gpd.GeoDataFrame(
        {
            "species": ["Loxodonta africana"] * n,
            "year": [2020] * n,
            "distance_m": [5000.0, 150000.0, 300000.0],
        },
        geometry=[Point(20 + i, -10) for i in range(n)],
        crs="EPSG:4326",
    )


def test_compute_stress_scores_returns_geodataframe():
    """compute_stress_scores() returns a GeoDataFrame."""
    from scripts.export_stress_scores import compute_stress_scores

    mock_engine = MagicMock()
    mock_gdf = make_mock_stress_gdf()

    with patch("scripts.export_stress_scores.gpd.read_postgis", return_value=mock_gdf):
        result = compute_stress_scores(mock_engine, "Loxodonta africana")

    assert isinstance(result, gpd.GeoDataFrame)


def test_compute_stress_scores_adds_distance_column():
    """compute_stress_scores() result contains distance_m column."""
    from scripts.export_stress_scores import compute_stress_scores

    mock_engine = MagicMock()
    mock_gdf = make_mock_stress_gdf()

    with patch("scripts.export_stress_scores.gpd.read_postgis", return_value=mock_gdf):
        result = compute_stress_scores(mock_engine, "Loxodonta africana")

    assert "distance_m" in result.columns


def test_compute_stress_scores_adds_stress_score_column():
    """compute_stress_scores() result contains stress_score column (0-1 float)."""
    from scripts.export_stress_scores import compute_stress_scores

    mock_engine = MagicMock()
    mock_gdf = make_mock_stress_gdf()

    with patch("scripts.export_stress_scores.gpd.read_postgis", return_value=mock_gdf):
        result = compute_stress_scores(mock_engine, "Loxodonta africana")

    assert "stress_score" in result.columns
    assert result["stress_score"].between(0.0, 1.0).all()


def test_compute_stress_scores_adds_stress_level_column():
    """compute_stress_scores() result contains stress_level column (low/moderate/high)."""
    from scripts.export_stress_scores import compute_stress_scores

    mock_engine = MagicMock()
    mock_gdf = make_mock_stress_gdf()

    with patch("scripts.export_stress_scores.gpd.read_postgis", return_value=mock_gdf):
        result = compute_stress_scores(mock_engine, "Loxodonta africana")

    assert "stress_level" in result.columns
    assert set(result["stress_level"].unique()).issubset({"low", "moderate", "high"})


def test_compute_stress_scores_low_distance_gives_low_stress():
    """Occurrence close to water gets low stress score."""
    from scripts.export_stress_scores import compute_stress_scores

    mock_engine = MagicMock()
    mock_gdf = gpd.GeoDataFrame(
        {"species": ["Loxodonta africana"], "year": [2020], "distance_m": [1000.0]},
        geometry=[Point(20, -10)],
        crs="EPSG:4326",
    )

    with patch("scripts.export_stress_scores.gpd.read_postgis", return_value=mock_gdf):
        result = compute_stress_scores(mock_engine, "Loxodonta africana")

    assert result["stress_level"].iloc[0] == "low"


def test_compute_stress_scores_high_distance_gives_high_stress():
    """Occurrence far from water (at threshold) gets high stress score."""
    from scripts.export_stress_scores import compute_stress_scores

    mock_engine = MagicMock()
    threshold = SPECIES_CONFIG["Loxodonta africana"]["water_threshold_m"]
    mock_gdf = gpd.GeoDataFrame(
        {"species": ["Loxodonta africana"], "year": [2020], "distance_m": [float(threshold)]},
        geometry=[Point(20, -10)],
        crs="EPSG:4326",
    )

    with patch("scripts.export_stress_scores.gpd.read_postgis", return_value=mock_gdf):
        result = compute_stress_scores(mock_engine, "Loxodonta africana")

    assert result["stress_level"].iloc[0] == "high"


def test_compute_stress_scores_works_for_all_species():
    """compute_stress_scores() works for every species in SPECIES_CONFIG."""
    from scripts.export_stress_scores import compute_stress_scores

    mock_engine = MagicMock()

    for scientific_name in SPECIES_CONFIG:
        mock_gdf = gpd.GeoDataFrame(
            {"species": [scientific_name], "year": [2020], "distance_m": [1000.0]},
            geometry=[Point(20, -10)],
            crs="EPSG:4326",
        )
        with patch("scripts.export_stress_scores.gpd.read_postgis", return_value=mock_gdf):
            result = compute_stress_scores(mock_engine, scientific_name)
        assert "stress_score" in result.columns


# ---------------------------------------------------------------------------
# export_stress_scores()
# ---------------------------------------------------------------------------


def test_export_stress_scores_writes_geojson(tmp_path):
    """export_stress_scores() writes a GeoJSON file to the output path."""
    from scripts.export_stress_scores import export_stress_scores

    mock_engine = MagicMock()
    output_path = tmp_path / "stress_loxodonta_africana.geojson"

    mock_gdf = gpd.GeoDataFrame(
        {
            "species": ["Loxodonta africana"],
            "year": [2020],
            "distance_m": [5000.0],
            "stress_score": [0.016],
            "stress_level": ["low"],
        },
        geometry=[Point(20, -10)],
        crs="EPSG:4326",
    )

    with patch("scripts.export_stress_scores.compute_stress_scores", return_value=mock_gdf):
        export_stress_scores(mock_engine, "Loxodonta africana", output_path)

    assert output_path.exists()


def test_export_stress_scores_output_is_valid_geojson(tmp_path):
    """export_stress_scores() output is valid GeoJSON FeatureCollection."""
    from scripts.export_stress_scores import export_stress_scores

    mock_engine = MagicMock()
    output_path = tmp_path / "stress_loxodonta_africana.geojson"

    mock_gdf = gpd.GeoDataFrame(
        {
            "species": ["Loxodonta africana"],
            "year": [2020],
            "distance_m": [5000.0],
            "stress_score": [0.016],
            "stress_level": ["low"],
        },
        geometry=[Point(20, -10)],
        crs="EPSG:4326",
    )

    with patch("scripts.export_stress_scores.compute_stress_scores", return_value=mock_gdf):
        export_stress_scores(mock_engine, "Loxodonta africana", output_path)

    with open(output_path) as f:
        data = json.load(f)

    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 1


def test_export_stress_scores_output_contains_stress_fields(tmp_path):
    """Exported GeoJSON features contain stress_score and stress_level properties."""
    from scripts.export_stress_scores import export_stress_scores

    mock_engine = MagicMock()
    output_path = tmp_path / "stress_loxodonta_africana.geojson"

    mock_gdf = gpd.GeoDataFrame(
        {
            "species": ["Loxodonta africana"],
            "year": [2020],
            "distance_m": [5000.0],
            "stress_score": [0.016],
            "stress_level": ["low"],
        },
        geometry=[Point(20, -10)],
        crs="EPSG:4326",
    )

    with patch("scripts.export_stress_scores.compute_stress_scores", return_value=mock_gdf):
        export_stress_scores(mock_engine, "Loxodonta africana", output_path)

    with open(output_path) as f:
        data = json.load(f)

    props = data["features"][0]["properties"]
    assert "stress_score" in props
    assert "stress_level" in props
    assert "year" in props
    assert "species" in props


def test_export_stress_scores_creates_output_directory(tmp_path):
    """export_stress_scores() creates the output directory if it doesn't exist."""
    from scripts.export_stress_scores import export_stress_scores

    mock_engine = MagicMock()
    output_path = tmp_path / "deep" / "nested" / "dir" / "stress.geojson"

    mock_gdf = gpd.GeoDataFrame(
        {
            "species": ["Loxodonta africana"],
            "year": [2020],
            "distance_m": [5000.0],
            "stress_score": [0.016],
            "stress_level": ["low"],
        },
        geometry=[Point(20, -10)],
        crs="EPSG:4326",
    )

    with patch("scripts.export_stress_scores.compute_stress_scores", return_value=mock_gdf):
        export_stress_scores(mock_engine, "Loxodonta africana", output_path)

    assert output_path.exists()


# ---------------------------------------------------------------------------
# export_all_stress_scores()
# ---------------------------------------------------------------------------


def test_export_all_stress_scores_calls_export_for_each_species(tmp_path):
    """export_all_stress_scores() calls export_stress_scores for every species."""
    from scripts.export_stress_scores import export_all_stress_scores

    mock_engine = MagicMock()

    with patch("scripts.export_stress_scores.export_stress_scores") as mock_export:
        export_all_stress_scores(mock_engine, tmp_path)

    assert mock_export.call_count == len(SPECIES_CONFIG)


def test_export_all_stress_scores_passes_correct_output_paths(tmp_path):
    """export_all_stress_scores() passes correctly named output paths."""
    from scripts.export_stress_scores import export_all_stress_scores

    mock_engine = MagicMock()

    with patch("scripts.export_stress_scores.export_stress_scores") as mock_export:
        export_all_stress_scores(mock_engine, tmp_path)

    output_paths = [call.args[2] for call in mock_export.call_args_list]
    output_names = [p.name for p in output_paths]

    for scientific_name in SPECIES_CONFIG:
        slug = scientific_name.lower().replace(" ", "_")
        expected = f"stress_scores_gbif_{slug}.geojson"
        assert expected in output_names, f"Missing output file for {scientific_name}"


def test_export_all_stress_scores_handles_errors(tmp_path):
    """export_all_stress_scores() prints error message when a species export fails."""
    from scripts.export_stress_scores import export_all_stress_scores

    mock_engine = MagicMock()
    error = ValueError("PostGIS connection failed")

    with patch("scripts.export_stress_scores.export_stress_scores", side_effect=error):
        # Should not raise — errors are caught and printed
        export_all_stress_scores(mock_engine, tmp_path)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def test_main_calls_export_all_stress_scores():
    """main() calls export_all_stress_scores with the correct default output path."""
    with patch("scripts.export_stress_scores.export_all_stress_scores") as mock_export, patch("scripts.export_stress_scores.create_engine"):
        from scripts.export_stress_scores import main

        main()
        mock_export.assert_called_once()
        call_kwargs = mock_export.call_args
        assert call_kwargs.kwargs.get("output_dir") == Path("apps/mapbox/data") or call_kwargs.args[1] == Path("apps/mapbox/data")
