"""
test_settlement_ingest.py

Tests for the OSMSettlements source class in
src/wildlife_water_stress_atlas/ingest/threats.py

Mirrors test_threats_ingest.py (OSMRoads). All tests mock gpd.read_file —
no real OSM data files needed.

NORMALIZED SCHEMA:
------------------
    geometry         : Point in EPSG:4326
    source_id        : unique str per settlement
    settlement_class : one of KNOWN_SETTLEMENT_CLASSES (mapped from OSM place tag)
    region           : str (default "africa")
"""

import warnings

import geopandas as gpd
import pytest
from shapely.geometry import Point

from wildlife_water_stress_atlas.config.species import KNOWN_SETTLEMENT_CLASSES
from wildlife_water_stress_atlas.ingest.threats import (
    OSM_PLACE_MAP,
    OSMSettlements,
    load_all_threats,
)

THREATS_READ_FILE = "wildlife_water_stress_atlas.ingest.threats.gpd.read_file"

REQUIRED_SCHEMA_COLUMNS = {"geometry", "source_id", "settlement_class", "region"}


def make_mock_places_gdf(place_values: list[str]) -> gpd.GeoDataFrame:
    """Build a minimal OSM-places-style GeoDataFrame with the given place tags."""
    return gpd.GeoDataFrame(
        {
            "place": place_values,
            "name": [f"Place {i}" for i in range(len(place_values))],
            "osm_id": list(range(len(place_values))),
        },
        geometry=[Point(i, 0) for i in range(len(place_values))],
        crs="EPSG:4326",
    )


@pytest.fixture
def mock_places_gdf():
    """One place of each directly-mapped class."""
    return make_mock_places_gdf(["city", "town", "village", "hamlet"])


# ---------------------------------------------------------------------------
# OSM_PLACE_MAP — the mapping constant itself
# ---------------------------------------------------------------------------


def test_osm_place_map_covers_all_known_settlement_classes():
    """Every KNOWN_SETTLEMENT_CLASS must appear as a value in OSM_PLACE_MAP."""
    assert set(OSM_PLACE_MAP.values()) == KNOWN_SETTLEMENT_CLASSES


def test_osm_place_map_direct_classes_map_to_themselves():
    for cls in KNOWN_SETTLEMENT_CLASSES:
        assert OSM_PLACE_MAP[cls] == cls


def test_osm_place_map_national_capital_maps_to_city():
    assert OSM_PLACE_MAP["national_capital"] == "city"


# ---------------------------------------------------------------------------
# OSMSettlements — normalized schema
# ---------------------------------------------------------------------------


def test_osm_settlements_produces_normalized_schema(monkeypatch, mock_places_gdf):
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: mock_places_gdf)
    result = OSMSettlements("dummy/places.gpkg").load()
    assert REQUIRED_SCHEMA_COLUMNS.issubset(result.columns), f"Missing columns: {REQUIRED_SCHEMA_COLUMNS - set(result.columns)}"


def test_osm_settlements_drops_non_schema_columns(monkeypatch, mock_places_gdf):
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: mock_places_gdf)
    result = OSMSettlements("dummy/places.gpkg").load()
    assert "name" not in result.columns
    assert "osm_id" not in result.columns
    assert "place" not in result.columns


# ---------------------------------------------------------------------------
# OSMSettlements — place tag mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "osm_place,expected_class",
    [
        ("city", "city"),
        ("national_capital", "city"),
        ("town", "town"),
        ("village", "village"),
        ("hamlet", "hamlet"),
    ],
)
def test_osm_settlements_maps_place_to_settlement_class(monkeypatch, osm_place, expected_class):
    gdf = make_mock_places_gdf([osm_place])
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: gdf)
    result = OSMSettlements("dummy/places.gpkg").load()
    assert len(result) == 1
    assert result.iloc[0]["settlement_class"] == expected_class


def test_osm_settlements_all_class_values_are_known(monkeypatch, mock_places_gdf):
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: mock_places_gdf)
    result = OSMSettlements("dummy/places.gpkg").load()
    assert set(result["settlement_class"]).issubset(KNOWN_SETTLEMENT_CLASSES)


