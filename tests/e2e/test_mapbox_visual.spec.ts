import { test, expect } from '@playwright/test';
// pngjs is bundled inside playwright-core — no extra dependency needed.
import { PNG } from 'playwright-core/lib/utilsBundle';

const APP_URL = 'http://localhost:3000';

// WHY THIS EXISTS (docs/TDD_CONTRACT.md, road-threat addendum, Blind spot B):
// ---------------------------------------------------------------------------
// The road layer once rendered at 0.4px line-width — i.e. INVISIBLE — while
// every DOM-level Playwright test stayed green (the button existed, the legend
// toggled). "No console errors" proves the layer LOADED, not that a human can
// SEE it. This test renders the app via software WebGL and asserts on pixels.
//
// The metric is floor-immune: it toggles ONLY the road backbone layer on/off
// and counts how many pixels change. That isolates the backbone's painted
// footprint from the basemap and the threat dots. Measured on this renderer:
//
//   healthy (line-width 1.4–4px): ~51k–54k changed px
//   broken  (line-width 0.4px):   ~21k changed px   <-- the historical bug
//
// A threshold of 35k sits cleanly between the two.
const MIN_BACKBONE_FOOTPRINT = 35000;

// Settlement points (cities & towns) painted in the SETTLEMENTS view. Measured
// on this renderer over the pinned camera: ~13k changed px when painting,
// ~0 if the layer silently fails to load. Threshold sits well between.
const MIN_SETTLEMENT_POINTS_FOOTPRINT = 6000;

// Cumulative-stress dots (STRESS view). Fed by a DENSE inline fixture (156 pts)
// injected into the map source, so this guard needs no generated data file — it
// runs anywhere the app + SwiftShader do. The dense grid + glow-hidden dot layer
// makes the real signal (paint / red→green recolor) measure ~5k–15k changed px,
// while SwiftShader's irreducible full-canvas basemap dither is ~750px. 2500 sits
// well above the noise and well below the smallest real signal.
const MIN_STRESS_FOOTPRINT = 2500;

// Per-pixel diff threshold for the STRESS tests. A stress recolor is a large
// per-pixel change (red→green ≈ 400+ summed RGB); this drops sub-threshold jitter.
const STRESS_PIXEL_THRESH = 90;

// A dense inline stress FeatureCollection covering the pinned camera (a 12×13
// grid = 156 points). Dense on purpose: the dot-recolor signal must dwarf
// SwiftShader's full-canvas basemap dither (~750px). Injected via
// map.getSource('stress-aggregate').setData(...) — the robust way to guard the
// frontend without depending on gitignored dev data.
function stressGrid(props) {
  return {
    type: 'FeatureCollection',
    features: Array.from({ length: 156 }, (_, i) => ({
      type: 'Feature',
      properties: { species: 'Test', year: 2020, ...props },
      geometry: { type: 'Point', coordinates: [31 + (i % 12) * 0.5, -5 + Math.floor(i / 12) * 0.45] },
    })),
  };
}

// High aggregate (red) but low roads (green) so the per-stressor toggle recolors.
const STRESS_FIXTURE = stressGrid({ stress_aggregate: 0.85, stress_water: 0.7, stress_roads: 0.08, stress_settlements: 0.2 });

// Roads DOMINATES (0.9), water/settlements negligible: the full total is red, but
// excluding/zeroing roads collapses it to green — a large, unambiguous recolor.
const SCENARIO_FIXTURE = stressGrid({ stress_aggregate: 0.91, stress_water: 0.05, stress_roads: 0.9, stress_settlements: 0.05 });

// Camera pinned over road/settlement-dense East/Central Africa so the
// measurement does not depend on where the fly-to animation happens to land.
const PINNED = { center: [34, -2] as [number, number], zoom: 6 };

async function waitForMapReady(page) {
  await page.waitForSelector('#loading', { state: 'detached', timeout: 30000 });
}

// Count pixels that differ meaningfully between two PNG screenshots.
function changedPixels(bufA: Buffer, bufB: Buffer, thresh = 30): number {
  const a = PNG.sync.read(bufA);
  const b = PNG.sync.read(bufB);
  let changed = 0;
  for (let i = 0; i < a.data.length; i += 4) {
    const d =
      Math.abs(a.data[i] - b.data[i]) +
      Math.abs(a.data[i + 1] - b.data[i + 1]) +
      Math.abs(a.data[i + 2] - b.data[i + 2]);
    if (d > thresh) changed++;
  }
  return changed;
}

