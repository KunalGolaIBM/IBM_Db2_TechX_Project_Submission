import { http, HttpResponse, delay } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { z } from 'zod'
import { apiRequest, buildUrl, setUnauthorizedHandler } from '../../src/api/client'
import { endpoints } from '../../src/api/endpoints'
import { ApiError } from '../../src/api/errors'
import { tokenStore } from '../../src/auth/tokenStore'
import { API, TOKENS, analyst, complaint, queueItem } from '../fixtures'
import { apiError, server } from '../msw'

const anything = z.unknown()
const expectApiError = async (promise: Promise<unknown>): Promise<ApiError> => {
  try {
    await promise
  } catch (error) {
    expect(error).toBeInstanceOf(ApiError)
    return error as ApiError
  }
  throw new Error('expected the request to fail')
}

afterEach(() => setUnauthorizedHandler(null))

describe('request construction', () => {
  it('sends the stored token as a bearer header and nothing else as credentials', async () => {
    tokenStore.set(TOKENS.analyst)
    let seen: Request | undefined
    server.use(
      http.get(`${API}/api/me`, ({ request }) => {
        seen = request
        return HttpResponse.json(analyst)
      }),
    )
    const spy = vi.spyOn(globalThis, 'fetch') // observes the real call; the request still goes through MSW
    await endpoints.me()
    expect(seen?.headers.get('authorization')).toBe(`Bearer ${TOKENS.analyst}`)
    expect(seen?.headers.get('accept')).toBe('application/json')
    const init = spy.mock.calls[0][1]
    expect(init?.credentials).toBe('omit') // never ambient cookies
    expect(init?.cache).toBe('no-store')
  })

  it('sends no Authorization header when there is no token', async () => {
    let header: string | null = 'unset'
    server.use(
      http.get(`${API}/api/complaints`, ({ request }) => {
        header = request.headers.get('authorization')
        return HttpResponse.json([])
      }),
    )
    await endpoints.complaints()
    expect(header).toBeNull()
  })

  it('an explicit token overrides the stored one (login checks a candidate before storing it)', async () => {
    tokenStore.set('stored-token')
    let header = ''
    server.use(
      http.get(`${API}/api/me`, ({ request }) => {
        header = request.headers.get('authorization') ?? ''
        return HttpResponse.json(analyst)
      }),
    )
    await endpoints.me('candidate-token')
    expect(header).toBe('Bearer candidate-token')
  })

  it('builds query strings from defined values only', () => {
    expect(buildUrl('/api/hotspots', { days: 30, category: undefined, min_count: 3, ward: null, q: '' })).toBe(
      `${API}/api/hotspots?days=30&min_count=3`,
    )
    expect(buildUrl('/api/me')).toBe(`${API}/api/me`)
  })

  it('POSTs JSON with the right content type', async () => {
    tokenStore.set(TOKENS.analyst)
    let body: unknown
    let type: string | null = null
    server.use(
      http.post(`${API}/api/investigations`, async ({ request }) => {
        body = await request.json()
        type = request.headers.get('content-type')
        return HttpResponse.json({
          investigation_id: 9, title: 't', question: 'q', status: 'OPEN', created_by: 'alice', created_at: '2026-11-09T09:00:00', closed_at: null,
        }) // fmt: skip
      }),
    )
    const created = await endpoints.createInvestigation({ title: 'Title', question: 'Question?' })
    expect(body).toEqual({ title: 'Title', question: 'Question?' })
    expect(type).toContain('application/json')
    expect(created.investigation_id).toBe(9)
  })
})

