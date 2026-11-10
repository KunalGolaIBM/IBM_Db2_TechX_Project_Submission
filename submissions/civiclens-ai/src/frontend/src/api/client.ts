import type { ZodType } from 'zod'
import { API_BASE_URL } from '../config'
import { tokenStore } from '../auth/tokenStore'
import { ApiError, errorFromResponse } from './errors'

type Primitive = string | number | boolean | null | undefined

export interface RequestOptions<T> {
  method?: 'GET' | 'POST'
  query?: Record<string, Primitive>
  body?: unknown
  schema: ZodType<T>
  signal?: AbortSignal
  /** Use this token instead of the stored one (login validates a token before storing it). */
  token?: string | null
  timeoutMs?: number
}

const DEFAULT_TIMEOUT_MS = 30_000

let onUnauthorized: (() => void) | null = null
/** Called when a request made with the *stored* token is rejected with 401. */
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler
}

export function buildUrl(path: string, query?: Record<string, Primitive>): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value))
  }
  const qs = params.toString()
  return `${API_BASE_URL}${path}${qs ? `?${qs}` : ''}`
}

export async function apiRequest<T>(path: string, options: RequestOptions<T>): Promise<T> {
  const { method = 'GET', query, body, schema, signal, timeoutMs = DEFAULT_TIMEOUT_MS } = options
  const usingStoredToken = options.token === undefined
  const token = usingStoredToken ? tokenStore.get() : options.token

  const headers: Record<string, string> = { Accept: 'application/json' }
  if (token) headers.Authorization = `Bearer ${token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  const controller = new AbortController()
  let timedOut = false
  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)
  const abortFromCaller = () => controller.abort()
  signal?.addEventListener('abort', abortFromCaller)

  let response: Response
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
      credentials: 'omit', // bearer tokens only; never ambient cookies
      cache: 'no-store',
    })
  } catch (cause) {
    if (timedOut) {
      throw new ApiError({
        kind: 'timeout',
        status: 0,
        code: 'TIMEOUT',
        message: `The server did not answer within ${Math.round(timeoutMs / 1000)} seconds.`,
      })
    }
    if (signal?.aborted) throw cause // the caller cancelled: let the query layer handle it
    throw new ApiError({
      kind: 'network',
      status: 0,
      code: 'NETWORK_ERROR',
      message: 'Could not reach the CivicLens API.',
    })
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', abortFromCaller)
  }

  const raw = await response.text()
  let payload: unknown = null
  if (raw) {
    try {
      payload = JSON.parse(raw)
    } catch {
      payload = null
    }
  }

  if (!response.ok) {
    if (response.status === 401 && usingStoredToken && token) onUnauthorized?.()
    throw errorFromResponse(response.status, payload, response.statusText)
  }

  const parsed = schema.safeParse(payload)
  if (!parsed.success) {
    throw new ApiError({
      kind: 'contract',
      status: response.status,
      code: 'CONTRACT_MISMATCH',
      message: 'The server response did not have the expected shape.',
      // paths only: response values may be sensitive and are not echoed
      details: { issues: parsed.error.issues.slice(0, 5).map((i) => i.path.join('.') || '(root)') },
    })
  }
  return parsed.data
}
