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

WHY SPLIT INTO THREE FETCH FUNCTIONS:
--------------------------------------
fetch_occurrence_count() and fetch_occurrences_page() are separate so they
can be tested independently without mocking complex pagination logic.
fetch_all_occurrences() orchestrates them — it's the function callers use
in practice, but its logic is simple enough to verify in tests by controlling
what the page function returns.

PAGINATION:
-----------
GBIF returns a maximum of 300 records per request. For species with thousands
of records (African elephants have 10,000+), we must loop with incrementing
offsets until endOfRecords is True. fetch_all_occurrences() handles this loop.

YEAR FIELD:
-----------
The year field from GBIF records is preserved through to the GeoDataFrame.
This is essential for the temporal animation slider — filtering occurrences
by year lets us show how populations have shifted from 1984 to present.
Not all GBIF records have a year — those will have NaN in the year column
and should be handled gracefully by downstream code.

CACHING:
--------
fetch_all_occurrences() can return tens of thousands of records. Callers
should cache the result to data/processed/ rather than fetching on every
run. Streamlit's @st.cache_data decorator handles this elegantly in the
web app layer.
"""

import geopandas as gpd
import pandas as pd
import requests

GBIF_API_URL = "https://api.gbif.org/v1/occurrence/search"

# GBIF hard limit — maximum records returnable in a single request
GBIF_PAGE_SIZE = 300


def fetch_occurrence_count(scientific_name: str) -> int:
    """
    Fetch the total number of occurrence records available for a species.

    Makes a minimal API call (limit=1) to get the count field from GBIF
    without downloading actual records. Use this before fetch_all_occurrences()
    to know how many pages to expect.

    Args:
        scientific_name: Full scientific name, e.g. "Loxodonta africana".

    Returns:
        Total number of records with coordinates available in GBIF.

    Raises:
        requests.HTTPError: If the API returns a non-200 response.
    """
    params = {
        "scientificName": scientific_name,
        "hasCoordinate": "true",
        "limit": 1,  # we only need the count, not actual records
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
    """
    Fetch a single page of occurrence records from GBIF.

    This is the building block for pagination — fetch_all_occurrences()
    calls this repeatedly with incrementing offsets until all records
    are retrieved.

    Args:
        scientific_name: Full scientific name, e.g. "Loxodonta africana".
        limit           : Number of records to request (max 300).
        offset          : Number of records to skip — used for pagination.
                          offset=0 → first page, offset=300 → second page, etc.
        year            : Optional — filter to records from a specific year.
                          When provided, only records with that year are returned.
                          When None, records from all years are returned.

    Returns:
        List of occurrence record dictionaries from GBIF.

    Raises:
        requests.HTTPError: If the API returns a non-200 response.
    """
    params = {
        "scientificName": scientific_name,
        "hasCoordinate": "true",
        "limit": limit,
        "offset": offset,
    }

    # Only add year to params when explicitly provided —
    # omitting it returns all years, which is what we want by default
    if year is not None:
        params["year"] = year

    response = requests.get(GBIF_API_URL, params=params, timeout=30)
    response.raise_for_status()

    return response.json().get("results", [])


def fetch_all_occurrences(
    scientific_name: str,
    year: int | None = None,
) -> list[dict]:
    """
    Fetch all occurrence records for a species via offset-based pagination.

    GBIF returns a maximum of 300 records per request. This function loops
    with incrementing offsets until endOfRecords is True, collecting all
    pages into a single flat list.

    For species with many records (African elephants have 10,000+), this
    may make dozens of API calls. Results should be cached to disk by the
    caller — see caching note in module docstring.

    Args:
        scientific_name: Full scientific name, e.g. "Loxodonta africana".
        year            : Optional — filter to records from a specific year.
                          Used by the temporal animation slider to fetch
                          one year's worth of occurrences at a time.

    Returns:
        Flat list of all occurrence record dictionaries. Empty list if no
        records exist for the given species/year combination.

    Raises:
        requests.HTTPError: If any API call returns a non-200 response.
    """
    # Check total count first — if zero, return immediately without
    # making unnecessary pagination calls
    total = fetch_occurrence_count(scientific_name)
    if total == 0:
        return []

    all_records = []
    offset = 0

    while True:
        page = fetch_occurrences_page(
            scientific_name,
            limit=GBIF_PAGE_SIZE,
            offset=offset,
            year=year,
        )

        all_records.extend(page)

        # GBIF signals end of results via endOfRecords flag.
        # We also stop if the page came back empty — defensive guard
        # against infinite loops if endOfRecords is missing.
        if not page:
            break

        # Check endOfRecords by making one more call to get the flag —
        # fetch_occurrences_page only returns results, not metadata.
        # Instead, we infer end of records from page size: if we got
        # fewer records than we asked for, we're on the last page.
        if len(page) < GBIF_PAGE_SIZE:
            break

        offset += GBIF_PAGE_SIZE

    return all_records


def occurrences_to_gdf(records: list[dict]) -> gpd.GeoDataFrame:
    """
    Convert GBIF occurrence records into a GeoDataFrame.

    Preserves all fields from the original records, including year —
    which is essential for the temporal animation slider. Records missing
    coordinates are dropped. Records missing year will have NaN in that
    column — downstream code should handle this gracefully.

    Args:
        records: List of GBIF occurrence record dictionaries.

    Returns:
        GeoDataFrame with WGS84 point geometries and all original fields
        preserved, including year where available.
    """
    df = pd.DataFrame(records)

    # Drop records without coordinates — they can't be mapped
    df = df.dropna(subset=["decimalLatitude", "decimalLongitude"]).copy()

    geometry = gpd.points_from_xy(df["decimalLongitude"], df["decimalLatitude"])

    return gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
