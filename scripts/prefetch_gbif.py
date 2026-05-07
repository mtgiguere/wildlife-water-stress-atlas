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
- GBIF rate limits are gentle — no throttling needed for this volume
"""

import argparse
import sys
import time
from pathlib import Path

# Add repo root to path so src/ and config/ are importable
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG
from wildlife_water_stress_atlas.ingest.gbif import fetch_all_occurrences, occurrences_to_gdf

CACHE_DIR = Path("data/processed")


def prefetch_species(scientific_name: str, force: bool = False) -> None:
    """
    Fetch and cache GBIF occurrences for a single species.

    Args:
        scientific_name : Must be a key in SPECIES_CONFIG.
        force           : If True, re-fetch even if cache exists.
    """
    cfg = SPECIES_CONFIG[scientific_name]
    common_name = cfg["common_name"]
    emoji = cfg["emoji"]
    cache_path = CACHE_DIR / cfg["gbif_cache_file"]

    print(f"\n{emoji} {common_name} ({scientific_name})")
    print(f"   Cache path: {cache_path}")

    if cache_path.exists() and not force:
        print("   ✅ Already cached — skipping. Use --force to re-fetch.")
        return

    print("   ⏳ Fetching from GBIF...")
    start = time.time()

    try:
        records = fetch_all_occurrences(scientific_name)

        if not records:
            print(f"   ⚠️  No records found for {scientific_name}")
            return

        gdf = occurrences_to_gdf(records)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        gdf.to_file(cache_path, driver="GPKG")

        elapsed = time.time() - start
        print(f"   ✅ {len(gdf):,} records cached in {elapsed:.1f}s → {cache_path}")

    except Exception as e:
        print(f"   ❌ Failed: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Pre-fetch GBIF occurrence data for all species in SPECIES_CONFIG.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch all species even if cache files already exist.",
    )
    parser.add_argument(
        "--species",
        type=str,
        default=None,
        help="Fetch a single species by scientific name. Fetches all if omitted.",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Wildlife Water Stress Atlas — GBIF Bulk Prefetch")
    print("=" * 60)

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
