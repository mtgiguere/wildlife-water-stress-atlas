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

  test('all 9 species buttons are rendered', async ({ page }) => {
    const buttons = page.locator('.species-btn');
    await expect(buttons).toHaveCount(9);
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
