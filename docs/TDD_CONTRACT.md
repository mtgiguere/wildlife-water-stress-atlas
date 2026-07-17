# The TDD Contract
## Why We Do Test-Driven Development — Evidence From This Codebase

This document exists because of a deliberate experiment.

During the development of the Geo-Fluid Dynamics Engine, Claude was given significant
autonomy and explicitly allowed to use TAD (Test-After Development) instead of TDD.
The results were analyzed in a systematic retrospective. What follows is the evidence —
not theory, not best practice citations, but specific bugs, specific tests, and specific
lines of code from this project that prove why TDD is not optional.

**If you are a new Claude Code session starting work on this project: read this first.**
**If you are inclined to skip TDD "just this once": re-read this.**

---

## What TAD Looks Like (What We Did Wrong)

TAD means: design in your head → write implementation → write tests that confirm
what you just wrote → push.

The tests look fine. They pass. Coverage looks good. But something is wrong:
**the tests are asking "does this code do what I just wrote?" not "does this code do
what it SHOULD do?"** That is a completely different question.

Here is the evidence from this project.

---

## Bug #1: Column Name Drift (adoption_prob → adoption_probability)

**What happened:**

`SurvivalDiffusionModel.get_adoption_frontier()` was implemented and returned a column
named `adoption_prob`. Separately, `frontier_map.build_layer()` was implemented expecting
a column named `adoption_probability`. Both were tested individually and both passed.

When CI wired them together via the API test, it crashed:
```
ValueError: Missing required columns: ['on_frontier', 'adoption_probability']
```

**Why TAD caused it:**

I wrote `get_adoption_frontier()` and tested it knowing I named the column `adoption_prob`.
I wrote `frontier_map.build_layer()` and tested it knowing I expected `adoption_probability`.
Both tests confirmed what I just coded. Neither test specified the contract between them.

**What TDD would have done:**

Write this test first, before implementing either function:
```python
def test_frontier_output_is_consumable_by_frontier_map():
    frontier = model.get_adoption_frontier()
    # This test specifies the contract between two functions
    result = frontier_map.build_layer(frontier)
    assert result["type"] == "FeatureCollection"
```

That test would fail immediately on the first implementation attempt because the column
name would be wrong. The contract would be specified before either function was written.

---

## Bug #2: Empty DataFrame KeyError (node_classifier)

**What happened:**

`classify_nodes()` was called with an empty adoption_events DataFrame.
`pd.DataFrame([])` with an empty list produces a DataFrame with **zero columns**, not
zero rows with the expected columns. So `adoption_events["topic_id"]` raised `KeyError`.

CI output:
```
KeyError: 'topic_id'
modules/gravity_engine/processing/node_classifier.py:87
```

**Why TAD caused it:**

I wrote `_compute_county_stats()` and tested it with non-empty adoption_events.
The happy path worked. I never asked "what does an empty adoption_events look like?"
because I was thinking about the implementation I just wrote, not the contract.

**What TDD would have done:**

Before writing a single line of `_compute_county_stats()`, write this test:
```python
def test_classify_nodes_with_no_adopters_for_topic():
    """Topic 2 has no adopters — function must not crash."""
    ae = _make_adoption_events({}, topic_id=2)  # empty dict → empty DataFrame
    result = classify_nodes(panel, out_c, in_c, fips_index, ae, topic_id=2)
    assert result["node_type"].isin(NODE_TYPES).all()
```

Watch it fail. Then write the guard. The bug never ships.

---

## Bug #3: FIPS Sort Order (The Comment That Lied)

**What happened:**

In `test_spatial_weights.py`, the test comment read:
```python
fips_order = sorted(panel["fips"].unique())
sup_vec = np.array(support)   # ordered: 29169, 29183, 29189 alphabetically
```

The comment said alphabetically. The code used `support` which was in **insertion order**
`[29169, 29189, 29183]`. The test had been wrong since it was written. CI found it:

```
assert np.float64(0.15000000000000002) < 1e-06
```

**Why TAD caused it:**

I wrote the test knowing the implementation sorts alphabetically. I wrote the assertion
knowing what I intended. I wrote the comment to remind myself. Then I wrote the wrong code
in the assertion because I was thinking about `support` in the order I created it, not in
the order the implementation would use it.

**What TDD would have done:**

Write the test first with an explicit mapping that makes the expected output unambiguous:
```python
fips_to_support = {"29169": 0.3, "29189": 0.6, "29183": 0.9}
fips_order = sorted(panel["fips"].unique())
sup_vec = np.array([fips_to_support[f] for f in fips_order])
```

The explicit mapping cannot lie. The comment can.

---

## Bug #4: The np.True_ Identity Check

**What happened:**

Three tests in `test_rolloff.py` failed with:
```
assert np.True_ is True   →   AssertionError
assert np.False_ is False →   AssertionError
```