def test_osm_settlements_drops_unknown_place_values(monkeypatch):
    """suburb, locality, farm, etc. are not in our settlement model — drop them."""
    gdf = make_mock_places_gdf(["city", "suburb", "locality", "town", "farm"])
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: gdf)
    result = OSMSettlements("dummy/places.gpkg").load()
    assert len(result) == 2
    assert set(result["settlement_class"]) == {"city", "town"}


def test_osm_settlements_returns_empty_when_no_known_classes(monkeypatch):
    gdf = make_mock_places_gdf(["suburb", "locality", "farm"])
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: gdf)
    result = OSMSettlements("dummy/places.gpkg").load()
    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 0


# ---------------------------------------------------------------------------
# OSMSettlements — source_id
# ---------------------------------------------------------------------------


def test_osm_settlements_source_id_is_unique(monkeypatch, mock_places_gdf):
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: mock_places_gdf)
    result = OSMSettlements("dummy/places.gpkg").load()
    assert result["source_id"].nunique() == len(result)


def test_osm_settlements_source_id_is_string(monkeypatch, mock_places_gdf):
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: mock_places_gdf)
    result = OSMSettlements("dummy/places.gpkg").load()
    assert isinstance(result.iloc[0]["source_id"], str)


# ---------------------------------------------------------------------------
# OSMSettlements — region
# ---------------------------------------------------------------------------


def test_osm_settlements_default_region_is_africa(monkeypatch, mock_places_gdf):
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: mock_places_gdf)
    result = OSMSettlements("dummy/places.gpkg").load()
    assert (result["region"] == "africa").all()


def test_osm_settlements_region_can_be_overridden(monkeypatch, mock_places_gdf):
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: mock_places_gdf)
    result = OSMSettlements("dummy/places.gpkg", region="east_africa").load()
    assert (result["region"] == "east_africa").all()


# ---------------------------------------------------------------------------
# OSMSettlements — CRS
# ---------------------------------------------------------------------------


def test_osm_settlements_output_is_wgs84(monkeypatch, mock_places_gdf):
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: mock_places_gdf)
    result = OSMSettlements("dummy/places.gpkg").load()
    assert result.crs.to_string() == "EPSG:4326"


def test_osm_settlements_reprojects_when_not_wgs84(monkeypatch):
    gdf = make_mock_places_gdf(["city"]).to_crs(epsg=3857)
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: gdf)
    result = OSMSettlements("dummy/places.gpkg").load()
    assert result.crs.to_string() == "EPSG:4326"


def test_osm_settlements_sets_crs_when_missing(monkeypatch):
    gdf = gpd.GeoDataFrame(
        {"place": ["city"], "name": ["Place 0"], "osm_id": [0]},
        geometry=[Point(0, 0)],
        crs=None,
    )
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: gdf)
    result = OSMSettlements("dummy/places.gpkg").load()
    assert result.crs.to_string() == "EPSG:4326"


# ---------------------------------------------------------------------------
# OSMSettlements — bbox clipping
# ---------------------------------------------------------------------------


def test_osm_settlements_clips_to_bbox(monkeypatch):
    gdf = gpd.GeoDataFrame(
        {"place": ["city", "city"]},
        geometry=[Point(22, -10), Point(105, 50)],  # inside Africa, far outside (Asia)
        crs="EPSG:4326",
    )
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: gdf)
    result = OSMSettlements("dummy/places.gpkg", bbox=(10, -30, 40, 10)).load()
    assert len(result) == 1


def test_osm_settlements_no_bbox_returns_all_rows(monkeypatch, mock_places_gdf):
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: mock_places_gdf)
    result = OSMSettlements("dummy/places.gpkg").load()
    assert len(result) == len(mock_places_gdf)


# ---------------------------------------------------------------------------
# load_all_threats — registry accepts osm_settlements
# ---------------------------------------------------------------------------


def test_load_all_threats_accepts_osm_settlements_source_type(monkeypatch, mock_places_gdf):
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: mock_places_gdf)
    config = {"sources": {"osm_settlements": {"path": "dummy/places.gpkg"}}}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = load_all_threats(config, bbox=(10, -30, 40, 10))
    assert isinstance(result, gpd.GeoDataFrame)
    assert "settlement_class" in result.columns
