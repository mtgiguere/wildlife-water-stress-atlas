"""
test_trends.py

Tests for src/wildlife_water_stress_atlas/analytics/trends.py

FUNCTION COVERAGE:
------------------
- compute_trend(year_counts)         — linear regression, returns slope, intercept, r2
- classify_trend(slope)              — "increasing" | "stable" | "declining"
- get_country_time_series(data, iso) — filter country_counts list by ISO_A3
"""

from wildlife_water_stress_atlas.analytics.trends import compute_linear_regression

# ---------------------------------------------------------------------------
# compute_trend()
# ---------------------------------------------------------------------------


def test_compute_linear_regression_returns_slope():
    """compute_trend() returns a slope value."""
    year_counts = {2018: 10, 2019: 20, 2020: 30, 2021: 40}
    result = compute_linear_regression(year_counts)
    assert "slope" in result


def test_compute_linear_regression_slope_is_correct_for_linear_data():
    """compute_trend() returns correct slope for perfectly linear data."""
    year_counts = {2018: 10, 2019: 20, 2020: 30, 2021: 40}
    result = compute_linear_regression(year_counts)
    assert abs(result["slope"] - 10.0) < 0.001


def test_compute_linear_regression_returns_intercept_and_r2():
    """compute_linear_regression() returns intercept and r2 values."""
    year_counts = {2018: 10, 2019: 20, 2020: 30, 2021: 40}
    result = compute_linear_regression(year_counts)
    assert "intercept" in result
    assert "r2" in result


def test_compute_linear_regression_r2_is_1_for_perfect_linear_data():
    """compute_linear_regression() returns r2=1.0 for perfectly linear data."""
    year_counts = {2018: 10, 2019: 20, 2020: 30, 2021: 40}
    result = compute_linear_regression(year_counts)
    assert abs(result["r2"] - 1.0) < 0.001


def test_compute_linear_regression_handles_empty_input():
    """compute_linear_regression() returns zeros for empty input."""
    result = compute_linear_regression({})
    assert result["slope"] == 0
    assert result["intercept"] == 0
    assert result["r2"] == 0


def test_compute_linear_regression_handles_single_point():
    """compute_linear_regression() returns zeros for a single data point."""
    result = compute_linear_regression({2020: 42})
    assert result["slope"] == 0
    assert result["intercept"] == 0
    assert result["r2"] == 0


def test_classify_trend_returns_increasing_for_positive_slope():
    """classify_trend() returns 'increasing' for positive slope."""
    from wildlife_water_stress_atlas.analytics.trends import classify_trend

    assert classify_trend(5.0) == "increasing"


def test_classify_trend_returns_declining_for_negative_slope():
    """classify_trend() returns 'declining' for negative slope."""
    from wildlife_water_stress_atlas.analytics.trends import classify_trend

    assert classify_trend(-5.0) == "declining"


def test_classify_trend_returns_stable_for_near_zero_slope():
    """classify_trend() returns 'stable' for slope near zero."""
    from wildlife_water_stress_atlas.analytics.trends import classify_trend

    assert classify_trend(0.0) == "stable"


def test_classify_trend_returns_stable_for_slope_below_threshold():
    """classify_trend() returns 'stable' for very small slopes — noise not signal."""
    from wildlife_water_stress_atlas.analytics.trends import classify_trend

    assert classify_trend(0.4) == "stable"
    assert classify_trend(-0.4) == "stable"
    assert classify_trend(0.5) == "increasing"
    assert classify_trend(-0.5) == "declining"


def test_get_country_time_series_filters_by_iso():
    """get_country_time_series() returns only records for the given ISO_A3."""
    from wildlife_water_stress_atlas.analytics.trends import get_country_time_series

    data = [
        {"NAME": "Kenya", "ISO_A3": "KEN", "year": 2018, "count": 10},
        {"NAME": "Kenya", "ISO_A3": "KEN", "year": 2019, "count": 20},
        {"NAME": "Tanzania", "ISO_A3": "TZA", "year": 2018, "count": 5},
    ]

    result = get_country_time_series(data, "KEN")
    assert len(result) == 2
    assert all(r["ISO_A3"] == "KEN" for r in result)


def test_get_country_time_series_is_sorted_by_year():
    """get_country_time_series() returns records sorted by year ascending."""
    from wildlife_water_stress_atlas.analytics.trends import get_country_time_series

    data = [
        {"NAME": "Kenya", "ISO_A3": "KEN", "year": 2020, "count": 30},
        {"NAME": "Kenya", "ISO_A3": "KEN", "year": 2018, "count": 10},
        {"NAME": "Kenya", "ISO_A3": "KEN", "year": 2019, "count": 20},
    ]

    result = get_country_time_series(data, "KEN")
    years = [r["year"] for r in result]
    assert years == sorted(years)


def test_get_country_time_series_returns_empty_for_unknown_iso():
    """get_country_time_series() returns empty list for unknown ISO_A3."""
    from wildlife_water_stress_atlas.analytics.trends import get_country_time_series

    data = [
        {"NAME": "Kenya", "ISO_A3": "KEN", "year": 2020, "count": 30},
    ]

    result = get_country_time_series(data, "ZZZ")
    assert result == []


def test_add_trends_to_country_counts_adds_slope_and_classification():
    """add_trends_to_country_counts() adds slope, r2, and trend to each country."""
    from wildlife_water_stress_atlas.analytics.trends import add_trends_to_country_counts

    data = [
        {"NAME": "Kenya", "ISO_A3": "KEN", "year": 2018, "count": 10},
        {"NAME": "Kenya", "ISO_A3": "KEN", "year": 2019, "count": 20},
        {"NAME": "Kenya", "ISO_A3": "KEN", "year": 2020, "count": 30},
    ]

    result = add_trends_to_country_counts(data)

    kenya_records = [r for r in result if r["ISO_A3"] == "KEN"]
    assert all("slope" in r for r in kenya_records)
    assert all("r2" in r for r in kenya_records)
    assert all("trend" in r for r in kenya_records)
    assert kenya_records[0]["trend"] == "increasing"