**Why TAD caused it:**

I was thinking about boolean logic when I wrote the tests. I knew the implementation
would produce True/False values. I used `is True` because that's what you write when
you're thinking "this should be True." I wasn't thinking about what pandas actually
returns — numpy scalars, not Python singletons.

**What TDD would have done:**

If you write the test first and actually RUN it to confirm it fails (the RED step),
you immediately discover that the implementation doesn't exist yet, and you think carefully
about what the assertion syntax should be. The RED step forces you to think about the
assertion before the implementation.

The correct pattern — never use `is True` or `is False` with pandas/numpy values:
```python
assert result["is_false_bastion"]        # truthiness check — works with np.bool_
assert not result["is_false_bastion"]
assert result["is_false_bastion"] == True  # value equality — not identity
```

---

## Bug #5: Eight Hollow Tests That Cannot Fail

**What happened:**

The retrospective analysis found 8 tests with conditional guards that let the
core assertion bypass entirely. The test runs, it passes, coverage is counted.
But the thing being tested is never actually verified.

Example:
```python
def test_wombling_value_equals_support_difference():
    """With support [0.8, 0.3], wombling_value should be 0.5."""
    ...
    if len(result) > 0:           # ← hollow guard
        assert abs(result.iloc[0]["wombling_value"] - 0.5) < 1e-6
```

If `result` is empty — because the adjacency detection has a bug — this test passes.
The bug ships. The test reported 100% on this line.

**Why TAD caused it:**

I knew the implementation sometimes returns empty results for edge cases. I added the
guard to avoid flaky tests. But I was protecting the implementation from the test,
which is exactly backwards. Tests are supposed to catch bugs. Guards prevent that.

**What TDD would have done:**

Write the test first. It specifies that for two adjacent polygons with supports 0.8
and 0.3, the output must be non-empty and must have wombling_value ≈ 0.5. Full stop.
```python
def test_wombling_value_equals_support_difference():
    gdf = _make_adjacent_counties()
    W = np.array([[0, 1], [1, 0]], dtype=float)
    support = pd.Series({"A": 0.8, "B": 0.3})
    result = lattice_wombling(gdf, support, W, ["A", "B"])
    assert len(result) == 1, "Two adjacent counties must produce one boundary"
    assert abs(result.iloc[0]["wombling_value"] - 0.5) < 1e-6
```

No guard. If the function doesn't detect the boundary, the test fails loudly.

---

## What 100% Coverage Actually Means

Coverage tells you which lines were **executed**. It does not tell you which behaviors
were **verified**.

Example: `compute_ifs(0.5, 0.5)` achieves 100% line coverage of `compute_ifs`.
It does not test:
- `compute_ifs(float('nan'), 0.5)` → returns NaN silently
- `compute_ifs(-0.1, 0.5)` → `np.clip` handles it, but was that specified?
- `compute_ifs(0.0, 0.5)` → geometric mean property, verified?
- `compute_ifs(1.0, 1.0)` → what does full-danger look like?

86% coverage with TAD ≠ 86% of behavior verified.
70% coverage with TDD > 86% coverage with TAD.

The number that matters is: **what fraction of the behavioral contract is specified
in tests before the code is written?**

---

## The Actual TDD Discipline — Not Theory, Instructions

### The Sequence (Non-Negotiable)

```
1. Write one test. It must describe behavior you want, not code you will write.
2. Run the test. CONFIRM IT FAILS (RED). If it passes, the test is wrong.
3. Write the minimum code to make it pass. Not more.
4. Run the test. CONFIRM IT PASSES (GREEN).
5. Refactor if needed. Run tests again.
6. Commit. The commit message describes the behavior added, not the code written.
7. Repeat.
```

The RED step is not optional. If you skip it, you are doing TAD.

### Red Flag Signals — Stop and Fix Before Proceeding

If you find yourself writing any of the following, you are not doing TDD:

```python
# RED FLAG 1: Skip guard without confirmed implementation
pytest.skip("not implemented")  # wrong — this is the TDD stub; DON'T add the code yet

# RED FLAG 2: Conditional guard hiding assertion
if len(result) > 0:
    assert something  # wrong — design fixture so result is always non-empty

# RED FLAG 3: Seed-specific assertion
rng = np.random.default_rng(42)  # wrong — use property-based testing for algorithms
assert some_trend_holds()         #        or construct data so the property is guaranteed

# RED FLAG 4: Identity check with pandas/numpy
assert result["col"] is True     # wrong — always
assert result["col"] is False    # wrong — always

# RED FLAG 5: Test name that describes implementation
def test_calls_psycopg2_connect():  # wrong — tests describe behavior not mechanism
def test_uses_groupby():

# RED FLAG 6: Test written after the function it tests
# (you wrote parse(), then wrote test_parse() — that is TAD)
```

