import { defineConfig, devices } from '@playwright/test'

/**
 * End-to-end tests drive the PRODUCTION BUILD (so the Content-Security-Policy is really enforced) against a REAL
 * FastAPI backend and IBM Db2. Start the backend first (see README), then:  npm run e2e
 *
 * Tokens come from CIVICLENS_AUTH_TOKENS ("id:role:token,...", needs one analyst and two reviewers). Traces, videos and
 * automatic screenshots are OFF on purpose: they would record Authorization headers and the sign-in field.
 */
const baseURL = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:4173'
const executablePath = process.env.PW_CHROMIUM_PATH || undefined
const proxy = process.env.HTTPS_PROXY ? { server: process.env.HTTPS_PROXY, bypass: '127.0.0.1,localhost' } : undefined

export default defineConfig({
  testDir: './e2e',
  timeout: 90_000,
  expect: { timeout: 12_000 },
  fullyParallel: false,
  workers: 1, // every test shares one Db2 and one demo dataset
  retries: 0,
  reporter: [['list'], ['json', { outputFile: 'test-results/e2e-results.json' }]],
  outputDir: 'test-results/artifacts',
  use: {
    baseURL,
    trace: 'off',
    video: 'off',
    screenshot: 'off',
    colorScheme: 'dark',
    locale: 'en-GB',
    timezoneId: 'UTC',
    launchOptions: { executablePath },
  },
  projects: [
    {
      name: 'functional',
      testIgnore: /(screenshots|demo)\.spec\.ts/,
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
    },
    {
      // Evidence screenshots use the real OpenStreetMap tiles (through the sandbox proxy); functional tests stub them.
      name: 'screenshots',
      testMatch: /screenshots\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1440, height: 900 },
        deviceScaleFactor: 2,
        launchOptions: { executablePath, proxy },
      },
    },
    {
      // A silent, captioned recording of the real app (e2e/demo.spec.ts). The spec makes its own context (video on, signed in off camera).
      name: 'demo',
      testMatch: /demo\.spec\.ts/,
      use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 720 }, launchOptions: { executablePath, proxy } },
    },
  ],
  webServer: process.env.E2E_NO_SERVER
    ? undefined
    : {
        command: 'npm run build && npm run preview -- --strictPort',
        url: baseURL,
        reuseExistingServer: true,
        timeout: 180_000,
      },
})
