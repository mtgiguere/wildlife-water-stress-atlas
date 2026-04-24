"""
test_water_sources_raster.py

Tests for raster-based water source classes:
- GLWDWetlands
- JRCGlobalSurfaceWater

These tests mock rasterio.open() rather than gpd.read_file() since
raster sources use a fundamentally different loading mechanism.
A rasterio dataset is a context manager, so we use MagicMock to
simulate the rasterio dataset interface without needing real files.

MOCKING STRATEGY:
-----------------
rasterio.open() returns a dataset object used as a context manager:

    with rasterio.open("path.tif") as src:
        data = src.read(1)
        meta = src.meta
        bounds = src.bounds

We mock this by:
1. Creating a MagicMock that acts as the context manager
2. Setting .read(), .meta, .bounds, .crs on the mock dataset
3. Patching "wildlife_water_stress_atlas.ingest.water.rasterio.open"
   so the patch intercepts the call where it actually happens
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

# Full module path for patching rasterio.open where it's used in water.py
RASTERIO_OPEN = "wildlife_water_stress_atlas.ingest.water.rasterio.open"

# ---------------------------------------------------------------------------
# Raster mock helpers
# ---------------------------------------------------------------------------

def make_raster_mock(data: np.ndarray, crs_epsg: int = 4326) -> MagicMock:
    """
    Build a MagicMock that simulates a rasterio dataset context manager.

    A rasterio dataset is used as:
        with rasterio.open("path.tif") as src:
            array = src.read(1)      # read band 1
            meta  = src.meta         # dict of metadata
            bounds = src.bounds      # BoundingBox(left, bottom, right, top)
            crs   = src.crs          # CRS object

    This helper creates a mock that satisfies all of those access patterns.

    Args:
        data      : 2D numpy array of pixel values to return from src.read(1)
        crs_epsg  : EPSG code for the mock CRS (default 4326)

    Returns:
        MagicMock configured to behave like a rasterio dataset context manager
    """
    # The transform defines how pixel coordinates map to geographic coordinates.
    # We use a simple 1-degree-per-pixel transform starting at (0, 2) —
    # good enough for unit tests, not meant to be geographically meaningful.
    transform = Affine(1.0, 0.0, 0.0, 0.0, -1.0, 2.0)

    # Build the mock dataset
    mock_dataset = MagicMock()
    mock_dataset.read.return_value = data
    mock_dataset.meta = {
        "crs":       CRS.from_epsg(crs_epsg),
        "transform": transform,
        "dtype":     data.dtype.name,
        "width":     data.shape[1],
        "height":    data.shape[0],
    }
    mock_dataset.crs   = CRS.from_epsg(crs_epsg)
    mock_dataset.transform = transform

    # rasterio.bounds returns a BoundingBox namedtuple.
    # Our 2x2 pixel array with 1-degree pixels starting at (0,2) covers (0,0,2,2)
    mock_dataset.bounds = rasterio.coords.BoundingBox(
        left=0.0, bottom=0.0, right=2.0, top=2.0
    )

    # Make the mock work as a context manager:
    # "with rasterio.open(...) as src" needs __enter__ to return the dataset
    # and __exit__ to do nothing (no real file to close)
    mock_context = MagicMock()
    mock_context.__enter__.return_value = mock_dataset
    mock_context.__exit__.return_value = False

    return mock_context


# ---------------------------------------------------------------------------
# GLWD class mapping reference
# Used in tests to verify correct schema values per GLWD class
# ---------------------------------------------------------------------------

GLWD_CLASS_EXPECTATIONS = {
    4: {"water_type": "floodplain", "permanence": "seasonal", "reliability": 0.7, "months_water": 6},
    7: {"water_type": "pan",        "permanence": "seasonal", "reliability": 0.6, "months_water": 4},
    9: {"water_type": "wetland",    "permanence": "seasonal", "reliability": 0.5, "months_water": 3},
}


# ---------------------------------------------------------------------------
# GLWDWetlands — normalized schema
# ---------------------------------------------------------------------------

def test_glwd_produces_normalized_schema():
    # 2x2 raster with class 7 (pan) in all pixels
    data = np.array([[7, 7], [7, 7]], dtype=np.uint8)

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
# GLWDWetlands — water_type per class
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("glwd_class,expected_type", [
    (4, "floodplain"),
    (7, "pan"),
    (9, "wetland"),
])
def test_glwd_sets_correct_water_type_per_class(glwd_class, expected_type):
    # Single pixel raster with the given class value
    data = np.array([[glwd_class, 0], [0, 0]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = GLWDWetlands("dummy/glwd.tif")
        result = source.load()

    assert not result.empty
    assert (result["water_type"] == expected_type).all()


# ---------------------------------------------------------------------------
# GLWDWetlands — mechanism
# ---------------------------------------------------------------------------

def test_glwd_mechanism_is_seasonal_surface():
    data = np.array([[7, 4], [9, 0]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = GLWDWetlands("dummy/glwd.tif")
        result = source.load()

    assert (result["mechanism"] == WaterMechanism.SEASONAL_SURFACE).all()


# ---------------------------------------------------------------------------
# GLWDWetlands — reliability and months_water per class
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("glwd_class,expected_reliability,expected_months", [
    (4, 0.7, 6),
    (7, 0.6, 4),
    (9, 0.5, 3),
])
def test_glwd_reliability_and_months_per_class(glwd_class, expected_reliability, expected_months):
    data = np.array([[glwd_class, 0], [0, 0]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = GLWDWetlands("dummy/glwd.tif")
        result = source.load()

    assert not result.empty
    assert (result["reliability"] == expected_reliability).all()
    assert (result["months_water"] == expected_months).all()


# ---------------------------------------------------------------------------
# GLWDWetlands — class filtering
# ---------------------------------------------------------------------------

def test_glwd_only_includes_pixels_matching_water_classes():
    # Raster with class 4, 7, 9, and 1 (not a wetland class we care about)
    data = np.array([[4, 7], [9, 1]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = GLWDWetlands("dummy/glwd.tif")
        result = source.load()

    # Class 1 should be excluded
    assert set(result["water_type"]).issubset({"floodplain", "pan", "wetland"})


def test_glwd_none_water_classes_uses_defaults():
    # None should default to {4, 7, 9}
    data = np.array([[4, 7], [9, 1]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = GLWDWetlands("dummy/glwd.tif", water_classes=None)
        result = source.load()

    assert set(result["water_type"]) == {"floodplain", "pan", "wetland"}


def test_glwd_empty_water_classes_raises_value_error():
    with pytest.raises(ValueError, match="water_classes"):
        GLWDWetlands("dummy/glwd.tif", water_classes=set())


def test_glwd_unknown_class_value_in_raster_is_ignored():
    # Class 99 doesn't exist in our mapping — should be silently skipped
    data = np.array([[99, 7], [0, 0]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = GLWDWetlands("dummy/glwd.tif")
        result = source.load()

    # Only class 7 (pan) should appear
    assert set(result["water_type"]) == {"pan"}


# ---------------------------------------------------------------------------
# GLWDWetlands — CRS
# ---------------------------------------------------------------------------

def test_glwd_output_is_wgs84():
    data = np.array([[7, 7], [7, 7]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = GLWDWetlands("dummy/glwd.tif")
        result = source.load()

    assert result.crs.to_string() == "EPSG:4326"


# ---------------------------------------------------------------------------
# GLWDWetlands — month parameter
# ---------------------------------------------------------------------------

def test_glwd_month_parameter_does_not_crash():
    # month is not yet implemented for GLWD but should not raise
    data = np.array([[7, 7], [7, 7]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = GLWDWetlands("dummy/glwd.tif", month=8)
        result = source.load()

    assert not result.empty


# ---------------------------------------------------------------------------
# JRCGlobalSurfaceWater — normalized schema
# ---------------------------------------------------------------------------

def test_jrc_produces_normalized_schema():
    # Occurrence values 0-100 — pixels at or above min_occurrence=10 included
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
    # Pixel with value 5 is below default min_occurrence=10 — should be excluded
    data = np.array([[50, 5], [80, 90]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = JRCGlobalSurfaceWater("dummy/jrc.tif", min_occurrence=10)
        result = source.load()

    # Only 3 pixels are at or above threshold
    assert len(result) == 3


def test_jrc_includes_pixels_at_min_occurrence():
    # Pixel exactly at min_occurrence should be included
    data = np.array([[10, 5], [0, 0]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = JRCGlobalSurfaceWater("dummy/jrc.tif", min_occurrence=10)
        result = source.load()

    assert len(result) == 1


def test_jrc_min_occurrence_defaults_to_10():
    # Without specifying min_occurrence, default of 10 should apply
    data = np.array([[9, 10], [11, 0]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = JRCGlobalSurfaceWater("dummy/jrc.tif")
        result = source.load()

    # Only pixels 10 and 11 should be included
    assert len(result) == 2


# ---------------------------------------------------------------------------
# JRCGlobalSurfaceWater — reliability
# ---------------------------------------------------------------------------

def test_jrc_reliability_equals_occurrence_divided_by_100():
    # A pixel with occurrence=80 should have reliability=0.8
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
# JRCGlobalSurfaceWater — month parameter
# ---------------------------------------------------------------------------

def test_jrc_month_parameter_does_not_crash():
    # month is not yet implemented for JRC GSW but should not raise
    data = np.array([[50, 80], [50, 90]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = JRCGlobalSurfaceWater("dummy/jrc.tif", month=3)
        result = source.load()

    assert not result.empty


# ---------------------------------------------------------------------------
# load_all_water — new source types in registry
# ---------------------------------------------------------------------------

def test_load_all_water_accepts_glwd_source_type():
    data = np.array([[7, 7], [7, 7]], dtype=np.uint8)

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
    # Verifies month parameter is accepted without error —
    # full behavioral test deferred until monthly layer is implemented
    data = np.array([[7, 7], [7, 7]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        config = {
            "sources": {
                "glwd": {"path": "dummy/glwd.tif"},
            }
        }
        result = load_all_water(config, bbox=(0, 0, 2, 2), month=8)

    assert isinstance(result, gpd.GeoDataFrame)

# ---------------------------------------------------------------------------
# GLWDWetlands — edge cases
# ---------------------------------------------------------------------------

def test_glwd_skips_class_not_in_class_map():
    # water_classes contains 99 which is not in CLASS_MAP — should be
    # silently skipped, not raise. Only class 7 should appear in output.
    data = np.array([[99, 7], [0, 0]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = GLWDWetlands("dummy/glwd.tif", water_classes={99, 7})
        result = source.load()

    assert set(result["water_type"]) == {"pan"}


def test_glwd_returns_empty_geodataframe_when_no_matching_pixels():
    # All pixels are class 0 — nothing matches water_classes {4, 7, 9}
    data = np.array([[0, 0], [0, 0]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = GLWDWetlands("dummy/glwd.tif")
        result = source.load()

    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 0


def test_glwd_reprojects_when_crs_is_not_wgs84():
    # Simulate a raster that comes back in a non-WGS84 CRS (EPSG:3857)
    data = np.array([[7, 7], [7, 7]], dtype=np.uint8)
    mock = make_raster_mock(data, crs_epsg=3857)

    with patch(RASTERIO_OPEN, return_value=mock):
        source = GLWDWetlands("dummy/glwd.tif")
        result = source.load()

    assert result.crs.to_string() == "EPSG:4326"


# ---------------------------------------------------------------------------
# JRCGlobalSurfaceWater — edge cases
# ---------------------------------------------------------------------------

def test_jrc_returns_empty_geodataframe_when_no_pixels_meet_threshold():
    # All pixels below min_occurrence — nothing should be returned
    data = np.array([[5, 3], [1, 0]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        source = JRCGlobalSurfaceWater("dummy/jrc.tif", min_occurrence=10)
        result = source.load()

    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 0


def test_jrc_reprojects_when_crs_is_not_wgs84():
    data = np.array([[50, 80], [50, 90]], dtype=np.uint8)
    mock = make_raster_mock(data, crs_epsg=3857)

    with patch(RASTERIO_OPEN, return_value=mock):
        source = JRCGlobalSurfaceWater("dummy/jrc.tif")
        result = source.load()

    assert result.crs.to_string() == "EPSG:4326"


# ---------------------------------------------------------------------------
# load_all_water — source-specific config passthrough
# ---------------------------------------------------------------------------

def test_load_all_water_passes_min_occurrence_to_jrc_gsw():
    # Pixels at 50 and 80 — with min_occurrence=60 only the 80 pixel
    # should survive, proving min_occurrence was passed through correctly
    data = np.array([[50, 80], [0, 0]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        config = {
            "sources": {
                "jrc_gsw": {
                    "path": "dummy/jrc.tif",
                    "min_occurrence": 60,
                },
            }
        }
        result = load_all_water(config, bbox=(0, 0, 2, 2))

    assert len(result) == 1
    assert result.iloc[0]["reliability"] == pytest.approx(0.8)


def test_load_all_water_passes_water_classes_to_glwd():
    # Only class 7 in water_classes — class 4 pixels should be excluded
    data = np.array([[4, 7], [4, 7]], dtype=np.uint8)

    with patch(RASTERIO_OPEN, return_value=make_raster_mock(data)):
        config = {
            "sources": {
                "glwd": {
                    "path": "dummy/glwd.tif",
                    "water_classes": {7},
                },
            }
        }
        result = load_all_water(config, bbox=(0, 0, 2, 2))

    assert set(result["water_type"]) == {"pan"}