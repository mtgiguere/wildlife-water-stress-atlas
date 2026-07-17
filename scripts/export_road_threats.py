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
is species-independent. Each species gets its own score via the unified scoring
engine (score_stressor(..., "roads", ...)), which applies that species'
roads-stressor sensitivity and class weights from SPECIES_CONFIG.

This script is part of the static pre-computation pipeline.
When OSM data updates, re-run this script to refresh the GeoJSON.
"""

from pathlib import Path

import geopandas as gpd

from wildlife_water_stress_atlas.analytics.apply import apply_road_threat_score
from wildlife_water_stress_atlas.analytics.overlap import add_distance_to_road
from wildlife_water_stress_atlas.analytics.stress_engine import score_stressor
from wildlife_water_stress_atlas.analytics.stressors import FeatureProximity
from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG
from wildlife_water_stress_atlas.ingest.threats import load_all_threats

# Bounding box covering continental Africa (lon_min, lat_min, lon_max, lat_max)
AFRICA_BBOX = (-20.0, -35.0, 55.0, 38.0)

_OUTPUT_COLS = ["species", "year", "distance_to_road_m", "road_class", "road_threat_score"]

# Backbone road network drawn on the map (ROADS view). Only the highest-order
# classes are shown — enough to make a red occurrence legible ("it's next to a
# motorway") without committing the full 400k+ segment network. Geometry is
# simplified for web display; the analytics still score against ALL major roads.
BACKBONE_ROAD_CLASSES = {"motorway", "trunk", "primary"}
ROAD_SIMPLIFY_TOLERANCE_DEG = 0.01  # ~1km at the equator — fine at continental zoom


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
    return apply_road_threat_score(with_distances, _road_threat_score)


def _road_threat_score(distance_m: float, road_class: str, species: str) -> float:
    """Adapter to the unified engine (cutover): the roads-stressor value the
    legacy threat_scoring.road_threat_score used to return."""
    return score_stressor(species, "roads", FeatureProximity(distance_m, road_class))


def build_backbone_roads(
    roads: gpd.GeoDataFrame,
    classes: set = BACKBONE_ROAD_CLASSES,
    tolerance: float = ROAD_SIMPLIFY_TOLERANCE_DEG,
) -> gpd.GeoDataFrame:
    """
    Subset roads to the backbone classes and simplify their geometry.

    Pure transform — no I/O. Used to build a lightweight road-network layer
    for the map without shipping the full segment set.

    Args:
        roads     : Normalized roads GeoDataFrame (must have a road_class column).
        classes   : Road classes to keep. Default BACKBONE_ROAD_CLASSES.
        tolerance : Simplification tolerance in degrees (EPSG:4326).

    Returns:
        GeoDataFrame with road_class + simplified geometry, backbone classes only.
    """
    backbone = roads[roads["road_class"].isin(classes)][["road_class", "geometry"]].copy()
    backbone["geometry"] = backbone.geometry.simplify(tolerance, preserve_topology=False)
    return backbone


def export_backbone_roads(
    roads_path: Path,
    output_path: Path,
    roads: gpd.GeoDataFrame | None = None,
) -> None:
    """
    Export the simplified backbone road network as GeoJSON for the map layer.

    Args:
        roads_path  : Path to the OSM roads GeoPackage (used only if roads is None).
        output_path : Path to write the output GeoJSON.
        roads       : Pre-loaded roads GDF. If provided, roads_path is ignored.
    """
    if roads is None:
        roads = load_all_threats(
            {"sources": {"osm_roads": {"path": str(roads_path)}}},
            bbox=AFRICA_BBOX,
        )

    backbone = build_backbone_roads(roads)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    backbone.to_file(output_path, driver="GeoJSON")


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
            print(f"  -> road_threats_gbif_{slug}.geojson")
        except Exception as e:
            print(f"  ERROR - {scientific_name}: {e}")


def main() -> None:
    export_all_road_threats(
        data_dir=Path("data/processed"),
        roads_path=Path("data/raw/threats/africa_roads.gpkg"),
        output_dir=Path("apps/mapbox/data"),
    )
    export_backbone_roads(
        roads_path=Path("data/raw/threats/africa_roads.gpkg"),
        output_path=Path("apps/mapbox/data/roads_backbone.geojson"),
    )


if __name__ == "__main__":  # pragma: no cover
    main()
