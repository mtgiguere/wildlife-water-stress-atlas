# Adding Species & Stressors — A Guide for Ecologists

*You do not need to be a programmer to use this.* This guide explains, in plain
language, how the atlas lets you add the animals **and** the environmental
pressures you study, and — importantly — **exactly what the math does** with the
numbers you provide, so you can trust (and defend) what appears on the map.

If you just want the field-by-field reference, see
[`src/wildlife_water_stress_atlas/config/species_plugins/README.md`](../src/wildlife_water_stress_atlas/config/species_plugins/README.md)
and
[`.../stressor_plugins/README.md`](../src/wildlife_water_stress_atlas/config/stressor_plugins/README.md).
This document is the *why and how* behind those.

---

## 1. What the atlas does

For each species, the atlas takes **where the animal has been recorded** (GBIF
occurrence points) and measures, at each point, how close it is to the things
that help or harm it — water, roads, human settlements, and (soon) anything else
you define. It turns each of those into a **0–1 stress score**, then combines
them into a single **cumulative stress** number you can compare across species
and across space. Green = low, red = high.

## 2. The big idea: species and stressors are *files*, not code

Everything you'd want to change lives in small **JSON files** — plain text you
can edit in any text editor. Adding a species is adding one file. Attaching a
pressure to that species is adding a few lines to it. The program discovers your
file automatically the next time it runs, checks it for mistakes, and — if
something's wrong — **skips just that one file and tells you what's wrong**,
rather than breaking everything.

You never touch the scoring code. The code already knows how to score three
**kinds** of pressure (below); your job is to describe *which* pressures affect
*your* animal and *how strongly*.

---

## 3. The three kinds of stressor

Every pressure falls into one of three **kinds**. The kind decides the *shape* of
the math; you only supply the numbers.

| Kind | Rule of thumb | Score is driven by | Examples |
|---|---|---|---|
| **hazard** | *Closer is worse* | **proximity** to the feature | roads, settlements, mines, fences |
| **resource** | *Closer is better* | **distance** from the feature (far = stressed) | water, forage |
| **ambient** | *It's just there* | a **measured value** (no distance) | temperature, pesticide load, salinity, air pollution |

- **water** is a *resource*: an animal **far** from water is stressed.
- **roads** and **settlements** are *hazards*: an animal **near** them is stressed.
- A future **pesticide** or **heat** layer would be *ambient*: you'd feed it a
  measured value, not a distance.

Because the code owns each kind's formula, **adding a new stressor of an existing
kind takes no new code** — just a small plugin file declaring its name and kind.

---

## 4. The three numbers you set (and what they do)

For a species' stressor you provide up to three things. Here's what each one
*physically means* and how it changes the picture on the map.

### `sensitivity` — "how much does *this animal* care?" (0.0 – 1.0)
A multiplier on the whole score. `1.0` = fully affected; `0.0` = **immune** (the
stressor is switched off for this species, and the math short-circuits to zero).
A flamingo has `road sensitivity ≈ 0`; a frog, which dies on roads, is high.
*Two species can share the same stressor and be affected completely differently —
that's this number.*

### `threshold_m` — "how far does the effect reach?" (metres)
The distance at which the effect runs out.
- For a **hazard** (roads): beyond `threshold_m` there is **no threat** (score 0);
  inside it, the threat grows smoothly the closer you get.
- For a **resource** (water): at `threshold_m` the animal is **maximally stressed**
  (score 1); closer than that, stress eases toward 0 at the water's edge.

### `class_weights` — "which *types* of the feature are worse?" (0.0 – 1.0 each)
Not all roads (or towns) are equal. A motorway is deadlier than a footpath; a
city looms larger than a hamlet. You give each class a weight. `0.0` means *that
class poses no threat to this animal* (e.g. a footpath to an elephant). Water
uses `type_weights` in the same spirit — how *reliable* each water type is
(a permanent lake vs a seasonal pan).

---

## 5. What the algorithm actually computes

Here is the whole calculation, in words and in numbers. Nothing is hidden.

### Step A — score each stressor, 0 to 1

**Hazard (roads, settlements):**
```
score = sensitivity × class_weight × (1 − distance / threshold_m)
```
…clamped to 0 at or beyond the threshold, and 0 for an immune species.
*Worked example — a frog 200 m from a motorway, threshold 1000 m, frog road
sensitivity 0.8, motorway weight 1.0:*
`0.8 × 1.0 × (1 − 200/1000) = 0.8 × 0.8 = 0.64` → fairly high road stress.

**Resource (water):**
```
score = min(distance / threshold_m, 1.0)
```
*Worked example — an elephant 150 km from water, threshold 300 km:*
`min(150/300, 1) = 0.5` → moderate water stress. At 300 km+ it's 1.0 (maxed).

**Ambient (e.g. pesticide):**
```
score = sensitivity × clamp( (value − low) / (high − low), 0, 1 )
```
i.e. a straight ramp from `low` (no effect) to `high` (full effect).

