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

import geopandas as gpd

from wildlife_water_stress_atlas.analytics.overlap import (
    add_distance_to_road,
    add_distance_to_settlement,
    add_distance_to_water,
)
from wildlife_water_stress_atlas.analytics.stress_engine import score_species_stress
from wildlife_water_stress_atlas.analytics.stressors import FeatureProximity


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

    water_s, road_s, settle_s, agg_s = [], [], [], []
    for _, row in occ.iterrows():
        measurements = {
            "water": FeatureProximity(row["distance_to_water"], None),
            "roads": FeatureProximity(row["distance_to_road_m"], row["road_class"]),
            "settlements": FeatureProximity(row["distance_to_settlement_m"], row["settlement_class"]),
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
