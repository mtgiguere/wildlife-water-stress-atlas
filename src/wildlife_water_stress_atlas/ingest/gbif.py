"""
gbif.py

Fetch species occurrence data from GBIF API.
"""

import geopandas as gpd
import pandas as pd
import requests

GBIF_API_URL = "https://api.gbif.org/v1/occurrence/search"


def fetch_occurrences(scientific_name: str, limit: int = 100) -> list[dict]:
    """
    Fetch occurrence records for a given scientific name from GBIF.

    Args:
        scientific_name: Full scientific name, e.g. "Loxodonta africana".
        limit: Maximum number of records to request.

    Returns:
        A list of occurrence record dictionaries.
    """
    params = {
        "scientificName": scientific_name,
        "limit": limit,
        "hasCoordinate": "true",
    }

    response = requests.get(GBIF_API_URL, params=params, timeout=30)
    response.raise_for_status()

    data = response.json()
    return data.get("results", [])


def occurrences_to_gdf(records: list[dict]) -> gpd.GeoDataFrame:
    """
    Convert GBIF occurrence records into a GeoDataFrame.

    Args:
        records: List of GBIF occurrence record dictionaries.

    Returns:
        GeoDataFrame with WGS84 point geometries.
    """
    df = pd.DataFrame(records)

    df = df.dropna(subset=["decimalLatitude", "decimalLongitude"]).copy()

    geometry = gpd.points_from_xy(df["decimalLongitude"], df["decimalLatitude"])

    return gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")