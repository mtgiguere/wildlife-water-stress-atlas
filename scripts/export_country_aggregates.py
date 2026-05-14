"""
export_country_aggregates.py

Spatial join of species occurrences to Natural Earth country boundaries.
Aggregates record counts by country + year for choropleth visualization.

USAGE:
------
    python scripts/export_country_aggregates.py

OUTPUT:
-------
    apps/mapbox/data/country_counts_gbif_{species}.geojson
    Format: [{NAME, ISO_A3, year, count}, ...]

TODO Phase 2 — Live Data:
    When GBIF data is updated on a schedule, wrap this script in a
    GitHub Actions workflow (e.g. nightly cron job) to auto-regenerate
    and commit updated GeoJSON. Frontend requires zero changes.
"""

import geopandas as gpd
from wildlife_water_stress_atlas.analytics.trends import add_trends_to_country_counts
from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG

COUNTRY_COLS = ["NAME", "ISO_A3", "CONTINENT"]


def load_countries(path):
    gdf = gpd.read_file(path)
    return gdf[COUNTRY_COLS + ["geometry"]]


def join_occurrences_to_countries(occurrences, countries):
    return gpd.sjoin(occurrences, countries, how="left", predicate="within")


def aggregate_by_country_year(joined):
    result = joined.dropna(subset=["NAME"])
    if "CONTINENT" in result.columns:
        result = result[result["CONTINENT"] == "Africa"]
    return result.groupby(["NAME", "ISO_A3", "year"]).size().reset_index(name="count")


def export_country_counts(scientific_name, data_dir, output_dir, countries_path):
    cfg = SPECIES_CONFIG[scientific_name]
    occurrences = gpd.read_file(data_dir / cfg["gbif_cache_file"])
    countries   = load_countries(countries_path)
    joined      = join_occurrences_to_countries(occurrences, countries)
    counts      = aggregate_by_country_year(joined)
    counts_with_trends = add_trends_to_country_counts(counts.to_dict("records"))

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"country_counts_{cfg['gbif_cache_file'].replace('.gpkg', '.geojson')}"

    import json
    output_file.write_text(json.dumps(counts_with_trends))


def export_all_country_counts(data_dir, output_dir, countries_path):
    for scientific_name in SPECIES_CONFIG:
        export_country_counts(scientific_name, data_dir, output_dir, countries_path)
