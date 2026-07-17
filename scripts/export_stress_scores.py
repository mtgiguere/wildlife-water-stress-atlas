"""
export_stress_scores.py

Computes water stress scores for all species using PostGIS KNN nearest-neighbor
queries and exports enriched GeoJSON for the Mapbox app.

Replaces the slow in-memory GeoPandas nearest-neighbor approach with
PostGIS GIST-indexed spatial queries — 21,900 elephants in ~2.5 seconds
vs potentially hours with the old approach.

USAGE:
------
    python scripts/export_stress_scores.py

OUTPUT:
-------
    apps/mapbox/data/stress_scores_gbif_{species}.geojson
    Format: GeoJSON FeatureCollection with stress_score (0-1) and
            stress_level (low/moderate/high) properties per occurrence.

ARCHITECTURE NOTE:
------------------
This script is part of the static pre-computation pipeline.
Stress scores are computed once and baked into GeoJSON — the frontend
reads pre-computed fields directly. No runtime database queries.
When GBIF data updates, re-run this script.

TODO Phase 2: Wrap in GitHub Actions cron job for automated updates.
"""

import os
from pathlib import Path

import geopandas as gpd
from sqlalchemy import create_engine

from wildlife_water_stress_atlas.analytics.scoring import classify_stress_level
from wildlife_water_stress_atlas.analytics.stress_engine import score_stressor
from wildlife_water_stress_atlas.analytics.stressors import FeatureProximity
from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG
from wildlife_water_stress_atlas.utils.generic_threader import GenericThreader

DB_URL = os.environ.get(
    "WILDLIFE_ATLAS_DB_URL",
    "postgresql://postgres:atlas123@127.0.0.1:5433/wildlife_atlas",
)

KNN_QUERY = """
    SELECT
        o.species,
        o.year,
        o.geometry,
        ST_Distance(
            o.geometry::geography,
            w.geometry::geography
        ) AS distance_m
    FROM {table} o
    CROSS JOIN LATERAL (
        SELECT geometry
        FROM water_sources
        ORDER BY o.geometry <-> geometry
        LIMIT 1
    ) w
"""


def compute_stress_scores(engine, scientific_name: str) -> gpd.GeoDataFrame:
    """
    Run KNN nearest-neighbor query for one species and compute stress scores.

    Uses PostGIS GIST index for fast spatial lookup — orders of magnitude
    faster than in-memory GeoPandas nearest-neighbor.

    Args:
        engine: SQLAlchemy engine connected to PostGIS
        scientific_name: Species scientific name (must be in SPECIES_CONFIG)

    Returns:
        GeoDataFrame with distance_m, stress_score, stress_level columns added
    """
    table = f"occurrences_{scientific_name.lower().replace(' ', '_')}"
    query = KNN_QUERY.format(table=table)

    gdf = gpd.read_postgis(query, engine, geom_col="geometry")

    gdf["stress_score"] = gdf["distance_m"].apply(lambda d: score_stressor(scientific_name, "water", FeatureProximity(d, None)))
    gdf["stress_level"] = gdf["stress_score"].apply(classify_stress_level)

    return gdf


def export_stress_scores(engine, scientific_name: str, output_path: Path) -> None:
    """
    Compute stress scores for one species and write enriched GeoJSON.

    Args:
        engine: SQLAlchemy engine connected to PostGIS
        scientific_name: Species scientific name
        output_path: Path to write the output GeoJSON file
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    gdf = compute_stress_scores(engine, scientific_name)

    cols = [c for c in ["species", "year", "distance_m", "stress_score", "stress_level"] if c in gdf.columns]
    gdf[cols + ["geometry"]].to_file(output_path, driver="GeoJSON")


def export_all_stress_scores(engine, output_dir: Path) -> None:
    """
    Compute and export stress scores for all species in SPECIES_CONFIG.
    Uses GenericThreader to fan out PostGIS queries in parallel —
    all 11 species run simultaneously since queries are I/O-bound.

    Args:
        engine: SQLAlchemy engine connected to PostGIS
        output_dir: Directory to write output GeoJSON files
    """
    # Build one job per species — (function, args, kwargs)
    jobs = []
    for scientific_name in SPECIES_CONFIG:
        slug = scientific_name.lower().replace(" ", "_")
        output_path = output_dir / f"stress_scores_gbif_{slug}.geojson"
        jobs.append((export_stress_scores, [engine, scientific_name, output_path], {}))

    # Fire all species queries in parallel — PostGIS handles concurrent connections
    threader = GenericThreader(jobs)
    results = threader.run()

    # Report results — surface any per-species errors without failing the whole run
    for scientific_name, result in zip(SPECIES_CONFIG.keys(), results, strict=False):
        if isinstance(result, Exception):
            print(f"  ERROR — {scientific_name}: {result}")
        else:
            slug = scientific_name.lower().replace(" ", "_")
            print(f"  → stress_scores_gbif_{slug}.geojson")


def main():
    engine = create_engine(DB_URL)
    export_all_stress_scores(
        engine=engine,
        output_dir=Path("apps/mapbox/data"),
    )


if __name__ == "__main__":  # pragma: no cover
    main()
