import { describe, expect, it } from 'vitest'
import { ApiError, errorFromResponse } from '../src/api/errors'
import { describeError } from '../src/lib/errorText'

const http = (status: number, code: string, message = 'server message', details: Record<string, unknown> = {}) =>
  errorFromResponse(status, { detail: { code, message, ...details } })

describe('describeError: every status the dashboard must handle', () => {
  it('401: asks the user to sign in again', () => {
    const d = describeError(http(401, 'UNAUTHENTICATED'))
    expect(d.title).toBe('Sign-in required')
    expect([d.status, d.code]).toEqual([401, 'UNAUTHENTICATED'])
  })

  it('403 self-review: explains the four-eyes rule', () => {
    const d = describeError(http(403, 'SELF_REVIEW_FORBIDDEN'))
    expect(d.title).toMatch(/cannot review your own investigation/i)
    expect(d.message).toMatch(/four-eyes/i)
  })

  it('403 role: shows the server message', () => {
    expect(describeError(http(403, 'FORBIDDEN', "Role 'analyst' may not do this.")).message).toContain("Role 'analyst'")
  })

  it('409 already decided: reassures that nothing changed', () => {
    const d = describeError(http(409, 'ALREADY_DECIDED'))
    expect(d.title).toBe('Already decided')
    expect(d.message).toMatch(/nothing was changed/i)
  })

  it('409 LLM not configured: warns, and says rule-based results are labelled', () => {
    const d = describeError(http(409, 'LLM_NOT_CONFIGURED'))
    expect(d.tone).toBe('warning')
    expect(d.message).toMatch(/never presented as AI/i)
  })

  it.each([
    ['INVESTIGATION_NOT_RUNNABLE', /cannot be run/i],
    ['INVESTIGATION_NOT_REVIEWABLE', /not awaiting review/i],
    ['EVIDENCE_MISSING', /evidence is missing/i],
    ['INVESTIGATION_CLOSED', /closed/i],
  ])('409 %s', (code, title) => {
    expect(describeError(http(409, code)).title).toMatch(title)
  })

  it('422 unknown ids: lists each offending complaint', () => {
    const d = describeError(http(422, 'UNKNOWN_COMPLAINT_IDS', 'x', { unknown_ids: [999999, 5] }))
    expect(d.title).toBe('Unknown complaint IDs')
    expect(d.items).toEqual(['Complaint #999999', 'Complaint #5'])
  })

  it('422 unattached evidence lists the ids', () => {
    const d = describeError(http(422, 'EVIDENCE_NOT_ATTACHED', 'x', { unattached_ids: [3] }))
    expect(d.items).toEqual(['Complaint #3'])
  })

  it('422 validation lists each field', () => {
    const e = errorFromResponse(422, { detail: [{ loc: ['body', 'title'], msg: 'String should have at least 3 characters' }] })
    const d = describeError(e)
    expect(d.title).toBe('Please correct the input')
    expect(d.items).toEqual(['title: String should have at least 3 characters'])
  })

  it('422 validation about the whole request shows just the message, without pydantic\'s "Value error, " prefix', () => {
    const e = errorFromResponse(422, { detail: [{ loc: ['body'], msg: 'Value error, A comment of at least 3 characters is required to reject.' }] })
    const d = describeError(e)
    expect(d.items).toEqual(['A comment of at least 3 characters is required to reject.'])
    expect(e.message).toBe('A comment of at least 3 characters is required to reject.')
  })

  it('503 database: calm, retryable wording', () => {
    const d = describeError(http(503, 'DB_UNAVAILABLE'))
    expect(d.title).toBe('Database unavailable')
    expect(d.tone).toBe('warning')
  })

  it('503 auth not configured: says the server fails closed', () => {
    const d = describeError(http(503, 'AUTH_NOT_CONFIGURED'))
    expect(d.title).toBe('Authentication is not configured')
    expect(d.message).toMatch(/fails closed/i)
  })

  it('agent failures (502/504) are described as the agent failing', () => {
    expect(describeError(http(502, 'EVIDENCE_REJECTED', 'ungrounded')).title).toMatch(/agent could not finish/i)
    expect(describeError(http(504, 'AGENT_TIMEOUT', 'too slow')).title).toMatch(/agent could not finish/i)
  })

  it('network, timeout and contract failures have their own wording', () => {
    expect(describeError(new ApiError({ kind: 'network', status: 0, code: 'NETWORK_ERROR', message: 'x' })).title).toBe('Cannot reach the API')
    expect(describeError(new ApiError({ kind: 'timeout', status: 0, code: 'TIMEOUT', message: 'slow' })).title).toBe('The request timed out')
    const contract = describeError(new ApiError({ kind: 'contract', status: 200, code: 'CONTRACT_MISMATCH', message: 'x', details: { issues: ['system.llm'] } }))
    expect(contract.title).toBe('Unexpected server response')
    expect(contract.items).toEqual(['Unexpected field: system.llm'])
  })

  it('unknown errors never crash the UI', () => {
    expect(describeError(new Error('boom')).message).toBe('boom')
    expect(describeError('weird').title).toBe('Something went wrong')
  })
})
