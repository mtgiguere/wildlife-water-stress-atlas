"""
prefetch_gbif.py

One-time bulk prefetch script for GBIF occurrence data.

WHY THIS EXISTS:
----------------
The Streamlit app fetches GBIF data on first load per species, which
can take several minutes per species. This script pre-populates the
cache for ALL species in SPECIES_CONFIG in one shot, so the app loads
instantly for every species from day one.

Run this script once after adding new species to SPECIES_CONFIG, or
when deploying to a new environment.

HOW TO RUN:
-----------
    python scripts/prefetch_gbif.py

Output files go to data/processed/ as GeoPackage files, named per
each species' gbif_cache_file field in SPECIES_CONFIG.

NOTES:
------
- Each species may take several minutes depending on record count
- Script skips species whose cache file already exists
- Use --force flag to re-fetch all species regardless of cache
- Use --resume flag to continue interrupted fetches from checkpoint
- GBIF rate limits are gentle — no throttling needed for this volume
- Checkpoints are written after every page — timeouts can be resumed
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

# Add repo root to path so src/ and config/ are importable
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG
from wildlife_water_stress_atlas.ingest.gbif import (
    GBIFTruncationError,
    build_search_params,
    occurrences_to_gdf,
    raise_if_unpageable,
)

GBIF_API_URL = "https://api.gbif.org/v1/occurrence/search"
GBIF_PAGE_SIZE = 300

# The atlas scores against Africa-only water/road/settlement layers, so a
# global result set is not merely wasteful — an out-of-extent occurrence gets a
# distance measured to a layer that does not cover it. Filtering here also
# keeps wide-ranging species under GBIF's 100k offset cap.
TARGET_CONTINENT = "AFRICA"

CACHE_DIR = Path("data/processed")

REQUEST_TIMEOUT = 60


def checkpoint_path(cache_path: Path) -> Path:
    return cache_path.with_suffix(".checkpoint.json")


def load_checkpoint(cache_path: Path) -> tuple[int, list[dict]]:
    cp = checkpoint_path(cache_path)
    if not cp.exists():
        return 0, []
    data = json.loads(cp.read_text())
    print(f"   ♻️  Resuming from checkpoint — offset {data['offset']:,}, {len(data['records']):,} records already fetched")
    return data["offset"], data["records"]


def save_checkpoint(cache_path: Path, offset: int, records: list[dict]) -> None:
    cp = checkpoint_path(cache_path)
    cp.write_text(json.dumps({"offset": offset, "records": records}))


def delete_checkpoint(cache_path: Path) -> None:
    cp = checkpoint_path(cache_path)
    if cp.exists():
        cp.unlink()


def fetch_all_with_checkpoint(scientific_name: str, cache_path: Path, continent: str | None = TARGET_CONTINENT) -> list[dict]:
    offset, all_records = load_checkpoint(cache_path)

    while True:
        params = build_search_params(
            scientific_name,
            limit=GBIF_PAGE_SIZE,
            offset=offset,
            continent=continent,
        )

        try:
            response = requests.get(GBIF_API_URL, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
        except requests.Timeout:
            save_checkpoint(cache_path, offset, all_records)
            raise

        total = data.get("count", "?")
        if isinstance(total, int):
            # Before accumulating anything: a query bigger than the offset cap
            # can only ever yield its first GBIF_MAX_OFFSET records, and this
            # loop would otherwise walk to the wall and stop as if finished.
            raise_if_unpageable(scientific_name, total)

        page = data.get("results", [])
        all_records.extend(page)

        print(f"   📄 offset={offset:>6,}  page={len(page):>3}  total so far={len(all_records):>6,}  of ~{total:,}")

        save_checkpoint(cache_path, offset + GBIF_PAGE_SIZE, all_records)

        if data.get("endOfRecords", True):
            break
        if not page:
            break

        offset += GBIF_PAGE_SIZE

    delete_checkpoint(cache_path)
    return all_records


def prefetch_species(scientific_name: str, force: bool = False) -> None:
    cfg = SPECIES_CONFIG[scientific_name]
    common_name = cfg["common_name"]
    emoji = cfg["emoji"]
    cache_path = CACHE_DIR / cfg["gbif_cache_file"]
    cp = checkpoint_path(cache_path)

    print(f"\n{emoji} {common_name} ({scientific_name})")
    print(f"   Cache path: {cache_path}")

    if cache_path.exists() and not force and not cp.exists():
        print("   ✅ Already cached — skipping. Use --force to re-fetch.")
        return

    if force and cache_path.exists():
        cache_path.unlink()
        delete_checkpoint(cache_path)
        print("   🗑️  Cleared existing cache (--force)")

    print("   ⏳ Fetching from GBIF...")
    start = time.time()

    try:
        records = fetch_all_with_checkpoint(scientific_name, cache_path)

        if not records:
            print(f"   ⚠️  No records found for {scientific_name}")
            return

        gdf = occurrences_to_gdf(records)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        gdf.to_file(cache_path, driver="GPKG")

        elapsed = time.time() - start
        print(f"   ✅ {len(gdf):,} records cached in {elapsed:.1f}s → {cache_path}")

    except requests.Timeout:
        print("   ⏱️  Timed out — checkpoint saved. Re-run to resume from where it stopped.")
    except GBIFTruncationError:
        # Deliberately NOT swallowed like other errors. A truncated species is
        # not a per-species hiccup to log and move past — it means the query
        # itself is wrong, and continuing would build a cache whose gaps are
        # invisible downstream.
        delete_checkpoint(cache_path)
        raise
    except Exception as e:
        print(f"   ❌ Failed: {e}")


def finalize_from_checkpoint(scientific_name: str) -> None:
    """
    Write a GeoPackage from an existing checkpoint file without fetching
    any more pages.

    ⚠️ This is a RESUME-AFTER-INTERRUPTION tool (a timeout, a killed run) —
    NOT a way around the offset cap. Using it for that is how the flamingo
    cache came to hold 99,900 of 554,418 records while looking complete. If a
    query is too big to page, narrow it (see TARGET_CONTINENT) and re-fetch;
    the resulting file is a real species layer rather than a prefix of one.
    """
    cfg = SPECIES_CONFIG[scientific_name]
    emoji = cfg["emoji"]
    common_name = cfg["common_name"]
    cache_path = CACHE_DIR / cfg["gbif_cache_file"]
    cp = checkpoint_path(cache_path)

    print(f"\n{emoji} {common_name} ({scientific_name})")

    if not cp.exists():
        print("   ❌ No checkpoint file found — nothing to finalize.")
        return

    data = json.loads(cp.read_text())
    records = data["records"]
    print(f"   📦 Finalizing {len(records):,} records from checkpoint...")

    gdf = occurrences_to_gdf(records)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    gdf.to_file(cache_path, driver="GPKG")
    delete_checkpoint(cache_path)

    print(f"   ✅ {len(gdf):,} records saved → {cache_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Pre-fetch GBIF occurrence data for all species in SPECIES_CONFIG.")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--species", type=str, default=None)
    parser.add_argument(
        "--finalize",
        action="store_true",
        help="Write gpkg from existing checkpoint without fetching more pages.",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Wildlife Water Stress Atlas — GBIF Bulk Prefetch")
    print("=" * 60)

    if args.finalize:
        if not args.species:
            print("❌ --finalize requires --species")
            sys.exit(1)
        finalize_from_checkpoint(args.species)
        return

    if args.species:
        if args.species not in SPECIES_CONFIG:
            print(f"❌ Unknown species: {args.species}")
            print(f"   Available: {list(SPECIES_CONFIG.keys())}")
            sys.exit(1)
        prefetch_species(args.species, force=args.force)
    else:
        print(f"Fetching {len(SPECIES_CONFIG)} species...")
        for scientific_name in SPECIES_CONFIG.keys():
            prefetch_species(scientific_name, force=args.force)

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
