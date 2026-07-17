"""
export_settlement_threats.py

Computes settlement threat scores for all species from OSM settlement (places)
data and exports enriched GeoJSON for the Mapbox app's SETTLEMENTS view.

USAGE:
------
    python scripts/export_settlement_threats.py

    Requires an OSM settlements GeoPackage at data/raw/threats/africa_settlements.gpkg
    (produced by scripts/fetch_road_data.py, which downloads each Geofabrik
    country once and extracts both roads and settlements).

OUTPUT:
-------
    apps/mapbox/data/settlement_threats_gbif_{species}.geojson
        GeoJSON FeatureCollection with settlement_threat_score (0-1),
        settlement_class, and distance_to_settlement_m per occurrence.
    apps/mapbox/data/settlements_points.geojson
        The city/town points drawn on the map (village/hamlet omitted to avoid
        clutter — analytics still score against ALL settlement classes).

ARCHITECTURE NOTE:
------------------
Mirrors export_road_threats.py. Settlements are loaded once, then reused across
all species — the settlement network is species-independent. Each species gets
its own score via the unified scoring engine (score_stressor(..., "settlements",
...)), using that species' settlements-stressor sensitivity and class weights
from SPECIES_CONFIG.

Part of the static pre-computation pipeline — re-run when OSM data updates.
"""

from pathlib import Path

import geopandas as gpd

from wildlife_water_stress_atlas.analytics.apply import apply_settlement_threat_score
from wildlife_water_stress_atlas.analytics.overlap import add_distance_to_settlement
from wildlife_water_stress_atlas.analytics.stress_engine import score_stressor
from wildlife_water_stress_atlas.analytics.stressors import FeatureProximity
from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG
from wildlife_water_stress_atlas.ingest.threats import load_all_threats

# Bounding box covering continental Africa (lon_min, lat_min, lon_max, lat_max)
AFRICA_BBOX = (-20.0, -35.0, 55.0, 38.0)

_OUTPUT_COLS = ["species", "year", "distance_to_settlement_m", "settlement_class", "settlement_threat_score"]

# Settlement classes drawn on the map (SETTLEMENTS view). Only the larger,
# sparser classes are shown — villages and hamlets number in the hundreds of
# thousands and would drown the occurrences. The analytics still score against
# ALL settlement classes; this only limits what is painted.
DISPLAY_SETTLEMENT_CLASSES = {"city", "town"}


def compute_settlement_threats(
    occurrences: gpd.GeoDataFrame,
    settlements: gpd.GeoDataFrame,
    scientific_name: str,
) -> gpd.GeoDataFrame:
    """
    Compute settlement threat scores for all occurrences of one species.

    Pure computation — no file I/O. Composes add_distance_to_settlement and
    apply_settlement_threat_score over the supplied GeoDataFrames.

    Args:
        occurrences    : GeoDataFrame of GBIF occurrence points.
        settlements    : Normalized settlements GDF from OSMSettlements.load().
        scientific_name: Species scientific name (must be in SPECIES_CONFIG).

    Returns:
        GeoDataFrame with distance_to_settlement_m, settlement_class, and
        settlement_threat_score columns added.
    """
    with_distances = add_distance_to_settlement(occurrences, settlements)
    return apply_settlement_threat_score(with_distances, _settlement_threat_score)


def _settlement_threat_score(distance_m: float, settlement_class: str, species: str) -> float:
    """Adapter to the unified engine (cutover): the settlements-stressor value the
    legacy threat_scoring.settlement_threat_score used to return."""
    return score_stressor(species, "settlements", FeatureProximity(distance_m, settlement_class))


def build_settlement_points(
    settlements: gpd.GeoDataFrame,
    classes: set = DISPLAY_SETTLEMENT_CLASSES,
) -> gpd.GeoDataFrame:
    """
    Subset settlements to the display classes for the map layer.

    Pure transform — no I/O. Settlements are points, so no geometry
    simplification is needed (unlike the road backbone).

    Args:
        settlements : Normalized settlements GDF (must have a settlement_class column).
        classes     : Classes to keep. Default DISPLAY_SETTLEMENT_CLASSES.

    Returns:
        GeoDataFrame with settlement_class + geometry, display classes only.
    """
    return settlements[settlements["settlement_class"].isin(classes)][["settlement_class", "geometry"]].copy()


