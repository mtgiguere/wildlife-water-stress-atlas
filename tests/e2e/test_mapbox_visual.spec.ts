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
});
