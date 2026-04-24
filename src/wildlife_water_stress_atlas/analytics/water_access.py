"""
water_access.py

Species-specific filtering and weighting of water sources.

WHY THIS FILE CHANGED:
----------------------
Previously this module maintained its own copies of species configuration:
    SPECIES_ACCESSIBLE_WATER_TYPES = {"Loxodonta africana": {"river", "lake"}}
    WATER_TYPE_WEIGHTS = {"Loxodonta africana": {"river": 1.0, "lake": 1.0}}

That was a maintenance hazard — adding a new water type (e.g. "pan") meant
editing both this file AND config/species.py. The two could silently drift
out of sync.

Now both functions read directly from SPECIES_CONFIG in config/species.py,
which is the single source of truth for all species configuration. Adding
a new water type to the elephant config there is all that's needed — no
changes required here.

This is also what makes the phantom thirst fix straightforward: once "pan",
"wetland", and "floodplain" are registered in SPECIES_CONFIG and their
source classes exist in water.py, they will automatically flow through
filter_accessible_water() and into the distance calculation.
"""

import geopandas as gpd

from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG


def filter_accessible_water(
    water: gpd.GeoDataFrame,
    species: str,
) -> gpd.GeoDataFrame:
    """
    Filter water sources to only those accessible to a given species.

    Reads accessible water types directly from the species config registry.
    Adding a new water type to SPECIES_CONFIG is all that's needed to make
    it visible to this filter — no changes required here.

    Args:
        water   : GeoDataFrame with a 'type' column describing each water
                  source type (e.g. "river", "lake", "pan").
        species : Scientific name of the species (must exist in SPECIES_CONFIG).

    Returns:
        Filtered GeoDataFrame containing only accessible water source types.
        Returns an empty GeoDataFrame if no features match — never raises
        on an empty result.

    Raises:
        KeyError: If species is not found in SPECIES_CONFIG.
    """
    # This will raise KeyError if species is unknown — intentional,
    # same behavior as before, consistent with how scoring.py handles it
    allowed_types = SPECIES_CONFIG[species]["accessible_water_types"]

    return water[water["type"].isin(allowed_types)].copy()


def get_water_type_weights(species: str) -> dict[str, float]:
    """
    Return species-specific reliability weights for each accessible water type.

    Reads directly from the species config registry. Weights reflect how
    reliably each water type provides accessible water for the species —
    1.0 means fully reliable year-round, lower values indicate seasonal
    or less dependable sources.

    Args:
        species : Scientific name of the species (must exist in SPECIES_CONFIG).

    Returns:
        Dict mapping water type strings to float weights (0.0, 1.0].

    Raises:
        KeyError: If species is not found in SPECIES_CONFIG.
    """
    return SPECIES_CONFIG[species]["water_type_weights"]