"""
test_occurrence_columns.py

Pins the per-occurrence identity/temporal columns that every export carries
through to the map layer.

WHY THIS FILE EXISTS:
---------------------
GBIF ships `month` on essentially every record (100% of elephant, 95%+ for most
species), and it survives all the way into data/processed/gbif_*.gpkg. It was
then dropped at export, because five separate scripts each kept their own
hardcoded output-column list.

That is the settlement-names bug exactly: the upstream source had the field, and
we pruned it ourselves at several independent sites. `name` was recovered by
making it part of one shared schema; `month` is recovered the same way.

Month is the temporal key the seasonal-water work needs — water availability is
strongly seasonal (the Okavango's inundated area swings several-fold between
peak flood and dry-down), so scoring a dry-season record against an
annual-maximum water layer understates exactly the stress the atlas exists to
measure.
"""

import geopandas as gpd
import pytest
from shapely.geometry import Point

from wildlife_water_stress_atlas.ingest.gbif import OCCURRENCE_COLS

_SPECIES = "Hyperolius marmoratus"


def _occurrences_with_month():
    return gpd.GeoDataFrame(
        {"species": [_SPECIES, _SPECIES], "year": [2019, 2020], "month": [1, 7]},
        geometry=[Point(0.05, 0), Point(0.5, 0.2)],
        crs="EPSG:4326",
    )


# ---------------------------------------------------------------------------
# The shared definition
# ---------------------------------------------------------------------------


def test_occurrence_columns_carry_species_year_and_month():
    assert list(OCCURRENCE_COLS) == ["species", "year", "month"]


# ---------------------------------------------------------------------------
# Every export's column list is built from that definition, not its own copy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "module_name",
    [
        "scripts.export_stress",
        "scripts.export_road_threats",
        "scripts.export_settlement_threats",
    ],
)
def test_export_output_columns_begin_with_the_shared_occurrence_columns(module_name):
    """Drift guard. Five scripts each hand-maintaining this list is how `month`
    (and before it `name`) went missing; pin them to the one definition."""
    import importlib

    module = importlib.import_module(module_name)

    assert list(module._OUTPUT_COLS[: len(OCCURRENCE_COLS)]) == list(OCCURRENCE_COLS)


# ---------------------------------------------------------------------------
# Month actually reaches the written file
# ---------------------------------------------------------------------------


def test_stress_export_writes_month_into_the_geojson(tmp_path):
    """The behaviour that matters: a consumer reading the map data can tell
    January from July."""
    import json
    from unittest.mock import patch

    from shapely.geometry import LineString

    from scripts.export_stress import export_species_stress

    water = gpd.GeoDataFrame({"type": ["r", "r2"]}, geometry=[LineString([(0, -1), (0, 1)]), LineString([(0, -2), (2, -2)])], crs="EPSG:4326")
    roads = gpd.GeoDataFrame(
        {"road_class": ["motorway", "primary"], "source_id": ["r0", "rf"], "region": ["africa", "africa"]},
        geometry=[LineString([(0.1, -1), (0.1, 1)]), LineString([(0, -3), (2, -3)])],
        crs="EPSG:4326",
    )
    settlements = gpd.GeoDataFrame(
        {"settlement_class": ["city", "town"], "source_id": ["s0", "sf"], "region": ["africa", "africa"]},
        geometry=[Point(0.2, 0), Point(2.0, 2.0)],
        crs="EPSG:4326",
    )

    out = tmp_path / "stress.geojson"
    with patch("scripts.export_stress.gpd.read_file", return_value=_occurrences_with_month()):
        export_species_stress(tmp_path / "occ.gpkg", out, _SPECIES, water=water, roads=roads, settlements=settlements)

    props = [f["properties"] for f in json.load(open(out))["features"]]

    assert [p["month"] for p in props] == [1, 7]


def test_exports_still_work_when_the_source_has_no_month(tmp_path):
    """Not every record carries a month (giraffe is only 67% populated), and
    older caches predate its capture entirely. A missing column must not crash
    the export."""
    import json
    from unittest.mock import patch

    from shapely.geometry import LineString

    from scripts.export_stress import export_species_stress

    monthless = gpd.GeoDataFrame(
        {"species": [_SPECIES], "year": [2019]},
        geometry=[Point(0.05, 0)],
        crs="EPSG:4326",
    )
    water = gpd.GeoDataFrame({"type": ["r", "r2"]}, geometry=[LineString([(0, -1), (0, 1)]), LineString([(0, -2), (2, -2)])], crs="EPSG:4326")
    roads = gpd.GeoDataFrame(
        {"road_class": ["motorway", "primary"], "source_id": ["r0", "rf"], "region": ["africa", "africa"]},
        geometry=[LineString([(0.1, -1), (0.1, 1)]), LineString([(0, -3), (2, -3)])],
        crs="EPSG:4326",
    )
    settlements = gpd.GeoDataFrame(
        {"settlement_class": ["city", "town"], "source_id": ["s0", "sf"], "region": ["africa", "africa"]},
        geometry=[Point(0.2, 0), Point(2.0, 2.0)],
        crs="EPSG:4326",
    )

    out = tmp_path / "stress.geojson"
    with patch("scripts.export_stress.gpd.read_file", return_value=monthless):
        export_species_stress(tmp_path / "occ.gpkg", out, _SPECIES, water=water, roads=roads, settlements=settlements)

    props = json.load(open(out))["features"][0]["properties"]

    assert "species" in props
    assert "month" not in props


def test_build_stress_from_scores_carries_month_through():
    """The FAST path that produced the shipped stress_gbif_* files rebuilds its
    output frame from scratch, so it drops anything not named explicitly."""
    from scripts.export_stress import build_stress_from_scores

    pts = [Point(0, 0), Point(1, 1)]

    def frame(col, values):
        return gpd.GeoDataFrame(
            {"species": ["X", "X"], "year": [2019, 2020], "month": [3, 11], col: values},
            geometry=pts,
            crs="EPSG:4326",
        )

    out = build_stress_from_scores(frame("stress_score", [0.1, 0.2]), frame("road_threat_score", [0.3, 0.4]), frame("settlement_threat_score", [0.5, 0.6]))

    assert list(out["month"]) == [3, 11]


def test_build_stress_from_scores_works_without_month():
    from scripts.export_stress import build_stress_from_scores

    pts = [Point(0, 0)]

    def frame(col, values):
        return gpd.GeoDataFrame({"species": ["X"], "year": [2019], col: values}, geometry=pts, crs="EPSG:4326")

    out = build_stress_from_scores(frame("stress_score", [0.1]), frame("road_threat_score", [0.3]), frame("settlement_threat_score", [0.5]))

    assert "month" not in out.columns
    assert out["stress_aggregate"].iloc[0] == pytest.approx(1 - 0.9 * 0.7 * 0.5)