### What a Good Test Looks Like

A good test is written **before the implementation** and specifies:
1. Given this specific, deterministic input
2. When this function is called
3. Then this exact output is produced (or this exact error is raised)

```python
def test_adoption_year_is_first_crossing():
    """Specifies: the adoption year is the FIRST year support crosses the threshold.
    Not the last. Not any year. The first."""
    support = pd.DataFrame({
        "fips": ["29169"] * 4,
        "topic_id": [1] * 4,
        "year": [2012, 2016, 2020, 2024],
        "support_pct": [0.40, 0.48, 0.52, 0.58],
    })
    events = compute_adoption_events(support, topic_id=1, threshold_pct=0.50)
    row = events[events["fips"] == "29169"].iloc[0]
    assert row["first_adoption_year"] == 2020  # not 2024; not 2016
```

This test was written before the implementation. It fails before the implementation.
It specifies exactly one thing. It has no guards. It has no seeds. It has one expected value.

### Using Hypothesis for Algorithmic Code

For mathematical functions (IFS, CCI, spatial weights, survival probability),
seed-based testing is always wrong. Use Hypothesis:

```python
from hypothesis import given, strategies as st

@given(
    cci=st.floats(0.0, 1.0, allow_nan=False),
    ili=st.floats(0.0, 1.0, allow_nan=False),
)
def test_ifs_always_in_0_1(cci, ili):
    """Property: IFS is always in [0, 1] for valid inputs."""
    assert 0.0 <= compute_ifs(cci, ili) <= 1.0
```

Hypothesis will find the edge cases you didn't think of.

---

## The Conversation You Will Have

At some point you will think:

> "This is a simple function. I know exactly what it does. Writing the test first
> is just busywork. I'll write the test after — it'll be faster."

That is exactly what happened in this project. Every time. The function that felt
simple had a bug. The test written after documented the bug. CI found it later.

The bugs above were not from complex functions. They were from:
- A column being named `adoption_prob` instead of `adoption_probability`
- An empty DataFrame having zero columns instead of zero rows
- A comment that said "alphabetically" while the code did insertion order
- A boolean being `np.True_` instead of `True`

None of these required deep thinking to get right. All of them required writing the
test first so the contract was specified before the code was written.

---

## The Standing Instruction for This Project

**For every new function added to this codebase:**

1. Write the test in the test file. Run pytest. Confirm RED.
2. Write the implementation. Run pytest. Confirm GREEN.
3. Then and only then, open a PR.

**For every bug fix:**
1. Write a test that reproduces the bug. Confirm RED.
2. Fix the bug. Confirm GREEN.
3. The test stays in the suite permanently.

**For every edge case you think of while implementing:**
1. Stop implementing. Write the edge case test first.
2. Run it. Confirm RED (or discover the implementation already handles it).
3. Continue.

This is not about discipline or methodology. This is about the specific, documented
bugs in this codebase that would not exist if we had done this.

---

## Summary of Evidence

| Bug | How Found | TDD Prevention |
|-----|-----------|----------------|
| `adoption_prob` vs `adoption_probability` | CI failure after PR merge | Interface contract test written before either function |
| Empty DataFrame KeyError in node_classifier | CI failure | Test with empty adoption_events before implementation |
| FIPS sort order mismatch | CI failure | Explicit mapping in test rather than `np.array(support)` |
| `np.True_ is True` assertion failure | CI failure | RED step forces you to think about assertion syntax |
| 8 hollow tests with conditional guards | Manual retrospective | No guards — design fixture to guarantee non-empty result |
| 20+ seed-dependent assertions | Manual retrospective | Hypothesis property tests |
| Column naming inconsistency (node types) | Manual retrospective | Enum defined in test file before any implementation |
| Geofabrik layer name `gis_osm_roads_free_1` | Real continental fetch produced 0 roads | Integration test against a real (small) download |
| Road layer rendered at 0.4px — invisible | Human noticed on the live map | Visual smoke test via software-WebGL screenshot |

None of these were caught by the tests. They were caught by CI or by a human reviewing.
**Tests that don't catch bugs are documentation, not verification.**

---

*This document was written after the fact as an honest retrospective.*
*Its purpose is to prevent future sessions from repeating the same patterns.*
*The evidence in it is real. The bugs were real. The fixes were real.*
*Do the work in the right order.*

---

## Addendum — Road Threat Layer (2026-06)

The road-threat / human-pressure feature was built with strict TDD on the
Python side and it held: the analytics (`threat_scoring`, threats ingest,
backbone export, the major-roads filter) were all genuine RED→GREEN, and the
scoring was correct the whole way. But the session exposed **two blind spots
the discipline above does not cover** — both bugs escaped green test suites and
were caught only by running against reality.

### Blind spot A: external-format assumptions (a live TAD specimen)

