import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  testMatch: '**/test_mapbox.spec.ts',
  timeout: 60000,         // 1 minute per test — static app, no server compute
  expect: {
    timeout: 30000,       // 30 seconds for assertions
  },
  fullyParallel: false,
  workers: 1,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