describe('error mapping (the real fetch stack, not stubs)', () => {
  it.each([
    [401, 'UNAUTHENTICATED'],
    [403, 'FORBIDDEN'],
    [404, 'INVESTIGATION_NOT_FOUND'],
    [409, 'ALREADY_DECIDED'],
    [503, 'DB_UNAVAILABLE'],
  ])('maps a structured %i response to status + code', async (status, code) => {
    server.use(http.get(`${API}/api/recommendations`, () => apiError(status, code, `message for ${code}`)))
    const error = await expectApiError(apiRequest('/api/recommendations', { schema: anything, token: 't' }))
    expect([error.kind, error.status, error.code, error.message]).toEqual(['http', status, code, `message for ${code}`])
  })

  it('keeps structured details such as unknown complaint ids (422)', async () => {
    server.use(
      http.post(`${API}/api/investigations/7/evidence`, () =>
        apiError(422, 'UNKNOWN_COMPLAINT_IDS', 'Some complaint ids do not exist.', { unknown_ids: [999999] }),
      ),
    )
    const error = await expectApiError(endpoints.attachEvidence(7, { complaint_ids: [999999] }))
    expect(error.status).toBe(422)
    expect(error.details.unknown_ids).toEqual([999999])
  })

  it("maps FastAPI's validation array (422) to field errors without 'body' noise", async () => {
    server.use(
      http.post(`${API}/api/complaints`, () =>
        HttpResponse.json(
          { detail: [{ loc: ['body', 'latitude'], msg: 'Input should be less than or equal to 90', type: 'less_than_equal' }] },
          { status: 422 },
        ),
      ),
    )
    const error = await expectApiError(
      endpoints.createComplaint({ category: 'OTHER', title: 'abc', description: 'abc', latitude: 91, longitude: 1, severity: 3, is_synthetic: true }),
    )
    expect(error.code).toBe('VALIDATION_ERROR')
    expect(error.fieldErrors).toEqual([{ field: 'latitude', message: 'Input should be less than or equal to 90' }])
  })

  it('copes with a non-JSON error body', async () => {
    server.use(http.get(`${API}/api/overview`, () => new HttpResponse('<html>Bad gateway</html>', { status: 502, headers: { 'content-type': 'text/html' } })))
    const error = await expectApiError(endpoints.overview())
    expect([error.status, error.code]).toEqual([502, 'HTTP_502'])
  })

  it('reports a network failure as status 0 without leaking anything', async () => {
    server.use(http.get(`${API}/api/overview`, () => HttpResponse.error()))
    const error = await expectApiError(endpoints.overview())
    expect([error.kind, error.status, error.code]).toEqual(['network', 0, 'NETWORK_ERROR'])
  })

  it('times out slow requests', async () => {
    server.use(
      http.get(`${API}/api/overview`, async () => {
        await delay(500)
        return HttpResponse.json({})
      }),
    )
    const error = await expectApiError(apiRequest('/api/overview', { schema: anything, timeoutMs: 40 }))
    expect([error.kind, error.code]).toEqual(['timeout', 'TIMEOUT'])
  })

  it('rejects a response that does not match the schema and echoes only field paths', async () => {
    server.use(http.get(`${API}/api/recommendations`, () => HttpResponse.json([{ ...queueItem(), generator_type: 'SECRET-VALUE-GPT' }])))
    const error = await expectApiError(endpoints.recommendations())
    expect(error.kind).toBe('contract')
    expect(error.code).toBe('CONTRACT_MISMATCH')
    expect(JSON.stringify(error.details)).toContain('generator_type')
    expect(JSON.stringify(error)).not.toContain('SECRET-VALUE-GPT') // values are not echoed
  })

  it('validates successful responses and returns typed data', async () => {
    server.use(http.get(`${API}/api/complaints`, () => HttpResponse.json([complaint({ complaint_id: 42 })])))
    const rows = await endpoints.complaints({ category: 'POTHOLE' })
    expect(rows[0].complaint_id).toBe(42)
  })
})

describe('unauthorised handler', () => {
  it('fires for a 401 that used the stored token', async () => {
    tokenStore.set('revoked-token')
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    server.use(http.get(`${API}/api/overview`, () => apiError(401, 'UNAUTHENTICATED', 'nope')))
    await expectApiError(endpoints.overview())
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('does not fire for a login attempt with a wrong candidate token', async () => {
    tokenStore.set(TOKENS.analyst)
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    server.use(http.get(`${API}/api/me`, () => apiError(401, 'UNAUTHENTICATED', 'nope')))
    await expectApiError(endpoints.me('wrong-candidate'))
    expect(handler).not.toHaveBeenCalled()
  })

  it('does not fire for other statuses', async () => {
    tokenStore.set(TOKENS.analyst)
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    server.use(http.get(`${API}/api/overview`, () => apiError(403, 'FORBIDDEN', 'no')))
    await expectApiError(endpoints.overview())
    expect(handler).not.toHaveBeenCalled()
  })
})