`fetch_road_data.py` assumed the Geofabrik roads layer was named
`gis_osm_roads_free_1`. The unit test *wrote its own fixture with that same
name and read it back* — so it passed green while disagreeing with reality (the
real layer is `gis_osm_roads_free`, no `_1`). Every real download silently
produced zero roads.

This is Bug #1's pattern in new clothing: **the test confirmed what the code
assumed, not what was true.** A self-referential fixture can never catch an
assumption about an *external* data format. Only an integration test that pulls
a real (small) file can.

> **Rule:** When code parses an external format (a download, an API response, a
> file schema), a unit test with a self-authored fixture proves your parser is
> self-consistent — nothing more. Add an `@pytest.mark.integration` test against
> one real sample.

### Blind spot B: visual / rendering behavior

The Mapbox layer was added correctly, threw no console errors, and passed every
DOM-level Playwright test (button exists, legend toggles) — yet drew at 0.4px
line-width, i.e. **invisible** at the default zoom. "No console errors" is
necessary but not sufficient: it proves the layer *loaded*, not that a human can
*see* it. Both visual regressions (invisible roads, then roads overpowering the
points) were caught by the user, not the suite.

> **Rule:** DOM assertions are not visual verification. For a WebGL map, render
> it (software WebGL / SwiftShader works headless) and assert on the pixels, or
> at minimum eyeball a screenshot before claiming a visualization "works."

### The meta-lesson

The original evidence table's refrain — *"None of these were caught by the
tests; they were caught by CI or by a human"* — held again, with two new
"realities" added to the list: **real external data sources** and **real
rendering**. TDD remains excellent on its home turf (pure/algorithmic Python).
Its coverage stops at the Python boundary; that boundary is exactly where these
two bugs lived. The follow-ups (integration test for the roads download; a
SwiftShader visual smoke test) are tracked in the project bible.

## Addendum — "Green ≠ Verified" (2026-07)

Two incidents this cycle sharpened a single theme already present in *Bug #5:
Eight Hollow Tests That Cannot Fail* — **a passing test proves nothing until you
have seen it fail for the right reason.**

### Blind spot C: a pixel-diff guard below the noise floor

The STRESS-view SwiftShader guards (Blind spot B's own remedy) asserted that a
recolor changed `> 200` pixels. But SwiftShader's frame-to-frame basemap dither
is ~300–750px on a full-canvas diff — *above* that threshold. So the guard was
**hollow**: it passed whether or not the app actually recolored. It was caught
only because a RED demo (disabling the recompute) *still passed* — the failing
step refused to fail.

> **Rule:** a pixel-diff / threshold guard is not trustworthy until you have
> *measured* both the real signal and the noise floor and shown the threshold
> sits provably between them. The fix here: make the signal dominate (dense
> fixture, isolate the crisp layer, raise the per-pixel delta) so signal ≫ noise,
> then set the threshold in the gap. "It passed" is not a measurement.

### The systematic detector: mutation testing

Blind spot C is the manual version of a general question — *which of my green
tests would still pass if the code were wrong?* Mutation testing answers it
mechanically: it perturbs the source and checks whether the suite fails. A
**surviving mutant is a RED that never got written.**

A scoped audit of the scoring + validation core (2026-07) bore this out:
- `analytics/stressors.py` — 136/152 killed; the one real gap was `AmbientStressor`
  tested only with `low=0.0` (so `−` vs `+` couldn't be told apart). Fixed.
- `config/species.py` — surfaced **6 real validation-boundary gaps** (`<= 0` vs
  `== 0`; water weights' strict `> 0`; exact key-set match vs subset; negative vs
  zero). All were "tested one bad value but not the boundary/other direction."
  Fixed. This is the field-drift bug class this whole document exists for.
- `analytics/stress_engine.py` — effectively clean (one trivial `frozen=` mutant).

> **Rule:** run a scoped mutation audit on correctness-critical Python (scoring,
> validation) when it changes — not as a CI gate (it's slow and equivalent
> mutants can never die), but as a periodic hunt for hollow tests. Read every
> survivor: kill the real ones with a test, and satisfy yourself the rest are
> genuinely equivalent.
>
> **Tooling caveat (Windows):** `mutmut` 3.x is WSL-only. `mutatest` 3.1.0 works
> but (a) needs a one-line Py3.12 fix (`random.sample` on a `set`) and (b) pins
> `coverage < 6`, which breaks `pytest-cov`. Run it in an isolated env, or drop to
> `coverage 5.x` for the audit window and restore `coverage 7` (+ confirm the
> suite) afterward. Do **not** add it to the project's dependencies.

### The meta-lesson, restated

The refrain is now: green is a *claim*, not *evidence*. The evidence is the
observed RED — whether from the classic RED-first step, a deliberate break of a
visual guard, or a mutant that your suite failed to kill.
