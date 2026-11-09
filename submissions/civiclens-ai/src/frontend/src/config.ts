/**
 * Build-time configuration. Only the (public) API base URL is configurable; credentials are never
 * part of the bundle. An empty base URL means "same origin" (the dev/preview proxy or a reverse proxy).
 */
export function resolveApiBaseUrl(raw: string | undefined): string {
  const value = (raw ?? '').trim().replace(/\/+$/, '')
  if (!value) return ''
  try {
    const url = new URL(value)
    if (url.protocol !== 'http:' && url.protocol !== 'https:') throw new Error('unsupported protocol')
    return url.origin + url.pathname.replace(/\/+$/, '')
  } catch {
    console.error('VITE_API_BASE_URL is not a valid http(s) URL; falling back to the same origin.')
    return ''
  }
}

export const API_BASE_URL = resolveApiBaseUrl(import.meta.env.VITE_API_BASE_URL)
export const REFRESH_INTERVAL_MS = 30_000
