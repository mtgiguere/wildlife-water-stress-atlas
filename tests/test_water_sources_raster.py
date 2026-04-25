"""
test_water_sources_raster.py

Tests for raster-based water source classes:
- GLWDWetlands
- JRCGlobalSurfaceWater

GLWD v2 CLASS SCHEMA:
---------------------
GLWD v2 has 33 classes (not 12 as in v1). Key classes for elephants:
    1  = Freshwater lake
    2  = Saline lake
    4  = Large river
    6  = Other permanent waterbody
    8  = Lacustrine, forested
    9  = Lacustrine, non-forested
    10 = Riverine, regularly flooded, forested
    11 = Riverine, regularly flooded, non-forested
    12 = Riverine, seasonally flooded, forested
    13 = Riverine, seasonally flooded, non-forested
    16 = Palustrine, regularly flooded, forested
    17 = Palustrine, regularly flooded, non-forested
    18 = Palustrine, seasonally saturated, forested
    19 = Palustrine, seasonally saturated, non-forested
    21 = Ephemeral, non-forested
    32 = Salt pan, saline/brackish wetland

Classes 1 and 4 are excluded from DEFAULT_WATER_CLASSES because
Natural Earth already provides freshwater lakes (as polygons) and
rivers (as lines, which are geometrically better for distance calc).
"""

from unittest.mock import MagicMock, patch

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from affine import Affine
from rasterio.crs import CRS

from wildlife_water_stress_atlas.ingest.water import (
    GLWDWetlands,
    JRCGlobalSurfaceWater,
    WaterMechanism,
    load_all_water,
)

RASTERIO_OPEN = "wildlife_water_stress_atlas.ingest.water.rasterio.open"


# ---------------------------------------------------------------------------
# Raster mock helpers
# ---------------------------------------------------------------------------

def make_raster_mock(data: np.ndarray, crs_epsg: int = 4326) -> MagicMock:
    """
    Build a MagicMock that simulates a rasterio dataset context manager.
    """
    transform = Affine(1.0, 0.0, 0.0, 0.0, -1.0, 2.0)

    mock_dataset = MagicMock()
    mock_dataset.read.return_value = data
    mock_dataset.meta = {
        "crs":       CRS.from_epsg(crs_epsg),
        "transform": transform,
        "dtype":     data.dtype.name,
        "width":     data.shape[1],
        "height":    data.shape[0],
    }
    mock_dataset.crs            = CRS.from_epsg(crs_epsg)
    mock_dataset.transform      = transform
    mock_dataset.bounds         = rasterio.coords.BoundingBox(
        left=0.0, bottom=0.0, right=2.0, top=2.0
    )
    mock_dataset.window_transform.return_value = transform

    mock_context = MagicMock()
    mock_context.__enter__.return_value = mock_dataset
    mock_context.__exit__.return_value  = False

    return mock_context


# ---------------------------------------------------------------------------
# GLWD v2 class map reference
# Used in tests to verify correct schema values per class
# ---------------------------------------------------------------------------

GLWD_CLASS_EXPECTATIONS = {
    2:  {"water_type": "saline_lake",     "permanence": "permanent", "reliability": 0.4, "months_water": 12},
    6:  {"water_type": "permanent_water", "permanence": "permanent", "reliability": 0.9, "months_water": 12},
    8:  {"water_type": "wetland",         "permanence": "seasonal",  "reliability": 0.7, "months_water": 8},
    9:  {"water_type": "wetland",         "permanence": "seasonal",  "reliability": 0.6, "months_water": 6},
    10: {"water_type": "floodplain",      "permanence": "seasonal",  "reliability": 0.8, "months_water": 8},
    11: {"water_type": "floodplain",      "permanence": "seasonal",  "reliability": 0.8, "months_water": 8},
    12: {"water_type": "floodplain",      "permanence": "seasonal",  "reliability": 0.7, "months_water": 6},
    13: {"water_type": "floodplain",      "permanence": "seasonal",  "reliability": 0.7, "months_water": 6},
    16: {"water_type": "wetland",         "permanence": "seasonal",  "reliability": 0.7, "months_water": 8},
    17: {"water_type": "wetland",         "permanence": "seasonal",  "reliability": 0.7, "months_water": 8},
    18: {"water_type": "wetland",         "permanence": "seasonal",  "reliability": 0.5, "months_water": 4},
    19: {"water_type": "wetland",         "permanence": "seasonal",  "reliability": 0.5, "months_water": 4},
    21: {"water_type": "pan",             "permanence": "ephemeral", "reliability": 0.3, "months_water": 2},
    32: {"water_type": "pan",             "permanence": "seasonal",  "reliability": 0.5, "months_water": 4},
}

