"""
test_export_country_aggregates.py

Tests for scripts/export_country_aggregates.py

TESTING STRATEGY:
-----------------
Export script loads Natural Earth country boundaries, spatially joins
occurrence points, aggregates by country + year, exports GeoJSON.

Unit tests mock all file I/O — no real data files needed.
Integration tests (marked) hit real filesystem.

FUNCTION COVERAGE:
------------------
- load_countries(path)                          — loads Natural Earth shapefile
- join_occurrences_to_countries(occ, countries) — spatial join points to polygons
- aggregate_by_country_year(joined)             — count records per country per year
- export_country_counts(species, data_dir, output_dir) — orchestrates all three
"""

from unittest.mock import patch

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon

# ---------------------------------------------------------------------------
# load_countries()
# ---------------------------------------------------------------------------


def test_load_countries_reads_shapefile(tmp_path):
    """load_countries() reads the shapefile at the given path."""
    mock_gdf = gpd.GeoDataFrame(
        {"NAME": ["Kenya"], "ISO_A3": ["KEN"], "CONTINENT": ["Africa"]},
        geometry=[Polygon([(33, -5), (42, -5), (42, 5), (33, 5)])],
        crs="EPSG:4326",
    )

    with patch("scripts.export_country_aggregates.gpd.read_file", return_value=mock_gdf) as mock_read:
        from scripts.export_country_aggregates import load_countries

        load_countries(tmp_path / "ne_110m_admin_0_countries.shp")
        mock_read.assert_called_once()


def test_load_countries_returns_required_columns(tmp_path):
    """load_countries() returns only NAME, ISO_A3, CONTINENT and geometry."""
    mock_gdf = gpd.GeoDataFrame(
        {
            "NAME": ["Kenya"],
            "ISO_A3": ["KEN"],
            "CONTINENT": ["Africa"],
            "POP_EST": [54000000],  # should be dropped
            "GDP_MD": [95000],  # should be dropped
        },
        geometry=[Polygon([(33, -5), (42, -5), (42, 5), (33, 5)])],
        crs="EPSG:4326",
    )

    with patch("scripts.export_country_aggregates.gpd.read_file", return_value=mock_gdf):
        from scripts.export_country_aggregates import load_countries

        result = load_countries(tmp_path / "ne_110m_admin_0_countries.shp")

    assert "NAME" in result.columns
    assert "ISO_A3" in result.columns
    assert "CONTINENT" in result.columns
    assert "POP_EST" not in result.columns
    assert "GDP_MD" not in result.columns


def test_join_occurrences_to_countries_returns_country_name(tmp_path):
    """join_occurrences_to_countries() adds NAME and ISO_A3 columns to occurrences."""
    countries = gpd.GeoDataFrame(
        {"NAME": ["Kenya"], "ISO_A3": ["KEN"], "CONTINENT": ["Africa"]},
        geometry=[Polygon([(33, -5), (42, -5), (42, 5), (33, 5)])],
        crs="EPSG:4326",
    )

    occurrences = gpd.GeoDataFrame(
        {"species": ["Loxodonta africana"], "year": [2020]},
        geometry=[Point(37, 0)],  # inside Kenya polygon
        crs="EPSG:4326",
    )

    from scripts.export_country_aggregates import join_occurrences_to_countries

    result = join_occurrences_to_countries(occurrences, countries)

    assert "NAME" in result.columns
    assert "ISO_A3" in result.columns
    assert result.iloc[0]["NAME"] == "Kenya"
    assert result.iloc[0]["ISO_A3"] == "KEN"


def test_join_occurrences_to_countries_handles_points_outside_countries():
    """Points outside all country polygons get null NAME and ISO_A3."""
    countries = gpd.GeoDataFrame(
        {"NAME": ["Kenya"], "ISO_A3": ["KEN"], "CONTINENT": ["Africa"]},
        geometry=[Polygon([(33, -5), (42, -5), (42, 5), (33, 5)])],
        crs="EPSG:4326",
    )

    occurrences = gpd.GeoDataFrame(
        {"species": ["Loxodonta africana"], "year": [2020]},
        geometry=[Point(0, 0)],  # in ocean, outside Kenya
        crs="EPSG:4326",
    )

    from scripts.export_country_aggregates import join_occurrences_to_countries

    result = join_occurrences_to_countries(occurrences, countries)

    assert len(result) == 1
    assert pd.isna(result.iloc[0]["NAME"])


def test_aggregate_by_country_year_counts_records():
    """aggregate_by_country_year() returns counts per country per year."""
    joined = gpd.GeoDataFrame(
        {
            "NAME": ["Kenya", "Kenya", "Tanzania", "Kenya"],
            "ISO_A3": ["KEN", "KEN", "TZA", "KEN"],
            "year": [2020, 2020, 2020, 2021],
            "species": ["Loxodonta africana"] * 4,
        },
        geometry=[Point(37, 0)] * 4,
        crs="EPSG:4326",
    )

    from scripts.export_country_aggregates import aggregate_by_country_year

    result = aggregate_by_country_year(joined)

    assert "NAME" in result.columns
    assert "ISO_A3" in result.columns
    assert "year" in result.columns
    assert "count" in result.columns

    kenya_2020 = result[(result["NAME"] == "Kenya") & (result["year"] == 2020)]
    assert kenya_2020.iloc[0]["count"] == 2

    tanzania_2020 = result[(result["NAME"] == "Tanzania") & (result["year"] == 2020)]
    assert tanzania_2020.iloc[0]["count"] == 1


