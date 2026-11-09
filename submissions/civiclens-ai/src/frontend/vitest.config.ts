import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Component + API-client tests. API traffic is intercepted by MSW, so these are MOCK-BASED tests of
// the UI; the real backend/Db2 is exercised by `npm run test:live` and by the Playwright suite.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/**/*.test.{ts,tsx}'],
    exclude: ['tests/live/**', 'e2e/**', 'node_modules/**'],
    env: { VITE_API_BASE_URL: 'http://api.test' },
    css: false,
    restoreMocks: true,
  },
})
