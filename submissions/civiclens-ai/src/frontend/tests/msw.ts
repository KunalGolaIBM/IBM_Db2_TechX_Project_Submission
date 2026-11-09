import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import {
  API,
  auditEntry,
  complaint,
  evidenceItem,
  hotspot,
  investigation,
  meForToken,
  overview,
  queueItem,
  recommendation,
  runResult,
} from './fixtures'

/** Bearer-token check shared by the fake endpoints, the way the real API behaves. */
export function bearer(request: Request): string | null {
  const header = request.headers.get('authorization') ?? ''
  return header.startsWith('Bearer ') ? header.slice(7) : null
}

const unauthenticated = () =>
  HttpResponse.json({ detail: { code: 'UNAUTHENTICATED', message: 'A valid bearer token is required.' } }, { status: 401 })

/** Wrap a resolver so it only runs for a known token (401 otherwise). */
export const authed =
  (resolve: (ctx: { request: Request; params: Record<string, string | readonly string[] | undefined> }) => Response | Promise<Response>) =>
  (ctx: { request: Request; params: Record<string, string | readonly string[] | undefined> }) => {
    const token = bearer(ctx.request)
    return token && meForToken(token) ? resolve(ctx) : unauthenticated()
  }

export const defaultHandlers = [
  http.get(`${API}/api/me`, authed(({ request }) => HttpResponse.json(meForToken(bearer(request)!)))),
  http.get(`${API}/api/overview`, authed(() => HttpResponse.json(overview()))),
  http.get(`${API}/api/complaints`, () => HttpResponse.json([complaint()])),
  http.get(`${API}/api/hotspots`, () => HttpResponse.json([hotspot()])),
  http.get(`${API}/api/investigations`, authed(() => HttpResponse.json([investigation()]))),
  http.get(`${API}/api/investigations/:id`, authed(() => HttpResponse.json(investigation()))),
  http.get(`${API}/api/investigations/:id/evidence`, authed(() => HttpResponse.json([evidenceItem()]))),
  http.get(`${API}/api/investigations/:id/audit`, authed(() => HttpResponse.json([auditEntry()]))),
  http.get(`${API}/api/investigations/:id/recommendations`, authed(() => HttpResponse.json([recommendation()]))),
  http.get(`${API}/api/recommendations`, authed(() => HttpResponse.json([queueItem()]))),
  http.post(`${API}/api/investigations/:id/run`, authed(() => HttpResponse.json(runResult()))),
]

export const server = setupServer(...defaultHandlers)

/** Shorthand for an error body in the API's structured shape. */
export const apiError = (status: number, code: string, message: string, extra: Record<string, unknown> = {}) =>
  HttpResponse.json({ detail: { code, message, ...extra } }, { status })