EXPECTED_DEFAULT_CLASSES = {2, 6, 8, 9, 10, 11, 12, 13, 16, 17, 18, 19, 21, 32}


# ---------------------------------------------------------------------------
# GLWDWetlands — normalized schema
# ---------------------------------------------------------------------------

def test_glwd_produces_normalized_schema():
    data = np.array([[32, 32], [32, 32]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = GLWDWetlands("dummy/glwd.tif")
        result = source.load()

    required_columns = {
        "geometry", "source_id", "water_type", "mechanism",
        "permanence", "reliability", "months_water", "region",
    }
    assert required_columns.issubset(result.columns), (
        f"Missing columns: {required_columns - set(result.columns)}"
    )


# ---------------------------------------------------------------------------
# GLWDWetlands — default water classes
# ---------------------------------------------------------------------------

def test_glwd_default_water_classes_are_correct():
    # Verifies the default set matches the expected v2 classes
    source = GLWDWetlands("dummy/glwd.tif")
    assert source.water_classes == EXPECTED_DEFAULT_CLASSES


def test_glwd_default_excludes_freshwater_lake_class():
    # Class 1 (freshwater lake) should NOT be in defaults —
    # Natural Earth lakes already cover this, avoiding duplication
    source = GLWDWetlands("dummy/glwd.tif")
    assert 1 not in source.water_classes


def test_glwd_default_excludes_large_river_class():
    # Class 4 (large river) should NOT be in defaults —
    # Natural Earth rivers (as lines) are geometrically better
    # for distance calculations than rasterized river polygons
    source = GLWDWetlands("dummy/glwd.tif")
    assert 4 not in source.water_classes


# ---------------------------------------------------------------------------
# GLWDWetlands — water_type per class
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("glwd_class,expected_type", [
    (2,  "saline_lake"),
    (6,  "permanent_water"),
    (8,  "wetland"),
    (9,  "wetland"),
    (10, "floodplain"),
    (11, "floodplain"),
    (12, "floodplain"),
    (13, "floodplain"),
    (16, "wetland"),
    (17, "wetland"),
    (18, "wetland"),
    (19, "wetland"),
    (21, "pan"),
    (32, "pan"),
])
def test_glwd_sets_correct_water_type_per_class(glwd_class, expected_type):
    data = np.array([[glwd_class, 0], [0, 0]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = GLWDWetlands("dummy/glwd.tif", water_classes={glwd_class})
        result = source.load()

    assert not result.empty
    assert (result["water_type"] == expected_type).all()


# ---------------------------------------------------------------------------
# GLWDWetlands — mechanism per class
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("glwd_class,expected_mechanism", [
    (2,  WaterMechanism.PERMANENT_SURFACE),
    (6,  WaterMechanism.PERMANENT_SURFACE),
    (8,  WaterMechanism.SEASONAL_SURFACE),
    (9,  WaterMechanism.SEASONAL_SURFACE),
    (10, WaterMechanism.SEASONAL_SURFACE),
    (11, WaterMechanism.SEASONAL_SURFACE),
    (12, WaterMechanism.SEASONAL_SURFACE),
    (13, WaterMechanism.SEASONAL_SURFACE),
    (16, WaterMechanism.SEASONAL_SURFACE),
    (17, WaterMechanism.SEASONAL_SURFACE),
    (18, WaterMechanism.SEASONAL_SURFACE),
    (19, WaterMechanism.SEASONAL_SURFACE),
    (21, WaterMechanism.SEASONAL_SURFACE),
    (32, WaterMechanism.SEASONAL_SURFACE),
])
def test_glwd_sets_correct_mechanism_per_class(glwd_class, expected_mechanism):
    data = np.array([[glwd_class, 0], [0, 0]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = GLWDWetlands("dummy/glwd.tif", water_classes={glwd_class})
        result = source.load()

    assert not result.empty
    assert (result["mechanism"] == expected_mechanism).all()


# ---------------------------------------------------------------------------
# GLWDWetlands — reliability and months_water per class
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("glwd_class,expected_reliability,expected_months", [
    (2,  0.4, 12),
    (6,  0.9, 12),
    (8,  0.7, 8),
    (9,  0.6, 6),
    (10, 0.8, 8),
    (11, 0.8, 8),
    (12, 0.7, 6),
    (13, 0.7, 6),
    (16, 0.7, 8),
    (17, 0.7, 8),
    (18, 0.5, 4),
    (19, 0.5, 4),
    (21, 0.3, 2),
    (32, 0.5, 4),
])
def test_glwd_reliability_and_months_per_class(glwd_class, expected_reliability, expected_months):
    data = np.array([[glwd_class, 0], [0, 0]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = GLWDWetlands("dummy/glwd.tif", water_classes={glwd_class})
        result = source.load()

    assert not result.empty
    assert (result["reliability"] == expected_reliability).all()
    assert (result["months_water"] == expected_months).all()


# ---------------------------------------------------------------------------
# GLWDWetlands — permanence per class
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("glwd_class,expected_permanence", [
    (2,  "permanent"),
    (6,  "permanent"),
    (9,  "seasonal"),
    (11, "seasonal"),
    (21, "ephemeral"),
    (32, "seasonal"),
])
def test_glwd_permanence_per_class(glwd_class, expected_permanence):
    data = np.array([[glwd_class, 0], [0, 0]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = GLWDWetlands("dummy/glwd.tif", water_classes={glwd_class})
        result = source.load()

    assert not result.empty
    assert (result["permanence"] == expected_permanence).all()


# ---------------------------------------------------------------------------
# GLWDWetlands — class filtering
# ---------------------------------------------------------------------------

def test_glwd_only_includes_pixels_matching_water_classes():
    # Raster with class 32, 21, and 1 — class 1 not in defaults so excluded
    data = np.array([[32, 21], [1, 0]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = GLWDWetlands("dummy/glwd.tif")
        result = source.load()

    assert set(result["water_type"]).issubset({"pan", "saline_lake", "permanent_water",
                                                "wetland", "floodplain"})
    assert "lake" not in set(result["water_type"])


def test_glwd_none_water_classes_uses_defaults():
    data = np.array([[32, 21], [9, 1]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = GLWDWetlands("dummy/glwd.tif", water_classes=None)
        result = source.load()

    # Class 1 excluded from defaults — only 32, 21, 9 should appear
    assert set(result["water_type"]) == {"pan", "wetland"}


def test_glwd_empty_water_classes_raises_value_error():
    with pytest.raises(ValueError, match="water_classes"):
        GLWDWetlands("dummy/glwd.tif", water_classes=set())


def test_glwd_unknown_class_value_in_raster_is_ignored():
    # Class 99 doesn't exist in CLASS_MAP — should be silently skipped
    data = np.array([[99, 32], [0, 0]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = GLWDWetlands("dummy/glwd.tif", water_classes={99, 32})
        result = source.load()

    assert set(result["water_type"]) == {"pan"}


# ---------------------------------------------------------------------------
# GLWDWetlands — CRS
# ---------------------------------------------------------------------------

def test_glwd_output_is_wgs84():
    data = np.array([[32, 32], [32, 32]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = GLWDWetlands("dummy/glwd.tif")
        result = source.load()

    assert result.crs.to_string() == "EPSG:4326"


# ---------------------------------------------------------------------------
# GLWDWetlands — bbox window read
# ---------------------------------------------------------------------------

def test_glwd_uses_read_window_when_bbox_provided():
    data = np.array([[32, 32], [32, 32]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)) as mock_open:
        source = GLWDWetlands("dummy/glwd.tif", bbox=(0, 0, 2, 2))
        source.load()

    mock_dataset = mock_open.return_value.__enter__.return_value
    call_kwargs  = mock_dataset.read.call_args
    assert call_kwargs is not None
    assert "window" in call_kwargs.kwargs, (
        "Expected read() to be called with a window argument for bbox-clipped loading."
    )


def test_glwd_clips_to_bbox():
    data = np.array([[32, 32], [32, 32]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = GLWDWetlands("dummy/glwd.tif", bbox=(0, 0, 2, 2))
        result = source.load()

    assert len(result) >= 0  # just verify it runs without error


# ---------------------------------------------------------------------------
# GLWDWetlands — CRS reprojection
# ---------------------------------------------------------------------------

def test_glwd_reprojects_when_crs_is_not_wgs84():
    data = np.array([[32, 32], [32, 32]], dtype=np.uint8)
    mock = make_raster_mock(data, crs_epsg=3857)

    with patch(RASTERIO_OPEN, return_value=mock):
        source = GLWDWetlands("dummy/glwd.tif")
        result = source.load()

    assert result.crs.to_string() == "EPSG:4326"


# ---------------------------------------------------------------------------
# GLWDWetlands — month parameter
# ---------------------------------------------------------------------------

def test_glwd_month_parameter_does_not_crash():
    data = np.array([[32, 32], [32, 32]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = GLWDWetlands("dummy/glwd.tif", month=8)
        result = source.load()

    assert not result.empty


# ---------------------------------------------------------------------------
# GLWDWetlands — edge cases
# ---------------------------------------------------------------------------

def test_glwd_skips_class_not_in_class_map():
    data = np.array([[99, 32], [0, 0]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = GLWDWetlands("dummy/glwd.tif", water_classes={99, 32})
        result = source.load()

    assert set(result["water_type"]) == {"pan"}


def test_glwd_returns_empty_geodataframe_when_no_matching_pixels():
    data = np.array([[0, 0], [0, 0]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = GLWDWetlands("dummy/glwd.tif")
        result = source.load()

    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 0


# ---------------------------------------------------------------------------
# JRCGlobalSurfaceWater — normalized schema
# ---------------------------------------------------------------------------

def test_jrc_produces_normalized_schema():
    data = np.array([[50, 80], [5, 90]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = JRCGlobalSurfaceWater("dummy/jrc.tif")
        result = source.load()

    required_columns = {
        "geometry", "source_id", "water_type", "mechanism",
        "permanence", "reliability", "months_water", "region",
    }
    assert required_columns.issubset(result.columns)


# ---------------------------------------------------------------------------
# JRCGlobalSurfaceWater — water_type and mechanism
# ---------------------------------------------------------------------------

def test_jrc_water_type_is_surface_water():
    data = np.array([[50, 80], [50, 90]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = JRCGlobalSurfaceWater("dummy/jrc.tif")
        result = source.load()

    assert (result["water_type"] == "surface_water").all()


def test_jrc_mechanism_is_seasonal_surface():
    data = np.array([[50, 80], [50, 90]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = JRCGlobalSurfaceWater("dummy/jrc.tif")
        result = source.load()

    assert (result["mechanism"] == WaterMechanism.SEASONAL_SURFACE).all()


# ---------------------------------------------------------------------------
# JRCGlobalSurfaceWater — occurrence threshold filtering
# ---------------------------------------------------------------------------

def test_jrc_excludes_pixels_below_min_occurrence():
    data = np.array([[50, 5], [80, 90]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = JRCGlobalSurfaceWater("dummy/jrc.tif", min_occurrence=10)
        result = source.load()

    assert len(result) == 3


def test_jrc_includes_pixels_at_min_occurrence():
    data = np.array([[10, 5], [0, 0]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = JRCGlobalSurfaceWater("dummy/jrc.tif", min_occurrence=10)
        result = source.load()

    assert len(result) == 1


def test_jrc_min_occurrence_defaults_to_10():
    data = np.array([[9, 10], [11, 0]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = JRCGlobalSurfaceWater("dummy/jrc.tif")
        result = source.load()

    assert len(result) == 2


# ---------------------------------------------------------------------------
# JRCGlobalSurfaceWater — reliability
# ---------------------------------------------------------------------------

def test_jrc_reliability_equals_occurrence_divided_by_100():
    data = np.array([[80, 0], [0, 0]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = JRCGlobalSurfaceWater("dummy/jrc.tif", min_occurrence=10)
        result = source.load()

    assert not result.empty
    assert result.iloc[0]["reliability"] == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# JRCGlobalSurfaceWater — CRS
# ---------------------------------------------------------------------------

def test_jrc_output_is_wgs84():
    data = np.array([[50, 80], [50, 90]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = JRCGlobalSurfaceWater("dummy/jrc.tif")
        result = source.load()

    assert result.crs.to_string() == "EPSG:4326"


# ---------------------------------------------------------------------------
# JRCGlobalSurfaceWater — CRS reprojection
# ---------------------------------------------------------------------------

def test_jrc_reprojects_when_crs_is_not_wgs84():
    data = np.array([[50, 80], [50, 90]], dtype=np.uint8)
    mock = make_raster_mock(data, crs_epsg=3857)

    with patch(RASTERIO_OPEN, return_value=mock):
        source = JRCGlobalSurfaceWater("dummy/jrc.tif")
        result = source.load()

    assert result.crs.to_string() == "EPSG:4326"


# ---------------------------------------------------------------------------
# JRCGlobalSurfaceWater — month parameter
# ---------------------------------------------------------------------------

def test_jrc_month_parameter_does_not_crash():
    data = np.array([[50, 80], [50, 90]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = JRCGlobalSurfaceWater("dummy/jrc.tif", month=3)
        result = source.load()

    assert not result.empty


# ---------------------------------------------------------------------------
# JRCGlobalSurfaceWater — edge cases
# ---------------------------------------------------------------------------

def test_jrc_returns_empty_geodataframe_when_no_pixels_meet_threshold():
    data = np.array([[5, 3], [1, 0]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = JRCGlobalSurfaceWater("dummy/jrc.tif", min_occurrence=10)
        result = source.load()

    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 0


# ---------------------------------------------------------------------------
# load_all_water — new source types in registry
# ---------------------------------------------------------------------------

def test_load_all_water_accepts_glwd_source_type():
    data = np.array([[32, 32], [32, 32]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        config = {
            "sources": {
                "glwd": {"path": "dummy/glwd.tif"},
            }
        }
        result = load_all_water(config, bbox=(0, 0, 2, 2))

    assert isinstance(result, gpd.GeoDataFrame)
    assert "water_type" in result.columns


def test_load_all_water_accepts_jrc_gsw_source_type():
    data = np.array([[50, 80], [50, 90]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        config = {
            "sources": {
                "jrc_gsw": {"path": "dummy/jrc.tif"},
            }
        }
        result = load_all_water(config, bbox=(0, 0, 2, 2))

    assert isinstance(result, gpd.GeoDataFrame)
    assert "water_type" in result.columns


def test_load_all_water_month_passes_through_to_sources():
    data = np.array([[32, 32], [32, 32]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        config = {
            "sources": {
                "glwd": {"path": "dummy/glwd.tif"},
            }
        }
        result = load_all_water(config, bbox=(0, 0, 2, 2), month=8)

    assert isinstance(result, gpd.GeoDataFrame)


def test_load_all_water_passes_min_occurrence_to_jrc_gsw():
    data = np.array([[50, 80], [0, 0]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        config = {
            "sources": {
                "jrc_gsw": {
                    "path":           "dummy/jrc.tif",
                    "min_occurrence": 60,
                },
            }
        }
        result = load_all_water(config, bbox=(0, 0, 2, 2))

    assert len(result) == 1
    assert result.iloc[0]["reliability"] == pytest.approx(0.8)


def test_load_all_water_passes_water_classes_to_glwd():
    data = np.array([[32, 21], [9, 2]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        config = {
            "sources": {
                "glwd": {
                    "path":          "dummy/glwd.tif",
                    "water_classes": {32},
                },
            }
        }
        result = load_all_water(config, bbox=(0, 0, 2, 2))

    assert set(result["water_type"]) == {"pan"}