def export_settlement_points(
    settlements_path: Path,
    output_path: Path,
    settlements: gpd.GeoDataFrame | None = None,
) -> None:
    """
    Export the display settlement points as GeoJSON for the map layer.

    Args:
        settlements_path : Path to the OSM settlements GeoPackage (used only if
                           settlements is None).
        output_path      : Path to write the output GeoJSON.
        settlements      : Pre-loaded settlements GDF. If provided, the path is ignored.
    """
    if settlements is None:
        settlements = load_all_threats(
            {"sources": {"osm_settlements": {"path": str(settlements_path)}}},
            bbox=AFRICA_BBOX,
        )

    points = build_settlement_points(settlements)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    points.to_file(output_path, driver="GeoJSON")


def export_settlement_threat(
    occurrences_path: Path,
    settlements_path: Path,
    output_path: Path,
    scientific_name: str,
    settlements: gpd.GeoDataFrame | None = None,
) -> None:
    """
    Compute and export settlement threat GeoJSON for one species.

    Args:
        occurrences_path : Path to the GBIF cache GeoPackage.
        settlements_path : Path to the OSM settlements GeoPackage (used only if
                           settlements is not provided).
        output_path      : Path to write the output GeoJSON.
        scientific_name  : Species scientific name.
        settlements      : Pre-loaded settlements GDF. If provided, the path is
                           ignored — avoids reloading for each species.
    """
    occurrences = gpd.read_file(occurrences_path)

    if settlements is None:
        settlements = load_all_threats(
            {"sources": {"osm_settlements": {"path": str(settlements_path)}}},
            bbox=AFRICA_BBOX,
        )

    gdf = compute_settlement_threats(occurrences, settlements, scientific_name)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cols = [c for c in _OUTPUT_COLS if c in gdf.columns]
    gdf[cols + ["geometry"]].to_file(output_path, driver="GeoJSON")


def export_all_settlement_threats(
    data_dir: Path,
    settlements_path: Path,
    output_dir: Path,
) -> None:
    """
    Compute and export settlement threat GeoJSON for every species in SPECIES_CONFIG.

    Settlements are loaded once and reused across all species.

    Args:
        data_dir         : Directory containing GBIF cache GeoPackages.
        settlements_path : Path to the OSM settlements GeoPackage.
        output_dir       : Directory to write output GeoJSON files.
    """
    settlements = load_all_threats(
        {"sources": {"osm_settlements": {"path": str(settlements_path)}}},
        bbox=AFRICA_BBOX,
    )

    for scientific_name, cfg in SPECIES_CONFIG.items():
        slug = scientific_name.lower().replace(" ", "_")
        occurrences_path = data_dir / cfg["gbif_cache_file"]
        output_path = output_dir / f"settlement_threats_gbif_{slug}.geojson"

        try:
            export_settlement_threat(
                occurrences_path=occurrences_path,
                settlements_path=settlements_path,
                output_path=output_path,
                scientific_name=scientific_name,
                settlements=settlements,
            )
            print(f"  -> settlement_threats_gbif_{slug}.geojson")
        except Exception as e:
            print(f"  ERROR - {scientific_name}: {e}")


def main() -> None:
    export_all_settlement_threats(
        data_dir=Path("data/processed"),
        settlements_path=Path("data/raw/threats/africa_settlements.gpkg"),
        output_dir=Path("apps/mapbox/data"),
    )
    export_settlement_points(
        settlements_path=Path("data/raw/threats/africa_settlements.gpkg"),
        output_path=Path("apps/mapbox/data/settlements_points.geojson"),
    )


if __name__ == "__main__":  # pragma: no cover
    main()
