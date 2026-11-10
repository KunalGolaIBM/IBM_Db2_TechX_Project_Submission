import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { tokenStore } from '../src/auth/tokenStore'
import { server } from './msw'

// jsdom has no layout engine and no matchMedia; the components degrade gracefully, these keep Leaflet-free code happy.
if (!window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia
}

// ...nor scrollIntoView (layout); views that bring a result into view call it, so it is a recorded no-op here.
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {}

beforeAll(() => server.listen({ onUnhandledFrame: 'error' })) // a request nobody expected is a test failure
afterEach(() => {
  cleanup()
  server.resetHandlers()
  tokenStore.clear()
  window.sessionStorage.clear()
  window.localStorage.clear()
})
afterAll(() => server.close())
