import json
from collections import Counter
from pathlib import Path

import geopandas as gpd

from wildlife_water_stress_atlas.ingest.gbif import (
    fetch_occurrence_count,
    fetch_occurrences_page,
    occurrences_to_gdf,
)

CACHE_PATH = Path("data/processed/gbif_loxodonta_africana.gpkg")
PARTIAL_PATH = Path("data/processed/gbif_loxodonta_africana_partial.json")
GBIF_PAGE_SIZE = 300
MAX_OFFSET = 21_900  # pre-2001 records cause timeouts — revisit later

if CACHE_PATH.exists():
    print("Loading from cache...")
    gdf = gpd.read_file(CACHE_PATH)
    print(f"Loaded {len(gdf):,} records from cache.")
else:
    total = fetch_occurrence_count("Loxodonta africana")
    print(f"Fetching {total:,} records from GBIF...")
    print(f"Estimated pages: {min(total, MAX_OFFSET) // GBIF_PAGE_SIZE + 1}\n")

    # Resume from partial if it exists
    if PARTIAL_PATH.exists():
        print("Resuming from partial save...")
        with open(PARTIAL_PATH) as f:
            all_records = json.load(f)
        offset = (len(all_records) // GBIF_PAGE_SIZE) * GBIF_PAGE_SIZE
        print(f"Resuming from offset {offset} ({len(all_records):,} records already fetched)\n")
    else:
        all_records = []
        offset = 0

    page_num = offset // GBIF_PAGE_SIZE + 1

    while offset < MAX_OFFSET:
        try:
            records = fetch_occurrences_page(
                "Loxodonta africana",
                limit=GBIF_PAGE_SIZE,
                offset=offset,
            )
        except Exception as e:
            print(f"\n⚠️  Error on page {page_num} (offset {offset}): {e}")
            print(f"Saving {len(all_records):,} records to partial cache...")
            with open(PARTIAL_PATH, "w") as f:
                json.dump(all_records, f)
            print("Partial save complete — re-run to resume.")
            break

        if not records:
            break

        all_records.extend(records)

        years = [r.get("year") for r in records if r.get("year")]
        year_info = f"years {min(years)}–{max(years)}" if years else "no year data"
        print(f"  Page {page_num:3d} | offset {offset:6d} | records {len(all_records):6,}/{total:,} | {year_info}")

        # Save partial every 10 pages in case of timeout
        if page_num % 10 == 0:
            with open(PARTIAL_PATH, "w") as f:
                json.dump(all_records, f)
            print(f"  💾 Partial save at {len(all_records):,} records")

        if len(records) < GBIF_PAGE_SIZE:
            break

        offset += GBIF_PAGE_SIZE
        page_num += 1

    else:
        print(f"\nReached MAX_OFFSET {MAX_OFFSET:,} — stopping (pre-2001 records deferred).")

    if all_records:
        print(f"\nFetched {len(all_records):,} records — converting to GeoDataFrame...")
        gdf = occurrences_to_gdf(all_records)
        print("Saving to cache...")
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        gdf.to_file(CACHE_PATH, driver="GPKG")
        # Clean up partial file
        if PARTIAL_PATH.exists():
            PARTIAL_PATH.unlink()
        print("Cached! ✅")

# Year distribution
year_counts = Counter(gdf["year"].dropna().astype(int).tolist())
print(f"\nTotal records: {len(gdf):,}")
print(f"Year range: {min(year_counts.keys())} – {max(year_counts.keys())}")
print("\nYear distribution (each █ = 10 records):")
for year in sorted(year_counts.keys()):
    bar = "█" * (year_counts[year] // 10)
    print(f"  {year}: {year_counts[year]:4d} {bar}")
