"""
export_stress.py

Generic, stressor-driven stress computation (Phase C) — the first real consumer
of the kind-aware engine over geospatial data.

compute_species_stress() composes the overlap layer (distance from each
occurrence to each stressor's features) with the generic engine
(score_species_stress) to produce, per occurrence, a per-stressor score
breakdown PLUS the cumulative aggregate. It reproduces the legacy per-stressor
pipelines exactly (golden guard in test_export_stress.py) while unifying them
through one engine — the step that lets the map become stressor-driven instead
of hardcoding one view per stressor.

The file-writing/export wrapper + retiring the special-case export scripts comes
in a later increment, once the frontend consumes this generic output.
"""

from pathlib import Path

import geopandas as gpd
import numpy as np

from wildlife_water_stress_atlas.analytics.overlap import (
    add_distance_to_road,
    add_distance_to_settlement,
    add_distance_to_water,
    within_layer_extent,
)
from wildlife_water_stress_atlas.analytics.scoring import classify_stress_level
from wildlife_water_stress_atlas.analytics.stress_engine import score_species_stress, score_stressor
from wildlife_water_stress_atlas.analytics.stressors import FeatureProximity, Score, aggregate_stress
from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG
from wildlife_water_stress_atlas.ingest.gbif import OCCURRENCE_COLS
from wildlife_water_stress_atlas.ingest.threats import load_all_threats

# Bounding box covering continental Africa (lon_min, lat_min, lon_max, lat_max)
AFRICA_BBOX = (-20.0, -35.0, 55.0, 38.0)

# Columns written to the per-species stress GeoJSON. The generic frontend reads
# stress_aggregate for the headline layer and the per-stressor columns for the
# breakdown/toggle.
_OUTPUT_COLS = [*OCCURRENCE_COLS, "stress_water", "stress_roads", "stress_settlements", "stress_aggregate"]


def rescore_water_with_added_source(
    stress_scores: gpd.GeoDataFrame,
    added_distance_m,
    species: str,
) -> gpd.GeoDataFrame:
    """
    Fold an ADDITIONAL accessible water source into an existing per-occurrence
    water-stress table (row-aligned).

    Adding water can only shorten the distance to nearest water, so the new
    distance is the elementwise min of the current distance and the distance to
    the new source; stress_score + stress_level are then recomputed via the
    engine. This lets us add HydroRIVERS to the existing stress_scores exports
    without reloading the whole water stack — and it preserves the occurrence
    alignment those files already share with roads/settlements.

    Raises:
        ValueError: if added_distance_m isn't the same length as stress_scores.
    """
    added = np.asarray(list(added_distance_m), dtype=float)
    if len(added) != len(stress_scores):
        raise ValueError(f"added_distance_m length {len(added)} != stress_scores length {len(stress_scores)}")

    out = stress_scores.copy()
    out["distance_m"] = np.minimum(out["distance_m"].to_numpy(dtype=float), added)
    out["stress_score"] = [score_stressor(species, "water", FeatureProximity(float(d), None)) for d in out["distance_m"]]
    out["stress_level"] = out["stress_score"].apply(classify_stress_level)
    return out


def _as_score(value) -> Score:
    """One per-stressor export value as a Score, honouring "no reading here".

    None/NaN is uncovered, never 0.0 — see Score.covered.
    """
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return Score(None, False)
    return Score(float(value), True)


