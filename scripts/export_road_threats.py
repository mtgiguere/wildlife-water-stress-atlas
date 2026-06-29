"""
export_road_threats.py

Computes road threat scores for all species from OSM road data and exports
enriched GeoJSON for the Mapbox app.

USAGE:
------
    python scripts/export_road_threats.py

    Requires an OSM roads GeoPackage at data/raw/threats/africa_roads.gpkg.
    See docs/ for how to obtain this from Geofabrik or overpass-turbo.

OUTPUT:
-------
    apps/mapbox/data/road_threats_gbif_{species}.geojson
    Format: GeoJSON FeatureCollection with road_threat_score (0-1),
            road_class, and distance_to_road_m properties per occurrence.

ARCHITECTURE NOTE:
------------------
Roads are loaded once, then reused across all species — the road network
is species-independent. Each species gets its own score via road_threat_score()
which applies species-specific sensitivity and class weights from SPECIES_CONFIG.

This script is part of the static pre-computation pipeline.
When OSM data updates, re-run this script to refresh the GeoJSON.
"""

from pathlib import Path

import geopandas as gpd

from wildlife_water_stress_atlas.analytics.apply import apply_road_threat_score
from wildlife_water_stress_atlas.analytics.overlap import add_distance_to_road
from wildlife_water_stress_atlas.analytics.threat_scoring import road_threat_score
from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG
from wildlife_water_stress_atlas.ingest.threats import load_all_threats

# Bounding box covering continental Africa (lon_min, lat_min, lon_max, lat_max)
AFRICA_BBOX = (-20.0, -35.0, 55.0, 38.0)

_OUTPUT_COLS = ["species", "year", "distance_to_road_m", "road_class", "road_threat_score"]


def compute_road_threats(
    occurrences: gpd.GeoDataFrame,
    roads: gpd.GeoDataFrame,
    scientific_name: str,
) -> gpd.GeoDataFrame:
    """
    Compute road threat scores for all occurrences of one species.

    Pure computation — no file I/O. Compose add_distance_to_road and
    apply_road_threat_score over the supplied GeoDataFrames.

    Args:
        occurrences    : GeoDataFrame of GBIF occurrence points.
        roads          : Normalized roads GeoDataFrame from OSMRoads.load().
        scientific_name: Species scientific name (must be in SPECIES_CONFIG).

    Returns:
        GeoDataFrame with distance_to_road_m, road_class, and
        road_threat_score columns added.
    """
    with_distances = add_distance_to_road(occurrences, roads)
    return apply_road_threat_score(with_distances, road_threat_score)


def export_road_threat(
    occurrences_path: Path,
    roads_path: Path,
    output_path: Path,
    scientific_name: str,
    roads: gpd.GeoDataFrame | None = None,
) -> None:
    """
    Compute and export road threat GeoJSON for one species.

    Args:
        occurrences_path : Path to the GBIF cache GeoPackage.
        roads_path       : Path to the OSM roads GeoPackage (used only if
                           roads is not provided).
        output_path      : Path to write the output GeoJSON.
        scientific_name  : Species scientific name.
        roads            : Pre-loaded roads GDF. If provided, roads_path is
                           ignored — this avoids reloading roads for each
                           species in export_all_road_threats().
    """
    occurrences = gpd.read_file(occurrences_path)

    if roads is None:
        roads = load_all_threats(
            {"sources": {"osm_roads": {"path": str(roads_path)}}},
            bbox=AFRICA_BBOX,
        )

    gdf = compute_road_threats(occurrences, roads, scientific_name)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cols = [c for c in _OUTPUT_COLS if c in gdf.columns]
    gdf[cols + ["geometry"]].to_file(output_path, driver="GeoJSON")


def export_all_road_threats(
    data_dir: Path,
    roads_path: Path,
    output_dir: Path,
) -> None:
    """
    Compute and export road threat GeoJSON for every species in SPECIES_CONFIG.

    Roads are loaded once and reused across all species.

    Args:
        data_dir   : Directory containing GBIF cache GeoPackages.
        roads_path : Path to the OSM roads GeoPackage.
        output_dir : Directory to write output GeoJSON files.
    """
    roads = load_all_threats(
        {"sources": {"osm_roads": {"path": str(roads_path)}}},
        bbox=AFRICA_BBOX,
    )

    for scientific_name, cfg in SPECIES_CONFIG.items():
        slug = scientific_name.lower().replace(" ", "_")
        occurrences_path = data_dir / cfg["gbif_cache_file"]
        output_path = output_dir / f"road_threats_gbif_{slug}.geojson"

        try:
            export_road_threat(
                occurrences_path=occurrences_path,
                roads_path=roads_path,
                output_path=output_path,
                scientific_name=scientific_name,
                roads=roads,
            )
            print(f"  → road_threats_gbif_{slug}.geojson")
        except Exception as e:
            print(f"  ERROR — {scientific_name}: {e}")


def main() -> None:
    export_all_road_threats(
        data_dir=Path("data/processed"),
        roads_path=Path("data/raw/threats/africa_roads.gpkg"),
        output_dir=Path("apps/mapbox/data"),
    )


if __name__ == "__main__":  # pragma: no cover
    main()
