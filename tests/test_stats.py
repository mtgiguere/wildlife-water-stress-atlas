"""
test_stats.py

Tests for apps/streamlit/components/stats.py

TESTING STRATEGY:
-----------------
Pure data functions only — no Streamlit rendering calls.
All Streamlit rendering is in stats.py's render functions
and covered by Playwright E2E tests.

FUNCTION COVERAGE:
------------------
- get_water_threshold_display(species) — formatted threshold string
- get_species_comparison(counts)       — dict of species → record count
"""

import sys
from unittest.mock import MagicMock

import pytest

from apps.streamlit.components.stats import get_species_comparison, get_water_threshold_display

# Mock streamlit before importing stats.py
mock_st = MagicMock()
mock_st.cache_data = lambda func=None, **kwargs: func if func is not None else lambda f: f
sys.modules["streamlit"] = mock_st


# ---------------------------------------------------------------------------
# get_water_threshold_display
# ---------------------------------------------------------------------------


def test_get_water_threshold_display_elephant():
    # 300,000m → "300 km"
    result = get_water_threshold_display("Loxodonta africana")
    assert result == "300 km"


def test_get_water_threshold_display_reed_frog():
    # 2,000m → "2 km"
    result = get_water_threshold_display("Hyperolius marmoratus")
    assert result == "2 km"


def test_get_water_threshold_display_raises_for_unknown_species():
    # Unknown species should raise KeyError — no silent defaults
    with pytest.raises(KeyError):
        get_water_threshold_display("Unicornus imaginus")


def test_get_water_threshold_display_crocodile():
    # 10,000m → "10 km" — spot check a third species
    result = get_water_threshold_display("Crocodylus niloticus")
    assert result == "10 km"


# ---------------------------------------------------------------------------
# get_species_comparison
# ---------------------------------------------------------------------------


def test_get_species_comparison_returns_dict():
    counts = {"Loxodonta africana": 21900, "Equus quagga": 22235}
    result = get_species_comparison(counts)
    assert isinstance(result, dict)


def test_get_species_comparison_keys_are_common_names():
    # UI displays common names, not scientific names
    counts = {"Loxodonta africana": 21900}
    result = get_species_comparison(counts)
    assert "🐘 African Elephant" in result


def test_get_species_comparison_values_are_record_counts():
    counts = {"Loxodonta africana": 21900}
    result = get_species_comparison(counts)
    assert result["🐘 African Elephant"] == 21900


def test_get_species_comparison_includes_all_passed_species():
    counts = {
        "Loxodonta africana": 21900,
        "Equus quagga": 22235,
        "Crocodylus niloticus": 9134,
    }
    result = get_species_comparison(counts)
    assert len(result) == 3


def test_get_species_comparison_raises_for_unknown_species():
    # Unknown species should raise KeyError — no silent defaults
    with pytest.raises(KeyError):
        get_species_comparison({"Unicornus imaginus": 42})


def test_get_species_comparison_empty_input_returns_empty_dict():
    result = get_species_comparison({})
    assert result == {}
