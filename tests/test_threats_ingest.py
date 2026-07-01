"""
test_threats_ingest.py

Tests for src/wildlife_water_stress_atlas/ingest/threats.py

TESTING STRATEGY:
-----------------
All tests mock gpd.read_file — no real OSM data files needed.
Integration tests (marked) hit real filesystem.

FUNCTION COVERAGE:
------------------
- OSMRoads.load()        — reads OSM GeoPackage/Shapefile, maps highway tags,
                           produces normalized schema
- load_all_threats()     — registry function, mirrors load_all_water()

NORMALIZED SCHEMA:
------------------
    geometry   : LineString in EPSG:4326
    source_id  : unique str per segment
    road_class : one of KNOWN_ROAD_CLASSES (mapped from OSM highway tag)
    region     : str (default "africa")
"""

import warnings

import geopandas as gpd
import pytest
from shapely.geometry import LineString

from wildlife_water_stress_atlas.config.species import KNOWN_ROAD_CLASSES
from wildlife_water_stress_atlas.ingest.threats import (
    OSM_HIGHWAY_MAP,
    OSMRoads,
    load_all_threats,
)

THREATS_READ_FILE = "wildlife_water_stress_atlas.ingest.threats.gpd.read_file"

REQUIRED_SCHEMA_COLUMNS = {"geometry", "source_id", "road_class", "region"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_mock_osm_gdf(highway_values: list[str]) -> gpd.GeoDataFrame:
    """Build a minimal OSM-style GeoDataFrame with the given highway tag values."""
    return gpd.GeoDataFrame(
        {
            "highway": highway_values,
            "name": [f"Road {i}" for i in range(len(highway_values))],
            "osm_id": list(range(len(highway_values))),
        },
        geometry=[LineString([(i, 0), (i + 1, 0)]) for i in range(len(highway_values))],
        crs="EPSG:4326",
    )


@pytest.fixture
def mock_roads_gdf():
    """One road of each directly-mapped class."""
    return make_mock_osm_gdf(["motorway", "trunk", "primary", "secondary", "tertiary", "track", "path"])


# ---------------------------------------------------------------------------
# OSM_HIGHWAY_MAP — the mapping constant itself
# ---------------------------------------------------------------------------


def test_osm_highway_map_covers_all_known_road_classes():
    """Every KNOWN_ROAD_CLASS must appear as a value in OSM_HIGHWAY_MAP."""
    assert set(OSM_HIGHWAY_MAP.values()) == KNOWN_ROAD_CLASSES


def test_osm_highway_map_direct_classes_map_to_themselves():
    """The 7 canonical class names map to themselves."""
    for cls in KNOWN_ROAD_CLASSES:
        assert OSM_HIGHWAY_MAP[cls] == cls


def test_osm_highway_map_link_variants_map_to_parent_class():
    """motorway_link, trunk_link, etc. should map to their parent class."""
    assert OSM_HIGHWAY_MAP["motorway_link"] == "motorway"
    assert OSM_HIGHWAY_MAP["trunk_link"] == "trunk"
    assert OSM_HIGHWAY_MAP["primary_link"] == "primary"
    assert OSM_HIGHWAY_MAP["secondary_link"] == "secondary"
    assert OSM_HIGHWAY_MAP["tertiary_link"] == "tertiary"


def test_osm_highway_map_footway_maps_to_path():
    assert OSM_HIGHWAY_MAP["footway"] == "path"


def test_osm_highway_map_cycleway_maps_to_path():
    assert OSM_HIGHWAY_MAP["cycleway"] == "path"


# ---------------------------------------------------------------------------
# OSMRoads — normalized schema
# ---------------------------------------------------------------------------


def test_osm_roads_produces_normalized_schema(monkeypatch, mock_roads_gdf):
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: mock_roads_gdf)
    result = OSMRoads("dummy/roads.gpkg").load()
    assert REQUIRED_SCHEMA_COLUMNS.issubset(result.columns), f"Missing columns: {REQUIRED_SCHEMA_COLUMNS - set(result.columns)}"


def test_osm_roads_drops_non_schema_columns(monkeypatch, mock_roads_gdf):
    """Source-specific columns (name, osm_id, highway) must not appear in output."""
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: mock_roads_gdf)
    result = OSMRoads("dummy/roads.gpkg").load()
    assert "name" not in result.columns
    assert "osm_id" not in result.columns
    assert "highway" not in result.columns


# ---------------------------------------------------------------------------
# OSMRoads — highway tag mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "osm_highway,expected_class",
    [
        ("motorway", "motorway"),
        ("motorway_link", "motorway"),
        ("trunk", "trunk"),
        ("trunk_link", "trunk"),
        ("primary", "primary"),
        ("primary_link", "primary"),
        ("secondary", "secondary"),
        ("secondary_link", "secondary"),
        ("tertiary", "tertiary"),
        ("tertiary_link", "tertiary"),
        ("track", "track"),
        ("path", "path"),
        ("footway", "path"),
        ("cycleway", "path"),
    ],
)
def test_osm_roads_maps_highway_to_road_class(monkeypatch, osm_highway, expected_class):
    gdf = make_mock_osm_gdf([osm_highway])
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: gdf)
    result = OSMRoads("dummy/roads.gpkg").load()
    assert len(result) == 1
    assert result.iloc[0]["road_class"] == expected_class


def test_osm_roads_all_road_class_values_are_known(monkeypatch, mock_roads_gdf):
    """Every road_class in the output must be in KNOWN_ROAD_CLASSES."""
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: mock_roads_gdf)
    result = OSMRoads("dummy/roads.gpkg").load()
    assert set(result["road_class"]).issubset(KNOWN_ROAD_CLASSES)