### Step B — "no data" is **not** "no stress"

If we have **no measurement** for a stressor at a point (say we lack settlement
data for that region), that stressor is marked **uncovered** and is simply left
out of the combination — it is *never* silently counted as 0. A truly 0 score
("we measured, and there's no pressure here") is different from "we don't know,"
and the atlas keeps them separate. This matters for honesty: an area shouldn't
look safe just because we haven't looked.

### Step C — combine into one cumulative score (**noisy-OR**)

The per-stressor scores are combined with one fixed formula — **noisy-OR**:
```
cumulative = 1 − (1 − s₁) × (1 − s₂) × (1 − s₃) × …   (over the covered stressors)
```
Think of it as **"death by a thousand cuts."** Each stressor is a chance of harm;
the formula asks *"what's the chance at least one gets you?"* Properties that make
it the right choice:
- It **never exceeds 1** and never dilutes — adding a stressor can only *raise*
  the total, never average it down.
- Two moderate pressures (say 0.5 and 0.5) combine to **0.75**, not 0.5 —
  cumulative pressure is worse than either alone.
- Because *every* species uses the *same* combine formula, the final numbers are
  **comparable across species**. (You set the per-stressor weights; you do **not**
  change the combine formula — that's deliberate, so a "0.7" means the same thing
  for a frog and an elephant.)

You'll see this on the map's **STRESS** view: one dot per occurrence, coloured by
its cumulative score, with a hover tooltip showing the per-stressor breakdown.

---

## 6. Walkthrough: a frog biologist tunes and extends the model

Say you study the **Painted Reed Frog** (*Hyperolius marmoratus*).

### 6a. Tune an existing stressor (works immediately)
Open `config/species_plugins/hyperolius_marmoratus.json`. In its `stressors`
list you'll find `water`, `roads`, `settlements`. To say "this frog is *extremely*
water-dependent and can't stray far," lower its water `threshold_m` (e.g. from
2000 to 1500 — now it hits max stress closer to water). To reflect road
mortality, raise the `roads` `sensitivity`. Save. Add a `rationale` sentence with
your source. That's it — the next run re-scores the frog everywhere.

### 6b. Add a brand-new stressor type (new *kind of pressure*)
Suppose you want an **agriculture** pressure (frogs near cropland face pesticide
runoff). Two small steps:

1. **Declare the stressor type** — create
   `config/stressor_plugins/agriculture.json`:
   ```json
   { "stressor_id": "agriculture", "name": "Agriculture", "kind": "hazard" }
   ```
   By choosing `"kind": "hazard"` you get the proximity-to-cropland math **for
   free** — no code.

2. **Attach it to the frog** — add to the frog's `stressors` list:
   ```json
   { "stressor_id": "agriculture", "sensitivity": 0.7,
     "params": { "threshold_m": 3000, "class_weights": { "cropland": 1.0, "pasture": 0.4 } },
     "source": "Smith et al. 2021", "validated": false }
   ```

Now the engine will score and combine `agriculture` alongside water/roads/
settlements automatically, and the map's controls (Colour-by, Scenario sliders,
legend) will show it because they're **generated from each species' stressor
list** — nothing is hardcoded.

> **The one honest caveat.** The *scoring* is automatic, but a stressor needs
> **data** to score against — for `agriculture` (a hazard), the pipeline must be
> able to measure each occurrence's distance to cropland. Existing stressors
> (water, roads, settlements) already have their data wired in. A genuinely new
> data source is the one place an engineer helps: point the ingest step at your
> dataset. The *model* is yours to define in files; hooking up a *new raw
> dataset* is the one shared step. (This is on the roadmap as a guided submission
> flow — see `docs/ARCHITECTURE.md` §11.)

---

## 7. "What if…?" — the scenario tools (no files needed)

On the **STRESS** view you can, live, **exclude** a stressor or slide its
**weight** from 100% down to 0% and watch the cumulative map re-colour instantly.
This is for asking mitigation questions — *"if we removed road pressure, how much
does frog stress fall?"* — without editing anything. It uses the same noisy-OR
math, just over the stressors you've left switched on.

---

## 8. Seeing your changes, and provenance

- **Run it:** after editing files, an engineer (or you, following the README)
  runs the export step; your new/updated scores flow to the map. The goal is a
  fast edit → see-it loop.
- **Cite your work:** every expert value can carry a `source` and a `validated`
  flag, and each species has a `rationale`. Please fill these — the atlas is a
  decision-support tool for conservation partners, and a number is only as
  trustworthy as its provenance. All current default values are *heuristic
  placeholders* awaiting exactly your kind of validation.

---

## Where to go next
- **Exact fields & rules:** the two plugin `README.md` files linked at the top.
- **Why it's built this way (the contract & the math's rationale):**
  [`docs/ARCHITECTURE.md`](ARCHITECTURE.md).
- **What's built and what's planned:** [`docs/BACKLOG.md`](BACKLOG.md).
