"""
test_water_sources.py

Tests for the refactored water source architecture in ingest/water.py.

Coverage targets:
- WaterMechanism enum
- WaterSource abstract base class contract
- ShapefileRivers and ShapefileLakes concrete classes
- Normalized schema on output GeoDataFrames
- load_all_water() registry function (bbox, warning, combining)
- Convenience functions load_rivers() and load_lakes() unchanged behavior
"""

import warnings

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Polygon

from wildlife_water_stress_atlas.ingest.water import (
    ShapefileLakes,
    ShapefileRivers,
    WaterMechanism,
    combine_water_layers,
    load_all_water,
    load_lakes,
    load_rivers,
)

# The full module path to gpd.read_file as used inside water.py.
# We patch at this path so the monkeypatch intercepts the call
# where it actually happens, not at the top-level gpd module.
WATER_READ_FILE = "wildlife_water_stress_atlas.ingest.water.gpd.read_file"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_rivers_gdf():
    """A minimal rivers GeoDataFrame simulating a loaded shapefile."""
    return gpd.GeoDataFrame(
        {"name": ["Test River"]},
        geometry=[LineString([(0, 0), (1, 1)])],
        crs="EPSG:4326",
    )


@pytest.fixture
def mock_lakes_gdf():
    """A minimal lakes GeoDataFrame simulating a loaded shapefile."""
    return gpd.GeoDataFrame(
        {"name": ["Test Lake"]},
        geometry=[Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])],
        crs="EPSG:4326",
    )


# ---------------------------------------------------------------------------
# WaterMechanism enum
# ---------------------------------------------------------------------------

def test_water_mechanism_has_permanent_surface():
    assert WaterMechanism.PERMANENT_SURFACE


def test_water_mechanism_has_seasonal_surface():
    assert WaterMechanism.SEASONAL_SURFACE


def test_water_mechanism_has_groundwater():
    assert WaterMechanism.GROUNDWATER


def test_water_mechanism_has_artificial():
    assert WaterMechanism.ARTIFICIAL


def test_water_mechanism_has_derived():
    assert WaterMechanism.DERIVED


def test_water_mechanism_invalid_value_raises():
    # Confirms the Enum rejects unknown values — the whole point of using
    # an Enum over a plain string
    with pytest.raises(ValueError):
        WaterMechanism("not_a_real_mechanism")


# ---------------------------------------------------------------------------
# Normalized schema
# ---------------------------------------------------------------------------

REQUIRED_SCHEMA_COLUMNS = {
    "geometry",
    "source_id",
    "water_type",
    "mechanism",
    "permanence",
    "reliability",
    "months_water",
    "region",
}


def test_shapefile_rivers_produces_normalized_schema(monkeypatch, mock_rivers_gdf):
    monkeypatch.setattr(WATER_READ_FILE, lambda _: mock_rivers_gdf)

    source = ShapefileRivers("dummy/path.shp")
    result = source.load()

    assert REQUIRED_SCHEMA_COLUMNS.issubset(result.columns), (
        f"Missing columns: {REQUIRED_SCHEMA_COLUMNS - set(result.columns)}"
    )


def test_shapefile_lakes_produces_normalized_schema(monkeypatch, mock_lakes_gdf):
    monkeypatch.setattr(WATER_READ_FILE, lambda _: mock_lakes_gdf)

    source = ShapefileLakes("dummy/path.shp")
    result = source.load()

    assert REQUIRED_SCHEMA_COLUMNS.issubset(result.columns), (
        f"Missing columns: {REQUIRED_SCHEMA_COLUMNS - set(result.columns)}"
    )


# ---------------------------------------------------------------------------
# water_type column values
# ---------------------------------------------------------------------------

def test_shapefile_rivers_sets_water_type_to_river(monkeypatch, mock_rivers_gdf):
    monkeypatch.setattr(WATER_READ_FILE, lambda _: mock_rivers_gdf)

    source = ShapefileRivers("dummy/path.shp")
    result = source.load()

    assert (result["water_type"] == "river").all()


def test_shapefile_lakes_sets_water_type_to_lake(monkeypatch, mock_lakes_gdf):
    monkeypatch.setattr(WATER_READ_FILE, lambda _: mock_lakes_gdf)

    source = ShapefileLakes("dummy/path.shp")
    result = source.load()

    assert (result["water_type"] == "lake").all()