def test_osm_roads_drops_unknown_highway_values(monkeypatch):
    """residential, service, unclassified, etc. are not in our threat model — drop them."""
    gdf = make_mock_osm_gdf(["motorway", "residential", "service", "primary"])
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: gdf)
    result = OSMRoads("dummy/roads.gpkg").load()
    assert len(result) == 2
    assert set(result["road_class"]) == {"motorway", "primary"}


def test_osm_roads_returns_empty_when_no_known_classes(monkeypatch):
    """If the file contains only unknown highway values, return an empty GeoDataFrame."""
    gdf = make_mock_osm_gdf(["residential", "service", "living_street"])
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: gdf)
    result = OSMRoads("dummy/roads.gpkg").load()
    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 0


# ---------------------------------------------------------------------------
# OSMRoads — source_id
# ---------------------------------------------------------------------------


def test_osm_roads_source_id_is_unique(monkeypatch, mock_roads_gdf):
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: mock_roads_gdf)
    result = OSMRoads("dummy/roads.gpkg").load()
    assert result["source_id"].nunique() == len(result)


def test_osm_roads_source_id_is_string(monkeypatch, mock_roads_gdf):
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: mock_roads_gdf)
    result = OSMRoads("dummy/roads.gpkg").load()
    assert isinstance(result.iloc[0]["source_id"], str)


# ---------------------------------------------------------------------------
# OSMRoads — region
# ---------------------------------------------------------------------------


def test_osm_roads_default_region_is_africa(monkeypatch, mock_roads_gdf):
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: mock_roads_gdf)
    result = OSMRoads("dummy/roads.gpkg").load()
    assert (result["region"] == "africa").all()


def test_osm_roads_region_can_be_overridden(monkeypatch, mock_roads_gdf):
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: mock_roads_gdf)
    result = OSMRoads("dummy/roads.gpkg", region="east_africa").load()
    assert (result["region"] == "east_africa").all()


# ---------------------------------------------------------------------------
# OSMRoads — CRS
# ---------------------------------------------------------------------------


def test_osm_roads_output_is_wgs84(monkeypatch, mock_roads_gdf):
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: mock_roads_gdf)
    result = OSMRoads("dummy/roads.gpkg").load()
    assert result.crs.to_string() == "EPSG:4326"


def test_osm_roads_reprojects_when_not_wgs84(monkeypatch):
    gdf = make_mock_osm_gdf(["motorway"])
    gdf = gdf.to_crs(epsg=3857)
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: gdf)
    result = OSMRoads("dummy/roads.gpkg").load()
    assert result.crs.to_string() == "EPSG:4326"


def test_osm_roads_sets_crs_when_missing(monkeypatch):
    gdf = gpd.GeoDataFrame(
        {"highway": ["primary"], "name": ["Road 0"], "osm_id": [0]},
        geometry=[LineString([(0, 0), (1, 0)])],
        crs=None,
    )
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: gdf)
    result = OSMRoads("dummy/roads.gpkg").load()
    assert result.crs.to_string() == "EPSG:4326"


# ---------------------------------------------------------------------------
# OSMRoads — bbox clipping
# ---------------------------------------------------------------------------


def test_osm_roads_clips_to_bbox(monkeypatch):
    gdf = gpd.GeoDataFrame(
        {"highway": ["motorway", "motorway"]},
        geometry=[
            LineString([(20, -10), (25, -10)]),  # inside Africa bbox
            LineString([(100, 50), (110, 50)]),  # far outside — Asia
        ],
        crs="EPSG:4326",
    )
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: gdf)
    result = OSMRoads("dummy/roads.gpkg", bbox=(10, -30, 40, 10)).load()
    assert len(result) == 1


def test_osm_roads_no_bbox_returns_all_rows(monkeypatch, mock_roads_gdf):
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: mock_roads_gdf)
    result = OSMRoads("dummy/roads.gpkg").load()
    assert len(result) == len(mock_roads_gdf)


# ---------------------------------------------------------------------------
# load_all_threats — registry function
# ---------------------------------------------------------------------------


def test_load_all_threats_accepts_osm_roads_source_type(monkeypatch, mock_roads_gdf):
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: mock_roads_gdf)
    config = {"sources": {"osm_roads": {"path": "dummy/roads.gpkg"}}}
    result = load_all_threats(config, bbox=(10, -30, 40, 10))
    assert isinstance(result, gpd.GeoDataFrame)
    assert "road_class" in result.columns


def test_load_all_threats_warns_when_no_bbox(monkeypatch, mock_roads_gdf):
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: mock_roads_gdf)
    config = {"sources": {"osm_roads": {"path": "dummy/roads.gpkg"}}}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        load_all_threats(config)
    assert any("bbox" in str(w.message).lower() for w in caught)


def test_load_all_threats_raises_for_unknown_source_type(monkeypatch, mock_roads_gdf):
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: mock_roads_gdf)
    config = {"sources": {"unknown_source": {"path": "dummy/data.gpkg"}}}
    with pytest.raises(KeyError, match="Unknown source type"):
        load_all_threats(config, bbox=(10, -30, 40, 10))


def test_load_all_threats_output_has_normalized_schema(monkeypatch, mock_roads_gdf):
    monkeypatch.setattr(THREATS_READ_FILE, lambda _: mock_roads_gdf)
    config = {"sources": {"osm_roads": {"path": "dummy/roads.gpkg"}}}
    result = load_all_threats(config, bbox=(10, -30, 40, 10))
    assert REQUIRED_SCHEMA_COLUMNS.issubset(result.columns)