async function setLayerVisible(page, id: string, visible: boolean) {
  const ok = await page.evaluate(
    ([id, visible]) => {
      try {
        // `map` is a top-level global in apps/mapbox/js/app.js (classic script).
        // eslint-disable-next-line no-undef
        map.setLayoutProperty(id as string, 'visibility', visible ? 'visible' : 'none');
        return true;
      } catch (e) {
        return String(e);
      }
    },
    [id, visible] as const,
  );
  expect(ok, `could not toggle layer ${id} — is the map global available?`).toBe(true);
}

test.describe('Mapbox app — WebGL visual smoke test', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(APP_URL);
    await waitForMapReady(page);
  });

  test('software WebGL is actually active (guards a black-canvas false pass)', async ({ page }) => {
    const version = await page.evaluate(() => {
      const c = document.createElement('canvas');
      const gl = c.getContext('webgl') || c.getContext('experimental-webgl');
      return gl ? (gl as WebGLRenderingContext).getParameter((gl as WebGLRenderingContext).VERSION) : null;
    });
    expect(version, 'WebGL context missing — run with SwiftShader args via playwright.visual.config.ts').toBeTruthy();
  });

  test('road backbone paints a visible footprint in ROADS view', async ({ page }) => {
    await page.locator('.species-btn', { hasText: 'Painted Reed Frog' }).click();
    await page.locator('.view-btn', { hasText: 'ROADS' }).click();
    await page.waitForTimeout(3500);

    // Isolate the backbone: hide the threat dots/glow so the toggle-diff measures
    // only the road line, not the occurrence points drawn in the same view.
    await setLayerVisible(page, 'threats-dot', false);
    await setLayerVisible(page, 'threats-glow', false);

    await page.evaluate((p) => map.jumpTo(p), PINNED);
    await page.waitForTimeout(3000);

    const withBackbone = await page.locator('#map canvas').screenshot();
    await setLayerVisible(page, 'roads-backbone-line', false);
    await page.waitForTimeout(1500);
    const withoutBackbone = await page.locator('#map canvas').screenshot();
    await setLayerVisible(page, 'roads-backbone-line', true);

    const footprint = changedPixels(withBackbone, withoutBackbone);
    expect(
      footprint,
      `road backbone footprint ${footprint}px is below ${MIN_BACKBONE_FOOTPRINT}px — ` +
        'the road network is effectively invisible (the 0.4px-width regression class)',
    ).toBeGreaterThan(MIN_BACKBONE_FOOTPRINT);
  });

  test('settlement points paint a visible footprint in SETTLEMENTS view', async ({ page }) => {
    // Lion has dense settlement-threat data over the pinned East-Africa camera.
    await page.locator('.species-btn', { hasText: 'Lion' }).click();
    await page.locator('.view-btn', { hasText: 'SETTLEMENTS' }).click();
    await page.waitForTimeout(3500);

    // Isolate the settlement points: hide the threat dots/glow so the toggle-diff
    // measures only the city/town context layer, not the occurrence points.
    await setLayerVisible(page, 'settlement-threats-dot', false);
    await setLayerVisible(page, 'settlement-threats-glow', false);

    await page.evaluate((p) => map.jumpTo(p), PINNED);
    await page.waitForTimeout(3000);

    const withPoints = await page.locator('#map canvas').screenshot();
    await setLayerVisible(page, 'settlements-points-layer', false);
    await page.waitForTimeout(1500);
    const withoutPoints = await page.locator('#map canvas').screenshot();
    await setLayerVisible(page, 'settlements-points-layer', true);

    const footprint = changedPixels(withPoints, withoutPoints);
    expect(
      footprint,
      `settlement points footprint ${footprint}px is below ${MIN_SETTLEMENT_POINTS_FOOTPRINT}px — ` +
        'the settlement layer is effectively invisible or failed to load',
    ).toBeGreaterThan(MIN_SETTLEMENT_POINTS_FOOTPRINT);
  });

  // --- STRESS view: fed by an inline fixture (no generated-data dependency) ---

  // Opens the STRESS view, injects a dense fixture, pins the camera, and hides the
  // glow layer — the blurred, semi-transparent glow re-composites
  // nondeterministically on SwiftShader and inflates the pixel-diff noise. We
  // measure the crisp dot layer instead.
  async function openStressViewWithFixture(page, fixture = STRESS_FIXTURE) {
    await page.locator('.view-btn', { hasText: 'STRESS' }).click();
    await page.waitForTimeout(1500);
    await page.evaluate((fc) => map.getSource('stress-aggregate').setData(fc), fixture);
    await page.evaluate((p) => map.jumpTo(p), { center: [34.5, -2], zoom: 6 });
    await setLayerVisible(page, 'stress-aggregate-glow', false);
    await page.waitForTimeout(2500);
  }

  test('cumulative-stress dots paint in the STRESS view', async ({ page }) => {
    await openStressViewWithFixture(page);

    const withDots = await page.locator('#map canvas').screenshot();
    await setLayerVisible(page, 'stress-aggregate-dot', false);
    await page.waitForTimeout(1000);
    const withoutDots = await page.locator('#map canvas').screenshot();
    await setLayerVisible(page, 'stress-aggregate-dot', true);

    const footprint = changedPixels(withDots, withoutDots, STRESS_PIXEL_THRESH);
    expect(
      footprint,
      `stress dots footprint ${footprint}px is below ${MIN_STRESS_FOOTPRINT}px — STRESS view not painting`,
    ).toBeGreaterThan(MIN_STRESS_FOOTPRINT);
  });

  test('per-stressor toggle recolors the STRESS dots', async ({ page }) => {
    await openStressViewWithFixture(page);

    const totalShot = await page.locator('#map canvas').screenshot();
    // Fixture is high aggregate (red) but low roads (green): switching must recolor.
    await page.locator('.stressby-btn', { hasText: 'Roads' }).click();
    await page.waitForTimeout(1000);
    const roadsShot = await page.locator('#map canvas').screenshot();

    const recolor = changedPixels(totalShot, roadsShot, STRESS_PIXEL_THRESH);
    expect(recolor, `toggle recolor changed only ${recolor}px — the colour-by toggle isn't recoloring`).toBeGreaterThan(MIN_STRESS_FOOTPRINT);
  });

  test('excluding a dominant stressor re-aggregates the cumulative total (scenario toggle)', async ({ page }) => {
    // Roads-dominant fixture: the full total is red; excluding roads must collapse
    // it toward green via the live noisy-OR recompute — a visible recolor.
    await openStressViewWithFixture(page, SCENARIO_FIXTURE);

    const withRoads = await page.locator('#map canvas').screenshot();
    await page.locator('.scenario-btn', { hasText: 'Roads' }).click();
    await page.waitForTimeout(1000);
    const withoutRoads = await page.locator('#map canvas').screenshot();

    const recolor = changedPixels(withRoads, withoutRoads, STRESS_PIXEL_THRESH);
    expect(recolor, `excluding roads changed only ${recolor}px — the scenario re-aggregation isn't recoloring`).toBeGreaterThan(MIN_STRESS_FOOTPRINT);
  });

  test('lowering a dominant stressor weight re-aggregates the total (reweight slider)', async ({ page }) => {
    // Roads-dominant fixture: dragging the roads weight to 0% must collapse the
    // red total toward green via the live noisy-OR recompute — a visible recolor.
    await openStressViewWithFixture(page, SCENARIO_FIXTURE);

    const fullWeight = await page.locator('#map canvas').screenshot();
    await page.locator('.scenario-weight[data-prop="stress_roads"]').evaluate((el: HTMLInputElement) => {
      el.value = '0';
      el.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await page.waitForTimeout(1000);
    const zeroWeight = await page.locator('#map canvas').screenshot();

    const recolor = changedPixels(fullWeight, zeroWeight, STRESS_PIXEL_THRESH);
    expect(recolor, `roads weight→0 changed only ${recolor}px — the reweight isn't re-aggregating`).toBeGreaterThan(MIN_STRESS_FOOTPRINT);
  });
});
