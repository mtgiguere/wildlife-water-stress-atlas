"""
gbif.py

Fetch species occurrence data from GBIF API.

FUNCTIONS:
----------
fetch_occurrence_count(scientific_name)
    → int: total number of records available for a species

fetch_occurrences_page(scientific_name, limit, offset, year=None)
    → list[dict]: single page of occurrence records

fetch_all_occurrences(scientific_name, year=None)
    → list[dict]: all records across all pages via offset pagination

occurrences_to_gdf(records)
    → GeoDataFrame: converts records to WGS84 points, preserves year field
"""

import geopandas as gpd
import pandas as pd
import requests

GBIF_API_URL = "https://api.gbif.org/v1/occurrence/search"
GBIF_PAGE_SIZE = 300


def fetch_occurrence_count(scientific_name: str) -> int:
    params = {
        "scientificName": scientific_name,
        "hasCoordinate": "true",
        "limit": 1,
    }
    response = requests.get(GBIF_API_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json().get("count", 0)


def fetch_occurrences_page(
    scientific_name: str,
    limit: int,
    offset: int,
    year: int | None = None,
) -> list[dict]:
    params = {
        "scientificName": scientific_name,
        "hasCoordinate": "true",
        "limit": limit,
        "offset": offset,
    }
    if year is not None:
        params["year"] = year

    response = requests.get(GBIF_API_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json().get("results", [])


def fetch_all_occurrences(
    scientific_name: str,
    year: int | None = None,
) -> list[dict]:
    total = fetch_occurrence_count(scientific_name)
    if total == 0:
        return []

    all_records = []
    offset = 0

    while True:
        params = {
            "scientificName": scientific_name,
            "hasCoordinate": "true",
            "limit": GBIF_PAGE_SIZE,
            "offset": offset,
        }
        if year is not None:
            params["year"] = year

        response = requests.get(GBIF_API_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        page = data.get("results", [])
        all_records.extend(page)

        if data.get("endOfRecords", True):
            break
        if not page:
            break

        offset += GBIF_PAGE_SIZE

    return all_records


def occurrences_to_gdf(records: list[dict]) -> gpd.GeoDataFrame:
    df = pd.DataFrame(records)
    df = df.dropna(subset=["decimalLatitude", "decimalLongitude"]).copy()
    geometry = gpd.points_from_xy(df["decimalLongitude"], df["decimalLatitude"])
    return gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