# ---------------------------------------------------------------------------
# mechanism column values
# ---------------------------------------------------------------------------

def test_shapefile_rivers_mechanism_is_permanent_surface(monkeypatch, mock_rivers_gdf):
    monkeypatch.setattr(WATER_READ_FILE, lambda _: mock_rivers_gdf)

    source = ShapefileRivers("dummy/path.shp")
    result = source.load()

    assert (result["mechanism"] == WaterMechanism.PERMANENT_SURFACE).all()


def test_shapefile_lakes_mechanism_is_permanent_surface(monkeypatch, mock_lakes_gdf):
    monkeypatch.setattr(WATER_READ_FILE, lambda _: mock_lakes_gdf)

    source = ShapefileLakes("dummy/path.shp")
    result = source.load()

    assert (result["mechanism"] == WaterMechanism.PERMANENT_SURFACE).all()


# ---------------------------------------------------------------------------
# CRS
# ---------------------------------------------------------------------------

def test_shapefile_rivers_output_is_wgs84(monkeypatch, mock_rivers_gdf):
    monkeypatch.setattr(WATER_READ_FILE, lambda _: mock_rivers_gdf)

    source = ShapefileRivers("dummy/path.shp")
    result = source.load()

    assert result.crs.to_string() == "EPSG:4326"


def test_shapefile_lakes_output_is_wgs84(monkeypatch, mock_lakes_gdf):
    monkeypatch.setattr(WATER_READ_FILE, lambda _: mock_lakes_gdf)

    source = ShapefileLakes("dummy/path.shp")
    result = source.load()

    assert result.crs.to_string() == "EPSG:4326"


# ---------------------------------------------------------------------------
# CRS missing / needs conversion
# ---------------------------------------------------------------------------

def test_shapefile_rivers_sets_crs_when_missing(monkeypatch, mock_rivers_gdf):
    # Simulate a shapefile that comes back with no CRS set
    mock_rivers_gdf_no_crs = gpd.GeoDataFrame(
        {"name": ["Test River"]},
        geometry=[LineString([(0, 0), (1, 1)])],
        crs=None,
    )
    monkeypatch.setattr(WATER_READ_FILE, lambda _: mock_rivers_gdf_no_crs)

    source = ShapefileRivers("dummy/path.shp")
    result = source.load()

    assert result.crs.to_string() == "EPSG:4326"


def test_shapefile_lakes_sets_crs_when_missing(monkeypatch, mock_lakes_gdf):
    mock_lakes_gdf_no_crs = gpd.GeoDataFrame(
        {"name": ["Test Lake"]},
        geometry=[Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])],
        crs=None,
    )
    monkeypatch.setattr(WATER_READ_FILE, lambda _: mock_lakes_gdf_no_crs)

    source = ShapefileLakes("dummy/path.shp")
    result = source.load()

    assert result.crs.to_string() == "EPSG:4326"


# ---------------------------------------------------------------------------
# bbox clipping
# ---------------------------------------------------------------------------

def test_shapefile_rivers_clips_to_bbox(monkeypatch):
    gdf = gpd.GeoDataFrame(
        {"name": ["In bbox", "Out of bbox"]},
        geometry=[
            LineString([(20, -10), (25, -10)]),
            LineString([(100, 50), (110, 50)]),
        ],
        crs="EPSG:4326",
    )
    monkeypatch.setattr(WATER_READ_FILE, lambda _: gdf)

    bbox = (10, -30, 40, 10)
    source = ShapefileRivers("dummy/path.shp", bbox=bbox)
    result = source.load()

    assert len(result) == 1
    assert result.iloc[0]["water_type"] == "river"


def test_shapefile_lakes_clips_to_bbox(monkeypatch):
    gdf = gpd.GeoDataFrame(
        {"name": ["In bbox", "Out of bbox"]},
        geometry=[
            Polygon([(20, -10), (20, -9), (21, -9), (21, -10)]),
            Polygon([(100, 50), (100, 51), (101, 51), (101, 50)]),
        ],
        crs="EPSG:4326",
    )
    monkeypatch.setattr(WATER_READ_FILE, lambda _: gdf)

    bbox = (10, -30, 40, 10)
    source = ShapefileLakes("dummy/path.shp", bbox=bbox)
    result = source.load()

    assert len(result) == 1
    assert result.iloc[0]["water_type"] == "lake"


