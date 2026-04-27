"""
sidebar.py

Sidebar data functions for the Wildlife Water Stress Atlas Streamlit app.

WHY THIS FILE EXISTS:
---------------------
The sidebar contains the year slider and stats panel. The Streamlit
rendering (st.slider, st.metric, st.write) cannot be unit tested
without a running server — those are covered by Playwright E2E tests.

The pure data functions here ARE unit testable and are kept separate
from Streamlit calls deliberately. This follows the same pattern as
the rest of the codebase — logic is separated from presentation.

FUNCTIONS:
----------
get_year_range(gdf)   — returns (min_year, max_year) for slider bounds
get_record_count(gdf) — returns total record count for stats display
get_year_counts(gdf)  — returns sorted dict of year → count for chart

STREAMLIT RENDERING:
--------------------
render_sidebar(gdf) wires the data functions to Streamlit widgets.
This function is NOT unit tested — covered by Playwright E2E instead.
"""

import geopandas as gpd
import streamlit as st

# ---------------------------------------------------------------------------
# Pure data functions — fully unit testable
# ---------------------------------------------------------------------------


def get_year_range(gdf: gpd.GeoDataFrame) -> tuple[int, int]:
    """
    Return the min and max year from an occurrences GeoDataFrame.

    Used to set the bounds of the year slider. Records with missing
    year values are ignored — they don't affect the range.

    Args:
        gdf: Occurrences GeoDataFrame with a year column.

    Returns:
        Tuple of (min_year, max_year) as integers.
    """
    years = gdf["year"].dropna()
    return int(years.min()), int(years.max())


def get_record_count(gdf: gpd.GeoDataFrame) -> int:
    """
    Return the total number of records in a GeoDataFrame.

    Used to display the record count stat in the sidebar.

    Args:
        gdf: Any GeoDataFrame.

    Returns:
        Integer count of rows.
    """
    return int(len(gdf))


def get_year_counts(gdf: gpd.GeoDataFrame) -> dict[int, int]:
    """
    Return a sorted dict mapping year → record count.

    Used to display the year distribution chart in the sidebar.
    Records with missing year values are excluded.

    Args:
        gdf: Occurrences GeoDataFrame with a year column.

    Returns:
        Dict of {year: count} sorted by year ascending.
        Empty dict if GeoDataFrame is empty or has no year values.
    """
    years = gdf["year"].dropna()

    if years.empty:
        return {}

    counts = years.astype(int).value_counts().sort_index()
    return {int(year): int(count) for year, count in counts.items()}


# ---------------------------------------------------------------------------
# Streamlit rendering — NOT unit tested, covered by Playwright E2E
# ---------------------------------------------------------------------------


def render_sidebar(gdf: gpd.GeoDataFrame) -> int:
    """
    Render the sidebar year slider and stats panel.

    This function is the only place Streamlit widgets are called in
    this module. It reads from the pure data functions above and
    wires them to Streamlit UI elements.

    Args:
        gdf: Full occurrences GeoDataFrame (all years).

    Returns:
        Selected year from the slider as an integer.
    """
    st.sidebar.title("🐘 Wildlife Water Stress Atlas")
    st.sidebar.markdown("---")

    min_year, max_year = get_year_range(gdf)
    year_counts = get_year_counts(gdf)

    selected_year = st.sidebar.slider(
        label="Select Year",
        min_value=min_year,
        max_value=max_year,
        value=max_year,  # default to most recent year
        step=1,
    )

    st.sidebar.markdown("---")

    # Stats for selected year
    year_count = year_counts.get(selected_year, 0)
    total = get_record_count(gdf)

    st.sidebar.metric(
        label=f"Records in {selected_year}",
        value=f"{year_count:,}",
    )

    st.sidebar.metric(
        label="Total Records",
        value=f"{total:,}",
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Data sources:** GBIF, GLWD v2, Natural Earth, JRC GSW")
    st.sidebar.markdown("**Species:** *Loxodonta africana*")

    return selected_year
