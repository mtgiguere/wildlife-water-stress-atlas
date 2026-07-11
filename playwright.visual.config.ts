import { defineConfig, devices } from '@playwright/test';

// Visual smoke test config — renders the Mapbox WebGL app with SOFTWARE WebGL
// (SwiftShader) so the map actually paints in a headless environment, then
// asserts on pixels. The default chromium-headless-shell has no WebGL, so a
// normal screenshot is black even when everything works (see the road-threat
// addendum in docs/TDD_CONTRACT.md, Blind spot B).
//
// This is a reality-dependent guard: it needs a real GPU-less WebGL stack and
// the live Mapbox basemap, so — like the roads-download integration test — it
// runs on demand, NOT in CI:
//
//     npx playwright test --config=playwright.visual.config.ts
//
// The webServer block starts the static Mapbox app automatically.
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: '**/test_mapbox_visual.spec.ts',
  timeout: 120000,
  expect: { timeout: 30000 },
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:3000',
    viewport: { width: 1400, height: 900 },
    launchOptions: {
      args: [
        '--use-gl=angle',
        '--use-angle=swiftshader',
        '--enable-unsafe-swiftshader',
        '--ignore-gpu-blocklist',
        '--enable-webgl',
      ],
    },
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: {
    command: 'python -m http.server 3000',
    cwd: './apps/mapbox',
    url: 'http://localhost:3000',
    reuseExistingServer: true,
    timeout: 30000,
  },
});
