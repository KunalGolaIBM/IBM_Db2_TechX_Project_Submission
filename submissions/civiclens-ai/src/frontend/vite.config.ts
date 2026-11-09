import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig, loadEnv, type Plugin } from 'vite'

/**
 * Production-only Content-Security-Policy (as a <meta> tag; `frame-ancestors` cannot be set this
 * way, so set it as an HTTP header at the host). The dev server is exempt because Vite's HMR needs
 * inline scripts and websockets. `connect-src` allows only this origin plus the configured API.
 */
function contentSecurityPolicy(apiBaseUrl: string): Plugin {
  const apiOrigin = apiBaseUrl ? new URL(apiBaseUrl).origin : ''
  const policy = [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'", // Leaflet positions tiles with inline style attributes
    "img-src 'self' data: https://tile.openstreetmap.org",
    "font-src 'self' data:",
    `connect-src 'self'${apiOrigin ? ` ${apiOrigin}` : ''}`,
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
  ].join('; ')
  return {
    name: 'civiclens-csp',
    apply: 'build',
    transformIndexHtml: () => [
      { tag: 'meta', attrs: { 'http-equiv': 'Content-Security-Policy', content: policy }, injectTo: 'head-prepend' },
    ],
  }
}

export default defineConfig(({ mode }) => {
  // Only VITE_-prefixed, non-secret settings are ever exposed to the browser bundle.
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  const apiBaseUrl = (env.VITE_API_BASE_URL ?? '').trim().replace(/\/+$/, '')
  // Dev/preview serve the SPA and forward same-origin /api calls to the backend.
  const proxy = { '/api': { target: process.env.API_PROXY_TARGET ?? 'http://127.0.0.1:8000' } }
  return {
    plugins: [react(), tailwindcss(), contentSecurityPolicy(apiBaseUrl)],
    server: { host: '127.0.0.1', port: 5173, proxy },
    preview: { host: '127.0.0.1', port: 4173, proxy },
    build: { sourcemap: false, target: 'es2022' },
  }
})
