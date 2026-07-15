"""
test_stress_aggregation.py

Tests for Score + aggregate_stress — the cumulative multi-stressor aggregation
(docs/ARCHITECTURE.md §6). One species' 1..* per-stressor scores combine into a
single stress read-out via probabilistic union (noisy-OR):

    stress = 1 - ∏(1 - sᵢ)   over the COVERED stressors

Design decisions being pinned here:
- Cumulative, NOT worst-wins — many small stressors accumulate ("death by a
  thousand cuts"); a lone 0.2 among four must exceed 0.2.
- Coverage is honest — a stressor with no data (covered=False) is IGNORED, never
  treated as 0.0 stress. If nothing is covered, the aggregate is itself uncovered.
- Bounded [0,1], monotonic, order-independent, no dilution from a 0.0.
"""

import pytest

from wildlife_water_stress_atlas.analytics.stressors import Score, aggregate_stress

# ---------------------------------------------------------------------------
# Coverage semantics — no-data is never a fake 0
# ---------------------------------------------------------------------------


def test_empty_is_uncovered():
    result = aggregate_stress([])
    assert result == Score(value=None, covered=False)


def test_all_uncovered_is_uncovered():
    result = aggregate_stress([Score(None, False), Score(None, False)])
    assert result == Score(value=None, covered=False)


def test_uncovered_stressors_are_ignored_not_treated_as_zero():
    # One covered 0.5, one no-data: aggregate reflects only what we know.
    result = aggregate_stress([Score(0.5, True), Score(None, False)])
    assert result.covered is True
    assert result.value == pytest.approx(0.5)


def test_covered_zero_is_covered_not_uncovered():
    # We HAVE data and it says no stress — that's covered with value 0.0,
    # distinct from "no data".
    result = aggregate_stress([Score(0.0, True)])
    assert result == Score(value=0.0, covered=True)


# ---------------------------------------------------------------------------
# Cumulative noisy-OR — the core formula
# ---------------------------------------------------------------------------


def test_single_covered_passes_value_through():
    result = aggregate_stress([Score(0.4, True)])
    assert result.value == pytest.approx(0.4)
    assert result.covered is True


def test_two_stressors_combine_by_noisy_or():
    # 1 - (1-0.2)(1-0.2) = 0.36
    result = aggregate_stress([Score(0.2, True), Score(0.2, True)])
    assert result.value == pytest.approx(0.36)


def test_many_small_stressors_accumulate_beyond_worst():
    # Four 0.2s: 1 - 0.8^4 = 0.5904 — far above the worst single (0.2).
    result = aggregate_stress([Score(0.2, True)] * 4)
    assert result.value == pytest.approx(0.5904)
    assert result.value > 0.2  # NOT worst-wins — the whole point


def test_a_saturating_stressor_dominates():
    result = aggregate_stress([Score(1.0, True), Score(0.3, True)])
    assert result.value == pytest.approx(1.0)


def test_adding_a_zero_stressor_does_not_change_result():
    without = aggregate_stress([Score(0.5, True)]).value
    with_zero = aggregate_stress([Score(0.5, True), Score(0.0, True)]).value
    assert without == pytest.approx(with_zero)


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


def test_result_always_in_unit_interval():
    for scores in ([Score(0.9, True), Score(0.9, True), Score(0.9, True)], [Score(0.0, True)], [Score(1.0, True)]):
        result = aggregate_stress(scores)
        assert 0.0 <= result.value <= 1.0


def test_order_independent():
    a = aggregate_stress([Score(0.1, True), Score(0.5, True), Score(0.9, True)]).value
    b = aggregate_stress([Score(0.9, True), Score(0.1, True), Score(0.5, True)]).value
    assert a == pytest.approx(b)


def test_monotonic_adding_a_stressor_never_decreases_stress():
    base = aggregate_stress([Score(0.3, True)]).value
    more = aggregate_stress([Score(0.3, True), Score(0.4, True)]).value
    assert more >= base
