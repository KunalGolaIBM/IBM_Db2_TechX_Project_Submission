import { defineConfig, devices } from "@playwright/test";

/**
 * Two projects, deliberately separated:
 *   real  – drives the UI against the REAL FastAPI backend + IBM Db2 (must be running on :8000)
 *   mock  – stubs selected HTTP responses (clearly labeled) to reach states the live system rarely produces
 */
export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 180_000,
  expect: { timeout: 60_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"], ["json", { outputFile: "test-results/e2e.json" }]],
  use: { baseURL: "http://localhost:3000", trace: "retain-on-failure", screenshot: "only-on-failure", permissions: ["clipboard-read", "clipboard-write"] },
  projects: [
    { name: "real-backend", testMatch: /real\.(workflow|meta)\.spec\.ts/, use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    { name: "mock-responses", testMatch: /mock\..*\.spec\.ts/, use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    { name: "real-mobile", testMatch: /real\.mobile\.spec\.ts/, use: { ...devices["Pixel 7"] } },
  ],
  webServer: {
    command: "npm run build && npm run start",
    url: "http://localhost:3000",
    reuseExistingServer: true,
    timeout: 240_000,
  },
});
