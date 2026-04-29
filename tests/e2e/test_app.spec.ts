import { test, expect } from '@playwright/test';

const APP_URL = 'http://localhost:8501';

test.describe('Wildlife Water Stress Atlas', () => {

    test.beforeEach(async ({ page }) => {
        // Navigate to app
        await page.goto(APP_URL);
        // Wait for the title to appear — this is immediate, before data loads
        await page.waitForSelector('h1', { timeout: 30000 });
    });

  // ---------------------------------------------------------------------------
  // Page structure
  // ---------------------------------------------------------------------------

  test('page title is correct', async ({ page }) => {
    await expect(page).toHaveTitle('Wildlife Water Stress Atlas');
  });

    test('main heading is visible', async ({ page }) => {
        await expect(
            page.getByTestId('stMainBlockContainer')
                .getByRole('heading', { name: '🐘 Wildlife Water Stress Atlas' })
        ).toBeVisible();
    });

    test('species description is visible', async ({ page }) => {
        await expect(
            page.getByTestId('stMainBlockContainer')
                .getByText('Loxodonta africana')
        ).toBeVisible();
    });

  // ---------------------------------------------------------------------------
  // Sidebar
  // ---------------------------------------------------------------------------

  test('year slider is visible in sidebar', async ({ page }) => {
    await expect(
      page.getByText('Select Year')
    ).toBeVisible();
  });

  test('sidebar shows record count metric', async ({ page }) => {
    await expect(
      page.getByText('Records in')
    ).toBeVisible();
  });

  test('sidebar shows total records metric', async ({ page }) => {
    await expect(
      page.getByText('Total Records')
    ).toBeVisible();
  });

  test('sidebar shows data sources', async ({ page }) => {
    await expect(
      page.getByText('GBIF')
    ).toBeVisible();
  });

  // ---------------------------------------------------------------------------
  // Map
  // ---------------------------------------------------------------------------

    test('map canvas renders', async ({ page }) => {
        await expect(
            page.locator('#deckgl-overlay')
        ).toBeVisible({ timeout: 300000 });
    });

  // ---------------------------------------------------------------------------
  // Stats row
  // ---------------------------------------------------------------------------

  test('elephant records metric is visible', async ({ page }) => {
    await expect(
      page.getByText('Elephant Records')
    ).toBeVisible();
  });

  test('total records in dataset metric is visible', async ({ page }) => {
    await expect(
      page.getByText('Total Records in Dataset')
    ).toBeVisible();
  });

  test('water sources mapped metric is visible', async ({ page }) => {
    await expect(
      page.getByText('Water Sources Mapped')
    ).toBeVisible();
  });

  // ---------------------------------------------------------------------------
  // Data quality note
  // ---------------------------------------------------------------------------

  test('data quality note is visible', async ({ page }) => {
    await expect(
      page.getByText('Data quality note')
    ).toBeVisible();
  });

  test('GLWD citation is visible', async ({ page }) => {
    await expect(
      page.getByText('GLWD v2')
    ).toBeVisible();
  });

  // ---------------------------------------------------------------------------
  // Year slider interaction
  // ---------------------------------------------------------------------------

  test('total records shows 21,900', async ({ page }) => {
    await expect(
      page.getByText('21,900')
    ).toBeVisible();
  });

});