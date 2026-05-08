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
2. Render sidebar — species selector returns selected species
3. Load full GBIF occurrence dataset for selected species from cache
4. Render sidebar stats with correct species data
5. Filter occurrences by selected year in memory (instant)
6. Build PyDeck layers from water + filtered occurrences
7. Render map + stats + chart

ADDING A NEW SPECIES:
---------------------
Add one entry to SPECIES_CONFIG in config/species.py.
Run scripts/prefetch_gbif.py to cache the occurrence data.
Nothing in this file needs to change.

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

from apps.streamlit.components.cache import load_gbif_data, load_water_layer_simplified#, load_gbif_data_safe
from apps.streamlit.components.map import build_deck, build_occurrences_layer, build_water_layer
from apps.streamlit.components.sidebar import get_year_counts, render_sidebar
from apps.streamlit.components.stats import get_water_threshold_display#,get_species_comparison
from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG

# ---------------------------------------------------------------------------
# Page config — must be first Streamlit call
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Wildlife Water Stress Atlas",
    page_icon="🌍",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Global styles + hero banner
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
        /* --- Dark theme for whole app --- */
        .stApp {
            background-color: #0E1117;
        }

        /* Sidebar dark background */
        [data-testid="stSidebar"] {
            background-color: #161B22;
        }

        /* Sidebar text light */
        [data-testid="stSidebar"] * {
            color: #E0E0E0 !important;
        }

        /* Main text light */
        .stMarkdown, .stText, p, li {
            color: #E0E0E0;
        }

        /* Metric labels and values */
        [data-testid="stMetricLabel"] {
            color: #A0A0A0 !important;
        }
        [data-testid="stMetricValue"] {
            color: #FFFFFF !important;
        }

        /* Subheader */
        h2, h3 {
            color: #FFFFFF !important;
        }

        /* Caption text */
        .stCaption {
            color: #888888 !important;
        }

        /* Remove default Streamlit top padding so banner sits flush */
        .block-container {
            padding-top: 0rem !important;
        }

        /* --- Hero banner --- */
        .hero-banner {
            position: relative;
            width: 100%;
            height: 280px;
            background-image: url('app/static/elephants_waterhole.jpeg');
            background-size: cover;
            background-position: center 60%;
            border-radius: 0 0 8px 8px;
            margin-bottom: 1.5rem;
            overflow: hidden;
        }

        /* Dark gradient overlay so text is always readable */
        .hero-banner::after {
            content: '';
            position: absolute;
            inset: 0;
            background: linear-gradient(
                to bottom,
                rgba(0,0,0,0.15) 0%,
                rgba(0,0,0,0.65) 100%
            );
        }

        .hero-text {
            position: absolute;
            bottom: 2rem;
            left: 2rem;
            z-index: 10;
            color: white;
        }

        .hero-text h1 {
            font-size: 2.4rem;
            font-weight: 700;
            margin: 0 0 0.3rem 0;
            text-shadow: 0 2px 8px rgba(0,0,0,0.6);
            color: white !important;
        }

        .hero-text p {
            font-size: 1rem;
            margin: 0;
            opacity: 0.9;
            text-shadow: 0 1px 4px rgba(0,0,0,0.6);
            color: white !important;
        }
    </style>

    <div class="hero-banner">
        <div class="hero-text">
            <h1>🌍 Wildlife Water Stress Atlas</h1>
            <p>Tracking wildlife occurrence records against freshwater availability across Africa.</p>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Load water layer — species-independent, loaded once per session
# ---------------------------------------------------------------------------

water_gdf = load_water_layer_simplified()

# ---------------------------------------------------------------------------
# Sidebar — species selector + year slider
#
# Two-pass loading pattern:
#   Pass 1: Render sidebar with elephant data to get selected_species.
#           This is necessary because render_sidebar() needs a GeoDataFrame
#           to compute year range — we use elephants as the default.
#   Pass 2: If a different species was selected, reload sidebar with the
#           correct species data so year range and stats are accurate.
#
# Both loads are instant after first run thanks to @st.cache_data.
# ---------------------------------------------------------------------------

# Persist species selection across reruns using session state.
# Without this, every rerun resets the species to the default.
if "selected_species" not in st.session_state:
    st.session_state.selected_species = "Loxodonta africana"

# Load data for currently selected species
all_occurrences = load_gbif_data(species=st.session_state.selected_species)

# Render sidebar once — never twice. Duplicate renders cause
# StreamlitDuplicateElementId errors on the selectbox widget.
selected_species, selected_year = render_sidebar(all_occurrences)

# Persist selection for next rerun
st.session_state.selected_species = selected_species

# ---------------------------------------------------------------------------
# Filter occurrences by selected year — instant, done in memory
# ---------------------------------------------------------------------------

year_occurrences = load_gbif_data(species=selected_species, year=selected_year)

# ---------------------------------------------------------------------------
# Build and render map
# ---------------------------------------------------------------------------

# Icon path driven by SPECIES_CONFIG — switches automatically with species
cfg = SPECIES_CONFIG[selected_species]
icon_path = cfg["icon_static_path"]

water_layers = build_water_layer(water_gdf)
occurrences_layer = build_occurrences_layer(year_occurrences, icon_path=icon_path)
deck = build_deck(water_layers, occurrences_layer)

st.pydeck_chart(deck, width="stretch")

# ---------------------------------------------------------------------------
# Stats row below map — dynamic labels from SPECIES_CONFIG
# ---------------------------------------------------------------------------

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label=f"{cfg['emoji']} {cfg['common_name']} Records — {selected_year}",
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

with col4:
    st.metric(
        label="Water Stress Threshold",
        value=get_water_threshold_display(selected_species),
    )
# ---------------------------------------------------------------------------
# Year distribution chart — dynamic title from SPECIES_CONFIG
# ---------------------------------------------------------------------------

st.subheader(f"{cfg['emoji']} {cfg['common_name']} Records by Year")
year_counts = get_year_counts(all_occurrences)
st.bar_chart(year_counts)

# st.subheader("🌍 Species Record Counts")
# comparison_counts = {s: len(load_gbif_data_safe(species=s)) for s in SPECIES_CONFIG}
# st.bar_chart(get_species_comparison(comparison_counts))

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