# ---------------------------------------------------------------------------
# load_all_water — registry function
# ---------------------------------------------------------------------------

def test_load_all_water_warns_when_no_bbox_provided(monkeypatch, mock_rivers_gdf, mock_lakes_gdf):
    monkeypatch.setattr(
        WATER_READ_FILE,
        lambda path: mock_rivers_gdf if "river" in path else mock_lakes_gdf,
    )

    config = {
        "sources": {
            "rivers": {"path": "dummy/rivers.shp"},
            "lakes":  {"path": "dummy/lakes.shp"},
        }
    }

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        load_all_water(config)

    messages = [str(w.message) for w in caught]
    assert any("bbox" in m.lower() for m in messages), (
        "Expected a warning about missing bbox"
    )


def test_load_all_water_returns_combined_geodataframe(monkeypatch, mock_rivers_gdf, mock_lakes_gdf):
    monkeypatch.setattr(
        WATER_READ_FILE,
        lambda path: mock_rivers_gdf if "river" in path else mock_lakes_gdf,
    )

    config = {
        "sources": {
            "rivers": {"path": "dummy/rivers.shp"},
            "lakes":  {"path": "dummy/lakes.shp"},
        }
    }

    result = load_all_water(config)

    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 2
    assert set(result["water_type"]) == {"river", "lake"}


def test_load_all_water_with_bbox_does_not_warn(monkeypatch, mock_rivers_gdf, mock_lakes_gdf):
    monkeypatch.setattr(
        WATER_READ_FILE,
        lambda path: mock_rivers_gdf if "river" in path else mock_lakes_gdf,
    )

    config = {
        "sources": {
            "rivers": {"path": "dummy/rivers.shp"},
            "lakes":  {"path": "dummy/lakes.shp"},
        }
    }

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        load_all_water(config, bbox=(10, -30, 40, 10))

    bbox_warnings = [w for w in caught if "bbox" in str(w.message).lower()]
    assert len(bbox_warnings) == 0


def test_load_all_water_output_has_normalized_schema(monkeypatch, mock_rivers_gdf, mock_lakes_gdf):
    monkeypatch.setattr(
        WATER_READ_FILE,
        lambda path: mock_rivers_gdf if "river" in path else mock_lakes_gdf,
    )

    config = {
        "sources": {
            "rivers": {"path": "dummy/rivers.shp"},
            "lakes":  {"path": "dummy/lakes.shp"},
        }
    }

    result = load_all_water(config)

    assert REQUIRED_SCHEMA_COLUMNS.issubset(result.columns)


def test_load_all_water_raises_for_unknown_source_type(monkeypatch, mock_rivers_gdf):
    monkeypatch.setattr(WATER_READ_FILE, lambda _: mock_rivers_gdf)

    config = {
        "sources": {
            "swamps": {"path": "dummy/swamps.shp"},
        }
    }

    with pytest.raises(KeyError, match="Unknown source type"):
        load_all_water(config, bbox=(10, -30, 40, 10))


# ---------------------------------------------------------------------------
# Convenience functions — unchanged behavior
# ---------------------------------------------------------------------------

def test_load_rivers_convenience_still_works(monkeypatch, mock_rivers_gdf):
    monkeypatch.setattr(WATER_READ_FILE, lambda _: mock_rivers_gdf)

    result = load_rivers("dummy/path.shp")

    assert isinstance(result, gpd.GeoDataFrame)
    assert result.crs.to_string() == "EPSG:4326"
    assert len(result) > 0


def test_load_lakes_convenience_still_works(monkeypatch, mock_lakes_gdf):
    monkeypatch.setattr(WATER_READ_FILE, lambda _: mock_lakes_gdf)

    result = load_lakes("dummy/path.shp")

    assert isinstance(result, gpd.GeoDataFrame)
    assert result.crs.to_string() == "EPSG:4326"
    assert len(result) > 0


def test_combine_water_layers_still_works(mock_rivers_gdf, mock_lakes_gdf):
    result = combine_water_layers(mock_rivers_gdf, mock_lakes_gdf)

    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 2
    assert result.crs.to_string() == "EPSG:4326"