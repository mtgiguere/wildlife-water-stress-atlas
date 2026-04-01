"""
apply.py

Apply analytics functions across GeoDataFrames.
"""


def apply_water_stress_score(gdf, scoring_func):
    """
    Return a copy of the GeoDataFrame with a water stress score column.

    Parameters
    ----------
    gdf : GeoDataFrame
        GeoDataFrame containing at least 'distance_to_water' and 'species'.
    scoring_func : callable
        Function accepting (distance, species) and returning a score.

    Returns
    -------
    GeoDataFrame
        Copy of the input GeoDataFrame with a new
        'water_stress_score' column.
    """
    result = gdf.copy()

    result["water_stress_score"] = result.apply(
        lambda row: scoring_func(
            row["distance_to_water"],
            row["species"],
        ),
        axis=1,
    )

    return result