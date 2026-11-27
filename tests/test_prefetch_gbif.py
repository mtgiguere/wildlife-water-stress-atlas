"""
test_prefetch_gbif.py

Tests for scripts/prefetch_gbif.py — the bulk GBIF cache builder.

WHY THIS FILE EXISTS:
---------------------
`prefetch_gbif.py` does NOT call `ingest.gbif.fetch_all_occurrences`; it carries
its own copy of the paging loop so it can checkpoint after every page. That
duplication is exactly the field-drift bug class documented in
docs/TDD_CONTRACT.md (Bug #1, and the settlement-names bug where three
independent sites each kept their own hardcoded column list).

The cache this script writes is what every downstream layer is actually built
from, so a query parameter that exists in `gbif.py` but is missing here is
silently inert. These tests pin the two seams together.
"""

import json

import pytest

from scripts.prefetch_gbif import TARGET_CONTINENT, build_search_params, fetch_all_with_checkpoint

PREFETCH_REQUESTS_GET = "scripts.prefetch_gbif.requests.get"


def make_gbif_response(results, count=None, end_of_records=True):
    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "endOfRecords": end_of_records,
                "count": count if count is not None else len(results),
                "results": results,
            }

    return _Resp()


def sample_records(n):
    return [
        {
            "decimalLatitude": -1.95 + i * 0.1,
            "decimalLongitude": 37.15 + i * 0.1,
            "species": "Loxodonta africana",
            "year": 2015,
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# The continent filter reaches the actual cache-building fetch
# ---------------------------------------------------------------------------


def test_prefetch_sends_continent_filter_to_gbif(monkeypatch, tmp_path):
    """Specifies: the script that BUILDS THE CACHE restricts to Africa.

    Adding the parameter to ingest/gbif.py alone would be inert — nothing in
    the cache pipeline goes through that module.
    """
    captured = {}

    def mock_get(url, params=None, timeout=None):
        captured.update(params or {})
        return make_gbif_response(sample_records(5))

    monkeypatch.setattr(PREFETCH_REQUESTS_GET, mock_get)

    fetch_all_with_checkpoint("Loxodonta africana", tmp_path / "cache.gpkg")

    assert captured.get("continent") == "AFRICA"


def test_prefetch_sends_continent_on_every_page(monkeypatch, tmp_path):
    """A filter dropped after page 1 would readmit the global records this
    change exists to exclude."""
    seen_continents = []

    def mock_get(url, params=None, timeout=None):
        seen_continents.append((params or {}).get("continent"))
        offset = (params or {}).get("offset", 0)
        return make_gbif_response(sample_records(300), count=600, end_of_records=offset >= 300)

    monkeypatch.setattr(PREFETCH_REQUESTS_GET, mock_get)

    fetch_all_with_checkpoint("Phoenicopterus roseus", tmp_path / "cache.gpkg")

    assert len(seen_continents) == 2, "fixture must exercise more than one page"
    assert seen_continents == ["AFRICA", "AFRICA"]


def test_prefetch_continent_survives_a_checkpoint_resume(monkeypatch, tmp_path):
    """Resuming mid-fetch must not silently drop the filter — a resumed cache
    would otherwise blend filtered and unfiltered records."""
    cache_path = tmp_path / "cache.gpkg"
    checkpoint = cache_path.with_suffix(".checkpoint.json")
    checkpoint.write_text(json.dumps({"offset": 300, "records": sample_records(300)}))

    seen_continents = []

    def mock_get(url, params=None, timeout=None):
        seen_continents.append((params or {}).get("continent"))
        return make_gbif_response(sample_records(10), count=310)

    monkeypatch.setattr(PREFETCH_REQUESTS_GET, mock_get)

    fetch_all_with_checkpoint("Phoenicopterus roseus", cache_path)

    assert seen_continents, "resume must still issue at least one request"
    assert all(c == "AFRICA" for c in seen_continents)


# ---------------------------------------------------------------------------
# Cross-seam contract: the two param builders cannot drift apart
# ---------------------------------------------------------------------------


def test_prefetch_and_ingest_build_identical_search_params():
    """THE drift guard. `ingest.gbif` and `prefetch_gbif` each issue GBIF
    queries; if they ever disagree about what a query means, the cache stops
    matching what the library would have fetched. Pin them to one builder."""
    from wildlife_water_stress_atlas.ingest import gbif

    mine = build_search_params("Loxodonta africana", limit=300, offset=600, continent=TARGET_CONTINENT)
    theirs = gbif.build_search_params("Loxodonta africana", limit=300, offset=600, continent=TARGET_CONTINENT)

    assert mine == theirs


def test_prefetch_target_continent_is_africa():
    """The atlas' layers are Africa-only; the cache must agree."""
    assert TARGET_CONTINENT == "AFRICA"


@pytest.mark.parametrize("continent", [None, "AFRICA"])
def test_build_search_params_omits_continent_only_when_none(continent):
    params = build_search_params("Loxodonta africana", limit=300, offset=0, continent=continent)

    if continent is None:
        assert "continent" not in params
    else:
        assert params["continent"] == "AFRICA"


# ---------------------------------------------------------------------------
# The cache builder refuses to write a truncated species layer
# ---------------------------------------------------------------------------


def _oversized_query_mock(page_budget):
    """A GBIF that reports more records than paging can reach.

    Bounded deliberately: without the guard this loop pages forever (that is
    the defect), and an unbounded fixture would hang the suite instead of
    failing it. The budget is far above the 1 page a correct implementation
    needs, so it cannot mask a late-firing guard.
    """
    from wildlife_water_stress_atlas.ingest.gbif import GBIF_MAX_OFFSET

    pages = {"n": 0}

    def mock_get(url, params=None, timeout=None):
        pages["n"] += 1
        return make_gbif_response(
            sample_records(300),
            count=GBIF_MAX_OFFSET + 1,
            end_of_records=pages["n"] >= page_budget,
        )

    return mock_get, pages


def test_prefetch_raises_when_query_exceeds_offset_cap(monkeypatch, tmp_path):
    """Specifies: the loop that actually built the 99,900-record flamingo cache
    now refuses. Returning 18% of a species as a finished layer is the bug."""
    from wildlife_water_stress_atlas.ingest.gbif import GBIFTruncationError

    mock_get, _ = _oversized_query_mock(page_budget=5)
    monkeypatch.setattr(PREFETCH_REQUESTS_GET, mock_get)

    with pytest.raises(GBIFTruncationError):
        fetch_all_with_checkpoint("Phoenicopterus roseus", tmp_path / "cache.gpkg")


def test_prefetch_stops_at_the_first_page_of_an_oversized_query(monkeypatch, tmp_path):
    """Fail fast: the count arrives with page 1, so there is no reason to keep
    paging a query that can never complete."""
    from wildlife_water_stress_atlas.ingest.gbif import GBIFTruncationError

    mock_get, pages = _oversized_query_mock(page_budget=5)
    monkeypatch.setattr(PREFETCH_REQUESTS_GET, mock_get)

    with pytest.raises(GBIFTruncationError):
        fetch_all_with_checkpoint("Phoenicopterus roseus", tmp_path / "cache.gpkg")

    assert pages["n"] == 1


def test_prefetch_does_not_write_a_cache_file_for_a_truncated_query(monkeypatch, tmp_path):
    """The failure must leave no half-species GeoPackage behind for a later run
    to mistake for real data."""
    from scripts.prefetch_gbif import prefetch_species
    from wildlife_water_stress_atlas.ingest.gbif import GBIFTruncationError

    cache_path = tmp_path / "gbif_phoenicopterus_roseus.gpkg"

    mock_get, _ = _oversized_query_mock(page_budget=5)
    monkeypatch.setattr(PREFETCH_REQUESTS_GET, mock_get)
    monkeypatch.setattr("scripts.prefetch_gbif.CACHE_DIR", tmp_path)

    with pytest.raises(GBIFTruncationError):
        prefetch_species("Phoenicopterus roseus")

    assert not cache_path.exists()


def test_prefetch_allows_a_query_that_fits_under_the_cap(monkeypatch, tmp_path):
    """Regression guard: the cap must not disturb an ordinary fetch."""
    from wildlife_water_stress_atlas.ingest.gbif import GBIF_MAX_OFFSET

    def mock_get(url, params=None, timeout=None):
        return make_gbif_response(sample_records(50), count=GBIF_MAX_OFFSET)

    monkeypatch.setattr(PREFETCH_REQUESTS_GET, mock_get)

    records = fetch_all_with_checkpoint("Loxodonta africana", tmp_path / "cache.gpkg")

    assert len(records) == 50
