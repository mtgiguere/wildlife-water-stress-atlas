"""
streamlit_app.py

Main entry point for the Wildlife Water Stress Atlas Streamlit application.

HOW TO RUN:
-----------
    streamlit run apps/streamlit/streamlit_app.py

ARCHITECTURE:
-------------
This file is intentionally thin — it only orchestrates the components.
All business logic lives in the library (src/) and component helpers
(apps/streamlit/components/). This keeps the app testable and the
pipeline reusable outside of Streamlit.

FLOW:
-----
1. Load water layer from cache (instant if cached, ~5min first run)
2. Load full GBIF occurrence dataset from cache (instant if cached)
3. Render sidebar — year slider returns selected year
4. Filter occurrences by selected year in memory (instant)
5. Build PyDeck layers from water + filtered occurrences
6. Render map + stats

DATA QUALITY NOTE:
------------------
GBIF records include museum specimens, historical sightings, imprecise
coordinates, and potentially captive animals alongside wild GPS-tracked
individuals. These are intentionally preserved — data gaps and anomalies
are insights, not errors. See project bible Section 4 for full details.
"""
import sys
from pathlib import Path

# Add repo root to path so 'apps' and 'src' packages are importable
# Required for Streamlit Cloud deployment where pip install -e . isn't run
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import streamlit as st

from apps.streamlit.components.cache import load_gbif_data, load_water_layer_simplified
from apps.streamlit.components.map import build_deck, build_occurrences_layer, build_water_layer
from apps.streamlit.components.sidebar import render_sidebar

# ---------------------------------------------------------------------------
# Page config — must be first Streamlit call
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Wildlife Water Stress Atlas",
    page_icon="🐘",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Main area header
# ---------------------------------------------------------------------------

st.title("🐘 Wildlife Water Stress Atlas")
st.markdown("Tracking African elephant (*Loxodonta africana*) occurrence records against freshwater availability across Africa. Use the year slider to watch population distribution shift over time.")
st.markdown("---")

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

# Water layer — loads from cache or builds on first run - load only the simplified version since browswer has trouble with full
water_gdf = load_water_layer_simplified()

# Full GBIF dataset — loads from cache or fetches on first run
all_occurrences = load_gbif_data()

# ---------------------------------------------------------------------------
# Sidebar — year slider + stats
# ---------------------------------------------------------------------------

selected_year = render_sidebar(all_occurrences)

# ---------------------------------------------------------------------------
# Filter occurrences by selected year
# ---------------------------------------------------------------------------

year_occurrences = load_gbif_data(year=selected_year)

# ---------------------------------------------------------------------------
# Build map
# ---------------------------------------------------------------------------

water_layers = build_water_layer(water_gdf)
occurrences_layer = build_occurrences_layer(year_occurrences)
deck = build_deck(water_layers, occurrences_layer)

# ---------------------------------------------------------------------------
# Render map
# ---------------------------------------------------------------------------

st.pydeck_chart(deck, use_container_width=True)

# ---------------------------------------------------------------------------
# Stats row below map
# ---------------------------------------------------------------------------

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label=f"Elephant Records — {selected_year}",
        value=f"{len(year_occurrences):,}",
    )

with col2:
    st.metric(
        label="Total Records in Dataset",
        value=f"{len(all_occurrences):,}",
    )

with col3:
    st.metric(
        label="Water Sources Mapped",
        value=f"{len(water_gdf):,}",
    )

# ---------------------------------------------------------------------------
# Data quality note
# ---------------------------------------------------------------------------

st.markdown("---")
st.caption(
    "**Data quality note:** GBIF records include museum specimens, "
    "historical sightings, and records with imprecise coordinates alongside "
    "wild GPS-tracked individuals. Gaps in the data (e.g. the 2020 COVID dip) "
    "are insights, not errors — they reflect funding cycles, field access, "
    "and the limits of our collective knowledge. "
    "**Data confidence is a first-class output of this platform.**"
)

st.caption("**Sources:** GBIF · GLWD v2 (Lehner et al., 2025) · Natural Earth · JRC Global Surface Water")
