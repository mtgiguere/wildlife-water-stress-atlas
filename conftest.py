import os
import sys
from pathlib import Path

# PostgreSQL/PostGIS sets PROJ_LIB to its own outdated PROJ database on
# Windows. Override it BEFORE importing rasterio or pyproj so the PROJ DLL
# initializes against the correct database (the one rasterio was compiled with).
# importlib.util.find_spec locates rasterio without importing it, so the PROJ
# DLL has not yet initialized when we set the environment variables.
import importlib.util as _ilu

_rasterio_spec = _ilu.find_spec("rasterio")
if _rasterio_spec and _rasterio_spec.origin:
    _rasterio_proj = str(Path(_rasterio_spec.origin).parent / "proj_data")
    if (Path(_rasterio_proj) / "proj.db").exists():
        os.environ["PROJ_LIB"] = _rasterio_proj
        os.environ["PROJ_DATA"] = _rasterio_proj

# Add project root to path so 'scripts' package is importable in tests
sys.path.insert(0, str(Path(__file__).parent))
