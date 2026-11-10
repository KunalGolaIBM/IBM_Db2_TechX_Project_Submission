import { defineConfig } from 'vitest/config'

// Contract test: the real TypeScript API client against a RUNNING FastAPI + IBM Db2 backend.
//   CIVICLENS_LIVE_API=http://127.0.0.1:8000 CIVICLENS_AUTH_TOKENS=... npm run test:live
export default defineConfig({
  test: {
    environment: 'node',
    include: ['tests/live/**/*.live.test.ts'],
    testTimeout: 60_000,
    env: { VITE_API_BASE_URL: process.env.CIVICLENS_LIVE_API ?? '' },
  },
})
