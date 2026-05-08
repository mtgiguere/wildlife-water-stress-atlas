"""
stats.py

Pure data functions for statistics and comparison displays
in the Wildlife Water Stress Atlas Streamlit app.

WHY THIS FILE EXISTS:
---------------------
Keeps streamlit_app.py thin by moving stat computation logic
into testable pure functions. No Streamlit calls here —
those live in the render functions at the bottom of this file
and are covered by Playwright E2E tests.
"""

from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG


def get_water_threshold_display(species: str) -> str:
    """
    Return a human-readable water stress threshold for a species.

    Converts the raw meter value from SPECIES_CONFIG into a
    clean km string for display in the UI.

    Args:
        species: Scientific name — must be a key in SPECIES_CONFIG.

    Returns:
        Formatted string e.g. "300 km", "2 km", "10 km"
    """
    threshold_m = SPECIES_CONFIG[species]["water_threshold_m"]
    # Convert meters to km — all thresholds are whole km values
    threshold_km = int(threshold_m / 1000)
    return f"{threshold_km} km"


def get_species_comparison(counts: dict[str, int]) -> dict[str, int]:
    """
    Convert a dict of scientific name → record count into
    a display-ready dict of "{emoji} {common_name}" → record count.

    Args:
        counts: Dict mapping scientific names to record counts.
                Keys must be present in SPECIES_CONFIG.

    Returns:
        Dict mapping "{emoji} {common_name}" to record counts,
        ready for display in the UI.

    Raises:
        KeyError: If any scientific name is not in SPECIES_CONFIG.
    """
    return {f"{SPECIES_CONFIG[species]['emoji']} {SPECIES_CONFIG[species]['common_name']}": count for species, count in counts.items()}