def test_aggregate_by_country_year_excludes_non_africa():
    """aggregate_by_country_year() excludes records outside Africa."""
    joined = gpd.GeoDataFrame(
        {
            "NAME": ["Kenya", "France"],
            "ISO_A3": ["KEN", "FRA"],
            "CONTINENT": ["Africa", "Europe"],
            "year": [2020, 2020],
            "species": ["Loxodonta africana"] * 2,
        },
        geometry=[Point(37, 0), Point(2, 47)],
        crs="EPSG:4326",
    )

    from scripts.export_country_aggregates import aggregate_by_country_year

    result = aggregate_by_country_year(joined)

    assert "France" not in result["NAME"].values
    assert "Kenya" in result["NAME"].values


def test_export_country_counts_writes_geojson(tmp_path):
    """export_country_counts() writes a GeoJSON file for the given species."""
    data_dir = tmp_path / "data" / "processed"
    output_dir = tmp_path / "apps" / "mapbox" / "data"
    countries_path = tmp_path / "countries" / "ne_110m_admin_0_countries.shp"

    mock_countries = gpd.GeoDataFrame(
        {"NAME": ["Kenya"], "ISO_A3": ["KEN"], "CONTINENT": ["Africa"]},
        geometry=[Polygon([(33, -5), (42, -5), (42, 5), (33, 5)])],
        crs="EPSG:4326",
    )

    mock_occurrences = gpd.GeoDataFrame(
        {"species": ["Loxodonta africana"], "year": [2020]},
        geometry=[Point(37, 0)],
        crs="EPSG:4326",
    )

    with patch("scripts.export_country_aggregates.load_countries", return_value=mock_countries), patch("scripts.export_country_aggregates.gpd.read_file", return_value=mock_occurrences):
        from scripts.export_country_aggregates import export_country_counts

        export_country_counts("Loxodonta africana", data_dir, output_dir, countries_path)

    output_file = output_dir / "country_counts_gbif_loxodonta_africana.geojson"
    assert output_file.exists()


def test_export_country_counts_output_has_required_fields(tmp_path):
    """export_country_counts() output JSON has NAME, ISO_A3, year, count fields."""
    import json

    data_dir = tmp_path / "data" / "processed"
    output_dir = tmp_path / "apps" / "mapbox" / "data"
    countries_path = tmp_path / "countries" / "ne_110m_admin_0_countries.shp"

    mock_countries = gpd.GeoDataFrame(
        {"NAME": ["Kenya"], "ISO_A3": ["KEN"], "CONTINENT": ["Africa"]},
        geometry=[Polygon([(33, -5), (42, -5), (42, 5), (33, 5)])],
        crs="EPSG:4326",
    )

    mock_occurrences = gpd.GeoDataFrame(
        {"species": ["Loxodonta africana"], "year": [2020]},
        geometry=[Point(37, 0)],
        crs="EPSG:4326",
    )

    with patch("scripts.export_country_aggregates.load_countries", return_value=mock_countries), patch("scripts.export_country_aggregates.gpd.read_file", return_value=mock_occurrences):
        from scripts.export_country_aggregates import export_country_counts

        export_country_counts("Loxodonta africana", data_dir, output_dir, countries_path)

    output_file = output_dir / "country_counts_gbif_loxodonta_africana.geojson"
    data = json.loads(output_file.read_text())

    assert len(data) == 1
    assert data[0]["NAME"] == "Kenya"
    assert data[0]["ISO_A3"] == "KEN"
    assert data[0]["year"] == 2020
    assert data[0]["count"] == 1


def test_export_all_country_counts_calls_export_for_each_species(tmp_path):
    """export_all_country_counts() calls export_country_counts for each species."""
    data_dir = tmp_path / "data" / "processed"
    output_dir = tmp_path / "apps" / "mapbox" / "data"
    countries_path = tmp_path / "countries" / "ne_110m_admin_0_countries.shp"

    with patch("scripts.export_country_aggregates.export_country_counts") as mock_export:
        from scripts.export_country_aggregates import export_all_country_counts

        export_all_country_counts(data_dir, output_dir, countries_path)

        from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG

        assert mock_export.call_count == len(SPECIES_CONFIG)

def test_export_country_aggregates_main_calls_export_all(tmp_path):
    """main() calls export_all_country_counts with the correct default paths."""
    from pathlib import Path
    with patch("scripts.export_country_aggregates.export_all_country_counts") as mock_export:
        from scripts.export_country_aggregates import main
        main()
        mock_export.assert_called_once_with(
            data_dir=Path("data/processed"),
            output_dir=Path("apps/mapbox/data"),
            countries_path=Path("data/raw/countries/ne_110m_admin_0_countries.shp"),
        )