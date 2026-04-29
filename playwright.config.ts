import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 360000,        // 6 minutes per test
  expect: {
    timeout: 360000,      // 6 minutes for expect assertions
  },
  fullyParallel: false,   // run sequentially — app can't handle parallel loads
  workers: 1,             // one worker — same reason
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:8501',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});