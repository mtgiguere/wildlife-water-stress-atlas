"""
gbif.py

Fetch species occurrence data from GBIF API.

FUNCTIONS:
----------
fetch_occurrence_count(scientific_name, continent=None)
    → int: total number of records available for a species

fetch_occurrences_page(scientific_name, limit, offset, year=None, continent=None)
    → list[dict]: single page of occurrence records

fetch_all_occurrences(scientific_name, year=None, continent=None)
    → list[dict]: all records across all pages via offset pagination

occurrences_to_gdf(records)
    → GeoDataFrame: converts records to WGS84 points, preserves year field

CONTINENT FILTER:
-----------------
The atlas scores occurrences against Africa-only water/road/settlement layers,
so a global result set is actively harmful: an out-of-extent record gets a
distance measured to a layer that does not cover it. Passing
continent="AFRICA" restricts the query at the source, which also keeps
wide-ranging species (e.g. Phoenicopterus roseus, ~554k records globally)
under GBIF's offset cap. See GBIF_MAX_OFFSET.
"""

import geopandas as gpd
import pandas as pd
import requests

GBIF_API_URL = "https://api.gbif.org/v1/occurrence/search"
GBIF_PAGE_SIZE = 300

# The per-occurrence identity/temporal columns every export carries through to
# the map layer. ONE definition on purpose: five export scripts previously kept
# their own hardcoded lists, which is how `month` was silently dropped despite
# being present on ~all GBIF records and in every cached GeoPackage — the same
# way `name` went missing from settlements at three independent prune sites.
#
# `month` is the key the seasonal-water work needs: water availability swings
# hard within a year, so a dry-season record scored against an annual water
# layer understates precisely the stress this atlas measures.
OCCURRENCE_COLS = ("species", "year", "month")

# GBIF's occurrence search refuses offsets at or beyond this value, so a plain
# offset walk can never retrieve more than this many records for one query.
GBIF_MAX_OFFSET = 100_000


class GBIFTruncationError(RuntimeError):
    """A query returns more records than offset paging can reach.

    Raised instead of returning a partial set. A truncated fetch is
    indistinguishable downstream from a complete one — the cached
    Phoenicopterus roseus layer sat at 99,900 of 554,418 records (18%, in
    GBIF's own ordering rather than a random sample) and presented itself as a
    whole species. The remedy is always to narrow the query, never to retry.
    """


def build_search_params(
    scientific_name: str,
    limit: int,
    offset: int | None = None,
    year: int | None = None,
    continent: str | None = None,
) -> dict:
    """Build one GBIF occurrence-search query.

    The single definition of what an atlas GBIF query means. `prefetch_gbif.py`
    keeps its own paging loop (it checkpoints per page) but MUST build its
    queries here — two hand-maintained param dicts are the field-drift bug
    class in docs/TDD_CONTRACT.md.
    """
    params: dict = {
        "scientificName": scientific_name,
        "hasCoordinate": "true",
        "limit": limit,
    }
    if offset is not None:
        params["offset"] = offset
    if year is not None:
        params["year"] = year
    if continent is not None:
        params["continent"] = continent
    return params


def raise_if_unpageable(scientific_name: str, total: int) -> None:
    """Fail a query that offset paging cannot finish, before fetching anything.

    Shared by the library fetch and the checkpointing prefetch loop so both
    refuse truncation on the same terms.
    """
    if total <= GBIF_MAX_OFFSET:
        return
    raise GBIFTruncationError(
        f"{scientific_name}: {total:,} records exceeds GBIF's {GBIF_MAX_OFFSET:,} offset cap, "
        f"so paging would silently return only the first {GBIF_MAX_OFFSET:,} in GBIF's ordering. "
        f"Narrow the query (continent, country or year) until it fits."
    )


def fetch_occurrence_count(scientific_name: str, continent: str | None = None) -> int:
    params = build_search_params(scientific_name, limit=1, continent=continent)
    response = requests.get(GBIF_API_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json().get("count", 0)


def fetch_occurrences_page(
    scientific_name: str,
    limit: int,
    offset: int,
    year: int | None = None,
    continent: str | None = None,
) -> list[dict]:
    params = build_search_params(scientific_name, limit=limit, offset=offset, year=year, continent=continent)
    response = requests.get(GBIF_API_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json().get("results", [])


def fetch_all_occurrences(
    scientific_name: str,
    year: int | None = None,
    continent: str | None = None,
) -> list[dict]:
    total = fetch_occurrence_count(scientific_name, continent=continent)
    if total == 0:
        return []
    raise_if_unpageable(scientific_name, total)

    all_records = []
    offset = 0

    while True:
        params = build_search_params(scientific_name, limit=GBIF_PAGE_SIZE, offset=offset, year=year, continent=continent)

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
