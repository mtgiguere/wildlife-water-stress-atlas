import { test, expect } from '@playwright/test';

const APP_URL = 'http://localhost:3000';

// Wait for the Mapbox loading overlay to disappear — map + data are ready
async function waitForMapReady(page) {
  await page.waitForSelector('#loading', { state: 'detached', timeout: 30000 });
}

test.describe('Wildlife Water Stress Atlas — Mapbox App', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto(APP_URL);
    await waitForMapReady(page);
  });

  // ---------------------------------------------------------------------------
  // Page structure
  // ---------------------------------------------------------------------------

  test('page title is correct', async ({ page }) => {
    await expect(page).toHaveTitle('Wildlife Water Stress Atlas');
  });

  test('atlas title is visible in panel', async ({ page }) => {
    await expect(page.locator('.atlas-title')).toContainText('WILDLIFE');
  });

  test('phase label is visible', async ({ page }) => {
    await expect(page.locator('.atlas-label')).toContainText('Phase 1');
  });

  test('map canvas renders', async ({ page }) => {
    await expect(page.locator('#map canvas')).toBeVisible();
  });

  test('panel footer shows data sources', async ({ page }) => {
    await expect(page.locator('#panel-footer')).toContainText('GBIF');
    await expect(page.locator('#panel-footer')).toContainText('GLWD v2');
  });

  // ---------------------------------------------------------------------------
  // Species selector
  // ---------------------------------------------------------------------------

  test('all 11 species buttons are rendered', async ({ page }) => {
    const buttons = page.locator('.species-btn');
    await expect(buttons).toHaveCount(11);
  });

  test('African Elephant is selected by default', async ({ page }) => {
    const activeBtn = page.locator('.species-btn.active');
    await expect(activeBtn).toContainText('African Elephant');
  });

  test('clicking Plains Zebra makes it active', async ({ page }) => {
    await page.locator('.species-btn', { hasText: 'Plains Zebra' }).click();
    await expect(
      page.locator('.species-btn.active')
    ).toContainText('Plains Zebra');
  });

  test('switching species updates legend label', async ({ page }) => {
    await page.locator('.species-btn', { hasText: 'Nile Crocodile' }).click();
    await expect(page.locator('#legend-species-label')).toContainText('Nile Crocodile');
  });

  test('species buttons show tier labels', async ({ page }) => {
    await expect(
      page.locator('.species-btn', { hasText: 'African Elephant' }).locator('.species-tier')
    ).toContainText('Megafauna');
  });

  // ---------------------------------------------------------------------------
  // View toggle
  // ---------------------------------------------------------------------------

  test('POINTS view button is active by default', async ({ page }) => {
    await expect(page.locator('.view-btn.active')).toContainText('POINTS');
  });

  test('all five view buttons fit within the panel (STRESS not clipped)', async ({ page }) => {
    const panel = await page.locator('#panel').boundingBox();
    const buttons = page.locator('.view-btn');
    await expect(buttons).toHaveCount(5);
    for (let i = 0; i < 5; i++) {
      const label = (await buttons.nth(i).innerText()).trim();
      const box = await buttons.nth(i).boundingBox();
      expect(box, `view button "${label}" has no box`).not.toBeNull();
      // Every button's right edge must sit within the panel — else it's clipped
      // off-panel (the STRESS-button overflow: #view-toggle had no flex-wrap).
      expect(
        box!.x + box!.width,
        `view button "${label}" overflows the panel (right edge ${Math.round(box!.x + box!.width)} > panel ${Math.round(panel!.x + panel!.width)})`,
      ).toBeLessThanOrEqual(panel!.x + panel!.width + 1);
    }
  });

  test('clicking COUNTRIES makes it active', async ({ page }) => {
    await page.locator('.view-btn', { hasText: 'COUNTRIES' }).click();
    await expect(page.locator('.view-btn.active')).toContainText('COUNTRIES');
  });

  test('clicking POINTS after COUNTRIES restores POINTS as active', async ({ page }) => {
    await page.locator('.view-btn', { hasText: 'COUNTRIES' }).click();
    await page.locator('.view-btn', { hasText: 'POINTS' }).click();
    await expect(page.locator('.view-btn.active')).toContainText('POINTS');
  });

  // ---------------------------------------------------------------------------
  // Road threat view
  // ---------------------------------------------------------------------------

  test('ROADS view button is present', async ({ page }) => {
    await expect(page.locator('.view-btn', { hasText: 'ROADS' })).toBeVisible();
  });

  test('clicking ROADS makes it active', async ({ page }) => {
    await page.locator('.view-btn', { hasText: 'ROADS' }).click();
    await expect(page.locator('.view-btn.active')).toContainText('ROADS');
  });

  test('road threat legend is hidden by default', async ({ page }) => {
    await expect(page.locator('#legend-threat')).toBeHidden();
  });

  test('road threat legend appears in ROADS view', async ({ page }) => {
    await page.locator('.view-btn', { hasText: 'ROADS' }).click();
    await expect(page.locator('#legend-threat')).toBeVisible();
  });

  test('water stress legend is hidden in ROADS view', async ({ page }) => {
    await page.locator('.view-btn', { hasText: 'ROADS' }).click();
    await expect(page.locator('#legend-stress')).toBeHidden();
  });

  test('switching from ROADS back to POINTS restores the water stress legend', async ({ page }) => {
    await page.locator('.view-btn', { hasText: 'ROADS' }).click();
    await page.locator('.view-btn', { hasText: 'POINTS' }).click();
    await expect(page.locator('#legend-stress')).toBeVisible();
    await expect(page.locator('#legend-threat')).toBeHidden();
  });

  // ---------------------------------------------------------------------------
  // Settlement threat view
  // ---------------------------------------------------------------------------

  test('SETTLEMENTS view button is present', async ({ page }) => {
    await expect(page.locator('.view-btn', { hasText: 'SETTLEMENTS' })).toBeVisible();
  });

  test('clicking SETTLEMENTS makes it active', async ({ page }) => {
    await page.locator('.view-btn', { hasText: 'SETTLEMENTS' }).click();
    await expect(page.locator('.view-btn.active')).toContainText('SETTLEMENTS');
  });

  test('settlement threat legend is hidden by default', async ({ page }) => {
    await expect(page.locator('#legend-settlement')).toBeHidden();
  });

  test('settlement threat legend appears in SETTLEMENTS view', async ({ page }) => {
    await page.locator('.view-btn', { hasText: 'SETTLEMENTS' }).click();
    await expect(page.locator('#legend-settlement')).toBeVisible();
  });

  test('water stress legend is hidden in SETTLEMENTS view', async ({ page }) => {
    await page.locator('.view-btn', { hasText: 'SETTLEMENTS' }).click();
    await expect(page.locator('#legend-stress')).toBeHidden();
  });

  test('road and settlement legends are mutually exclusive', async ({ page }) => {
    await page.locator('.view-btn', { hasText: 'SETTLEMENTS' }).click();
    await expect(page.locator('#legend-settlement')).toBeVisible();
    await expect(page.locator('#legend-threat')).toBeHidden();
    await page.locator('.view-btn', { hasText: 'ROADS' }).click();
    await expect(page.locator('#legend-threat')).toBeVisible();
    await expect(page.locator('#legend-settlement')).toBeHidden();
  });

  // ---------------------------------------------------------------------------
  // Cumulative stress view
  // ---------------------------------------------------------------------------

  test('STRESS view button is present', async ({ page }) => {
    await expect(page.locator('.view-btn', { hasText: 'STRESS' })).toBeVisible();
  });

  test('clicking STRESS makes it active', async ({ page }) => {
    await page.locator('.view-btn', { hasText: 'STRESS' }).click();
    await expect(page.locator('.view-btn.active')).toContainText('STRESS');
  });

  test('cumulative stress legend is hidden by default', async ({ page }) => {
    await expect(page.locator('#legend-aggregate')).toBeHidden();
  });

  test('cumulative stress legend appears in STRESS view', async ({ page }) => {
    await page.locator('.view-btn', { hasText: 'STRESS' }).click();
    await expect(page.locator('#legend-aggregate')).toBeVisible();
  });

  test('other legends are hidden in STRESS view', async ({ page }) => {
    await page.locator('.view-btn', { hasText: 'STRESS' }).click();
    await expect(page.locator('#legend-stress')).toBeHidden();
    await expect(page.locator('#legend-threat')).toBeHidden();
    await expect(page.locator('#legend-settlement')).toBeHidden();
  });

  // ---------------------------------------------------------------------------
  // Per-stressor colour toggle (within STRESS view)
  // ---------------------------------------------------------------------------

  test('colour-by toggle is hidden outside STRESS view', async ({ page }) => {
    await expect(page.locator('#stress-colorby')).toBeHidden();
  });

  test('colour-by toggle appears in STRESS view with Total active', async ({ page }) => {
    await page.locator('.view-btn', { hasText: 'STRESS' }).click();
    await expect(page.locator('#stress-colorby')).toBeVisible();
    await expect(page.locator('.stressby-btn.active')).toContainText('Total');
  });

  test('clicking a stressor recolors: active button + legend label update', async ({ page }) => {
    await page.locator('.view-btn', { hasText: 'STRESS' }).click();
    await page.locator('.stressby-btn', { hasText: 'Roads' }).click();
    await expect(page.locator('.stressby-btn.active')).toContainText('Roads');
    await expect(page.locator('#legend-aggregate-label')).toHaveText('Road stress');
    // and back to Total
    await page.locator('.stressby-btn', { hasText: 'Total' }).click();
    await expect(page.locator('#legend-aggregate-label')).toHaveText('Cumulative stress');
  });

  // ---------------------------------------------------------------------------
  // Scenario toggles (within STRESS view) — include/exclude a stressor and
  // re-aggregate the cumulative stress live.
  // ---------------------------------------------------------------------------

  test('scenario control is hidden outside STRESS view', async ({ page }) => {
    await expect(page.locator('#stress-scenario')).toBeHidden();
  });

  test('scenario control appears in STRESS view with all stressors enabled', async ({ page }) => {
    await page.locator('.view-btn', { hasText: 'STRESS' }).click();
    await expect(page.locator('#stress-scenario')).toBeVisible();
    const buttons = page.locator('.scenario-btn');
    await expect(buttons).toHaveCount(3);
    // all three included by default
    await expect(page.locator('.scenario-btn.active')).toHaveCount(3);
  });

  test('clicking a scenario stressor toggles it off then on', async ({ page }) => {
    await page.locator('.view-btn', { hasText: 'STRESS' }).click();
    const roads = page.locator('.scenario-btn', { hasText: 'Roads' });
    await roads.click();
    await expect(roads).not.toHaveClass(/active/);
    await roads.click();
    await expect(roads).toHaveClass(/active/);
  });

  test('excluding a stressor annotates the cumulative-stress legend label', async ({ page }) => {
    await page.locator('.view-btn', { hasText: 'STRESS' }).click();
    // Coloring by Total, excluding Roads should note the exclusion.
    await page.locator('.scenario-btn', { hasText: 'Roads' }).click();
    await expect(page.locator('#legend-aggregate-label')).toContainText('Roads');
    // re-including restores the plain cumulative label
    await page.locator('.scenario-btn', { hasText: 'Roads' }).click();
    await expect(page.locator('#legend-aggregate-label')).toHaveText('Cumulative stress');
  });

  test('scenario weight sliders appear in STRESS view at 100%', async ({ page }) => {
    await page.locator('.view-btn', { hasText: 'STRESS' }).click();
    await expect(page.locator('.scenario-weight')).toHaveCount(3);
    for (const p of ['stress_water', 'stress_roads', 'stress_settlements']) {
      await expect(page.locator(`.scenario-weight[data-prop="${p}"]`)).toHaveValue('100');
    }
  });

  test('changing a scenario weight updates its displayed percentage', async ({ page }) => {
    await page.locator('.view-btn', { hasText: 'STRESS' }).click();
    const roads = page.locator('.scenario-weight[data-prop="stress_roads"]');
    await roads.evaluate((el: HTMLInputElement, v) => {
      el.value = v as string;
      el.dispatchEvent(new Event('input', { bubbles: true }));
    }, '40');
    await expect(page.locator('.scenario-weight-val[data-prop="stress_roads"]')).toHaveText('40%');
  });

  // ---------------------------------------------------------------------------
  // Year slider
  // ---------------------------------------------------------------------------

  test('year display is visible', async ({ page }) => {
    await expect(page.locator('#year-display')).toBeVisible();
  });

  test('year slider is present', async ({ page }) => {
    await expect(page.locator('#year-slider')).toBeVisible();
  });

  test('year display updates when slider moves', async ({ page }) => {
    const slider = page.locator('#year-slider');
    await slider.evaluate((el: HTMLInputElement) => {
      el.value = '2015';
      el.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await expect(page.locator('#year-display')).toHaveText('2015');
  });

  // ---------------------------------------------------------------------------
  // Autoplay controls
  // ---------------------------------------------------------------------------

  test('play button is visible', async ({ page }) => {
    await expect(page.locator('#play-btn')).toBeVisible();
  });

  test('MED speed button is active by default', async ({ page }) => {
    await expect(page.locator('.speed-btn.active')).toContainText('MED');
  });

  test('clicking SLOW makes it active', async ({ page }) => {
    await page.locator('.speed-btn', { hasText: 'SLOW' }).click();
    await expect(page.locator('.speed-btn.active')).toContainText('SLOW');
  });

  // ---------------------------------------------------------------------------
  // Statistics
  // ---------------------------------------------------------------------------

  test('stats grid shows water sources mapped', async ({ page }) => {
    await expect(page.locator('#stats-grid')).toContainText('20K+');
  });

  test('stats grid shows species tracked count', async ({ page }) => {
    await expect(page.locator('#stats-grid')).toContainText('9');
  });

  // ---------------------------------------------------------------------------
  // COVID annotation
  // ---------------------------------------------------------------------------

  test('COVID note is visible when year is 2020', async ({ page }) => {
    const slider = page.locator('#year-slider');
    await slider.evaluate((el: HTMLInputElement) => {
      el.value = '2020';
      el.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await expect(page.locator('#covid-note')).toBeVisible();
  });

  test('COVID note is hidden when year is not 2020', async ({ page }) => {
    const slider = page.locator('#year-slider');
    await slider.evaluate((el: HTMLInputElement) => {
      el.value = '2019';
      el.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await expect(page.locator('#covid-note')).toBeHidden();
  });

  // ---------------------------------------------------------------------------
  // Trend chart modal
  // ---------------------------------------------------------------------------

  test('trend panel is hidden by default', async ({ page }) => {
    await expect(page.locator('#trend-panel')).toBeHidden();
  });

  test('trend panel close button hides the panel', async ({ page }) => {
    // Force-show the panel to test close button
    await page.locator('#trend-panel').evaluate(el => el.classList.add('visible'));
    await page.locator('#trend-close').click();
    await expect(page.locator('#trend-panel')).toBeHidden();
  });

});