def build_stress_from_scores(
    water_gdf: gpd.GeoDataFrame,
    roads_gdf: gpd.GeoDataFrame,
    settlements_gdf: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """
    Build the cumulative-stress GeoDataFrame from the already-computed per-stressor
    exports — the FAST path that avoids recomputing distances over continental
    roads/water.

    The per-stressor scores in those exports ARE the engine's scores (post-cutover
    every export routes through score_stressor), so the noisy-OR here is identical
    to compute_species_stress's aggregate — it just reuses prior work.

    Inputs must be ROW-ALIGNED (same occurrences in the same order) — they are, as
    all three derive from the same GBIF cache. Columns read: water.stress_score,
    roads.road_threat_score, settlements.settlement_threat_score.

    Raises:
        ValueError: if the three inputs are not the same length (misaligned).
    """
    n = len(roads_gdf)
    if not (len(water_gdf) == len(settlements_gdf) == n):
        raise ValueError(f"per-stressor exports are misaligned: water={len(water_gdf)}, roads={n}, settlements={len(settlements_gdf)}")

    water = water_gdf["stress_score"].to_numpy()
    roads = roads_gdf["road_threat_score"].to_numpy()
    setts = settlements_gdf["settlement_threat_score"].to_numpy()

    # A present score is covered — a real 0 means "measured, no stress". A
    # MISSING one means the per-stressor export had no reading there (the
    # occurrence fell outside that layer's extent), and must stay out of the
    # noisy-OR rather than entering it as a fabricated 0.0.
    aggregate = [aggregate_stress([_as_score(w), _as_score(r), _as_score(s)]).value for w, r, s in zip(water, roads, setts, strict=True)]

    out = roads_gdf[[c for c in OCCURRENCE_COLS if c in roads_gdf.columns]].copy()
    out["stress_water"] = water
    out["stress_roads"] = roads
    out["stress_settlements"] = setts
    out["stress_aggregate"] = aggregate
    out["geometry"] = roads_gdf.geometry.to_numpy()
    return gpd.GeoDataFrame(out, geometry="geometry", crs=roads_gdf.crs)


# Default input/output locations (match the other export scripts).
DEFAULT_DATA_DIR = Path("data/processed")
DEFAULT_WATER_PATH = Path("data/processed/water_africa_simplified.gpkg")
DEFAULT_ROADS_PATH = Path("data/raw/threats/africa_roads.gpkg")
DEFAULT_SETTLEMENTS_PATH = Path("data/raw/threats/africa_settlements.gpkg")
DEFAULT_OUTPUT_DIR = Path("apps/mapbox/data")


def compute_species_stress(
    occurrences: gpd.GeoDataFrame,
    *,
    water: gpd.GeoDataFrame,
    roads: gpd.GeoDataFrame,
    settlements: gpd.GeoDataFrame,
    species: str,
) -> gpd.GeoDataFrame:
    """
    Score a species' occurrences across all its stressors via the engine.

    For each occurrence: compute distance to the nearest water / road /
    settlement, hand those measurements to score_species_stress, and record the
    per-stressor breakdown plus the noisy-OR aggregate.

    Args:
        occurrences : GeoDataFrame of occurrence points.
        water       : water source geometries (for the RESOURCE stressor).
        roads       : normalized roads GDF (road_class) — HAZARD.
        settlements : normalized settlements GDF (settlement_class) — HAZARD.
        species     : scientific name (must be in SPECIES_CONFIG).

    Returns:
        The occurrences GeoDataFrame with the overlap distance/class columns plus
        stress_water, stress_roads, stress_settlements, stress_aggregate.
    """
    occ = add_distance_to_water(occurrences, water)
    occ = add_distance_to_road(occ, roads)
    occ = add_distance_to_settlement(occ, settlements)

    # An occurrence outside a layer's extent has no measurement for it, only a
    # distance to wherever that layer's data happens to stop. Passing None
    # instead makes the engine mark the stressor uncovered and drop it from the
    # noisy-OR, rather than inventing a score: absent hazard data would read as
    # a confident 0.0, and absent RESOURCE data inverts into maximum scarcity.
    covered = {
        "water": within_layer_extent(occ, water).to_numpy(),
        "roads": within_layer_extent(occ, roads).to_numpy(),
        "settlements": within_layer_extent(occ, settlements).to_numpy(),
    }

    water_s, road_s, settle_s, agg_s = [], [], [], []
    for i, (_, row) in enumerate(occ.iterrows()):
        measurements = {
            "water": FeatureProximity(row["distance_to_water"], None) if covered["water"][i] else None,
            "roads": FeatureProximity(row["distance_to_road_m"], row["road_class"]) if covered["roads"][i] else None,
            "settlements": FeatureProximity(row["distance_to_settlement_m"], row["settlement_class"]) if covered["settlements"][i] else None,
        }
        result = score_species_stress(species, measurements)
        water_s.append(result.breakdown["water"].value)
        road_s.append(result.breakdown["roads"].value)
        settle_s.append(result.breakdown["settlements"].value)
        agg_s.append(result.aggregate.value)

    occ = occ.copy()
    occ["stress_water"] = water_s
    occ["stress_roads"] = road_s
    occ["stress_settlements"] = settle_s
    occ["stress_aggregate"] = agg_s
    return occ


def export_species_stress(
    occurrences_path: Path,
    output_path: Path,
    species: str,
    *,
    water: gpd.GeoDataFrame,
    roads: gpd.GeoDataFrame,
    settlements: gpd.GeoDataFrame,
) -> None:
    """
    Compute and write one species' stress GeoJSON (per-stressor + aggregate).

    Feature layers are passed in pre-loaded so export_all_stress can load them
    once and reuse across all species.
    """
    occurrences = gpd.read_file(occurrences_path)
    gdf = compute_species_stress(occurrences, water=water, roads=roads, settlements=settlements, species=species)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cols = [c for c in _OUTPUT_COLS if c in gdf.columns]
    gdf[cols + ["geometry"]].to_file(output_path, driver="GeoJSON")


def export_all_stress(
    data_dir: Path = DEFAULT_DATA_DIR,
    water_path: Path = DEFAULT_WATER_PATH,
    roads_path: Path = DEFAULT_ROADS_PATH,
    settlements_path: Path = DEFAULT_SETTLEMENTS_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> None:
    """
    Compute and write stress GeoJSON for every species in SPECIES_CONFIG.

    Water / roads / settlements are loaded once and reused. A species that fails
    (e.g. missing cache file) is logged and skipped — the run continues.
    """
    water = gpd.read_file(water_path)
    roads = load_all_threats({"sources": {"osm_roads": {"path": str(roads_path)}}}, bbox=AFRICA_BBOX)
    settlements = load_all_threats({"sources": {"osm_settlements": {"path": str(settlements_path)}}}, bbox=AFRICA_BBOX)

    for scientific_name, cfg in SPECIES_CONFIG.items():
        slug = scientific_name.lower().replace(" ", "_")
        occurrences_path = data_dir / cfg["gbif_cache_file"]
        output_path = output_dir / f"stress_gbif_{slug}.geojson"
        try:
            export_species_stress(occurrences_path, output_path, scientific_name, water=water, roads=roads, settlements=settlements)
            print(f"  -> stress_gbif_{slug}.geojson")
        except Exception as e:
            print(f"  ERROR - {scientific_name}: {e}")


def main() -> None:
    export_all_stress(
        data_dir=DEFAULT_DATA_DIR,
        water_path=DEFAULT_WATER_PATH,
        roads_path=DEFAULT_ROADS_PATH,
        settlements_path=DEFAULT_SETTLEMENTS_PATH,
        output_dir=DEFAULT_OUTPUT_DIR,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
