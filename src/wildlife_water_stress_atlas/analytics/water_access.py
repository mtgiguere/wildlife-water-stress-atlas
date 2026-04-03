"""
water_access.py

Species-specific filtering for accessible water sources.
"""

import geopandas as gpd

SPECIES_ACCESSIBLE_WATER_TYPES = {
    "Loxodonta africana": {"river", "lake"},
}

WATER_TYPE_WEIGHTS = {
    "Loxodonta africana": {
        "river": 1.0,
        "lake": 1.0,
    },
}


def filter_accessible_water(
    water: gpd.GeoDataFrame,
    species: str,
) -> gpd.GeoDataFrame:
    """
    Filter water sources to only those accessible for a given species.

    Args:
        water: GeoDataFrame with a 'type' column describing water source type.
        species: Scientific name of the species.

    Returns:
        Filtered GeoDataFrame containing only accessible water source types.
    """
    allowed_types = SPECIES_ACCESSIBLE_WATER_TYPES[species]
    return water[water["type"].isin(allowed_types)].copy()

def get_water_type_weights(species: str) -> dict[str, float]:
    """
    Return species-specific weights for accessible water types.

    Args:
        species: Scientific name of the species.

    Returns:
        Mapping of water type to relative weight.
    """
    return WATER_TYPE_WEIGHTS[species]