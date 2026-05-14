

# Minimum slope (records/year) to classify a trend as increasing or declining.
# Slopes within [-0.5, 0.5] are considered stable — noise, not signal.
# Heuristic placeholder — ecological validation needed in Phase 2.
STABLE_THRESHOLD = 0.5

def compute_linear_regression(year_counts):
    if len(year_counts) < 2:
        return {"slope": 0, "intercept": 0, "r2": 0}

    xs = list(year_counts.keys())
    ys = list(year_counts.values())
    n  = len(xs)

    x_mean = sum(xs) / n
    y_mean = sum(ys) / n

    numerator   = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    denominator = sum((x - x_mean) ** 2 for x in xs)

    slope     = numerator / denominator if denominator else 0
    intercept = y_mean - slope * x_mean

    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - y_mean) ** 2 for y in ys)
    r2     = 1 - ss_res / ss_tot if ss_tot else 0

    return {"slope": slope, "intercept": intercept, "r2": r2}


def classify_trend(slope):
    if slope >= STABLE_THRESHOLD:
        return "increasing"
    elif slope <= -STABLE_THRESHOLD:
        return "declining"
    else:
        return "stable"
    
def get_country_time_series(data, iso_a3):
    return sorted(
        [r for r in data if r["ISO_A3"] == iso_a3],
        key=lambda r: r["year"]
    )

def add_trends_to_country_counts(data):
    # Get unique countries
    countries = {r["ISO_A3"] for r in data}

    # Compute regression per country
    trends = {}
    for iso in countries:
        series = get_country_time_series(data, iso)
        year_counts = {r["year"]: r["count"] for r in series}
        regression = compute_linear_regression(year_counts)
        trends[iso] = {
            "slope": regression["slope"],
            "r2":    regression["r2"],
            "trend": classify_trend(regression["slope"]),
        }

    # Add trend fields to every record
    return [
        {**r, **trends[r["ISO_A3"]]}
        for r in data
    ]