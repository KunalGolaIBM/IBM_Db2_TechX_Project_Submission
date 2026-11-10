/**
 * LIVE contract test: the real TypeScript API client (and its zod schemas) against a RUNNING FastAPI + IBM Db2
 * backend. No mocks. It proves that every response the dashboard relies on has the shape the UI expects.
 *
 *   CIVICLENS_LIVE_API=http://127.0.0.1:8000 CIVICLENS_AUTH_TOKENS="id:role:token,..." npm run test:live
 *
 * Rows it creates are marked "[CONTRACT]" so `scripts/cleanup_test_data.py` can remove them afterwards.
 * Tokens come from the environment and are never printed.
 */
import { beforeAll, describe, expect, it } from 'vitest'
import { endpoints } from '../../src/api/endpoints'
import { ApiError } from '../../src/api/errors'
import { tokenStore } from '../../src/auth/tokenStore'

const live = process.env.CIVICLENS_LIVE_API
const raw = process.env.CIVICLENS_AUTH_TOKENS ?? ''
const users = raw
  .split(',')
  .map((e) => e.trim().split(':'))
  .filter((p) => p.length >= 3)
  .map(([id, role, ...t]) => ({ id, role, token: t.join(':') }))
const analyst = users.find((u) => u.role === 'analyst')
const reviewers = users.filter((u) => u.role === 'reviewer')
const enabled = Boolean(live && analyst && reviewers.length >= 2)

const as = (user: { token: string } | undefined) => tokenStore.set(user!.token)
const failure = async (promise: Promise<unknown>): Promise<ApiError> => {
  try {
    await promise
  } catch (e) {
    expect(e).toBeInstanceOf(ApiError)
    return e as ApiError
  }
  throw new Error('expected the request to fail')
}

describe.skipIf(!enabled)('live API contract (real backend + Db2)', () => {
  let complaintIds: number[] = []
  let llmConfigured = false

  beforeAll(async () => {
    as(analyst)
    const rows = await endpoints.complaints({ limit: 10 })
    complaintIds = rows.slice(0, 3).map((c) => c.complaint_id)
    expect(complaintIds.length).toBeGreaterThan(0)
    llmConfigured = (await endpoints.overview()).system.llm.configured
  })

  it('identifies each caller and their capabilities', async () => {
    as(analyst)
    const a = await endpoints.me()
    expect(a).toMatchObject({ user_id: analyst!.id, role: 'analyst' })
    expect(a.capabilities).toContain('investigation:create')
    expect(a.capabilities).not.toContain('recommendation:decide')
    as(reviewers[0])
    const r = await endpoints.me()
    expect(r.role).toBe('reviewer')
    expect(r.capabilities).toEqual(['recommendation:decide'])
  })

  it('401 for a wrong token and for no token', async () => {
    expect((await failure(endpoints.me('definitely-not-a-token'))).status).toBe(401)
    tokenStore.clear()
    expect((await failure(endpoints.overview())).status).toBe(401)
  })

  it('serves a schema-valid overview whose numbers are consistent with the complaint list', async () => {
    as(analyst)
    const o = await endpoints.overview()
    expect(o.system.database.product).toMatch(/^DB2/)
    expect(o.complaints.synthetic + o.complaints.real).toBe(o.complaints.total)
    expect(o.complaints.by_severity.map((s) => s.severity)).toEqual([1, 2, 3, 4, 5])
    expect(o.complaints.trend).toHaveLength(o.complaints.trend_days)
    expect(o.complaints.by_category.reduce((n, c) => n + c.count, 0)).toBe(o.complaints.total)
    expect(o.recommendations.pending_review).toBe(o.recommendations.by_status.PROPOSED)
    expect(o.hotspots.total).toBeGreaterThanOrEqual(o.hotspots.items.length)
    expect(o.system.agent.tools).toContain('hotspot_summary')
    const list = await endpoints.complaints({ limit: 200 })
    expect(list.length).toBeLessThanOrEqual(o.complaints.total)
  })

  it('serves schema-valid complaints and hotspots', async () => {
    const rows = await endpoints.complaints({ limit: 5 })
    expect(rows.length).toBeGreaterThan(0)
    expect(rows[0].geo_cell).toMatch(/^C-?\d+_-?\d+$/)
    const spots = await endpoints.hotspots({ days: 365, minCount: 2, limit: 5 })
    expect(Array.isArray(spots)).toBe(true)
  })

  it('complaint intake: analyst only, with Db2 duplicate candidates', async () => {
    const body = {
      category: 'STREETLIGHT' as const,
      title: '[CONTRACT] synthetic streetlight fault',
      description: '[SYNTHETIC] created by the live contract test',
      latitude: 12.0505,
      longitude: 70.0505,
      severity: 3,
      source: 'DASHBOARD',
      is_synthetic: true,
    }
    tokenStore.clear()
    expect((await failure(endpoints.createComplaint(body))).status).toBe(401)
    as(reviewers[0])
    expect((await failure(endpoints.createComplaint(body))).status).toBe(403)
    as(analyst)
    const first = await endpoints.createComplaint(body)
    expect(first.complaint.is_synthetic).toBe(true)
    const second = await endpoints.createComplaint(body)
    expect(second.duplicate_candidates.map((d) => d.complaint_id)).toContain(first.complaint.complaint_id)
  })

  it('the full workflow: create, attach (422 then OK), run rule-based, review, and 409/403 guards', async () => {
    as(analyst)
    const inv = await endpoints.createInvestigation({ title: '[CONTRACT] live workflow', question: 'Does the contract hold end to end?' })
    expect(inv).toMatchObject({ status: 'OPEN', created_by: analyst!.id })
    expect((await endpoints.investigation(inv.investigation_id)).title).toBe('[CONTRACT] live workflow')
    expect((await endpoints.investigations('OPEN')).map((i) => i.investigation_id)).toContain(inv.investigation_id)

    const bad = await failure(endpoints.attachEvidence(inv.investigation_id, { complaint_ids: [2_000_000_000] }))
    expect([bad.status, bad.code]).toEqual([422, 'UNKNOWN_COMPLAINT_IDS'])
    expect(bad.details.unknown_ids).toEqual([2_000_000_000])
    const attached = await endpoints.attachEvidence(inv.investigation_id, { complaint_ids: complaintIds })
    expect(attached.map((e) => e.complaint_id).sort()).toEqual([...complaintIds].sort())
    expect((await endpoints.evidence(inv.investigation_id)).length).toBe(complaintIds.length)

    const run = await endpoints.run(inv.investigation_id, { mode: 'fallback', days: 365, category: null, max_hotspots: 2 })
    expect(run).toMatchObject({ generator: 'DETERMINISTIC_FALLBACK', status: 'PENDING_REVIEW' })
    expect(run.notice).toMatch(/NO LLM WAS USED/)
    expect(run.recommendation_ids.length).toBeGreaterThan(0)
    expect((await failure(endpoints.run(inv.investigation_id, { mode: 'fallback', days: 30, category: null, max_hotspots: 1 }))).code).toBe('INVESTIGATION_NOT_RUNNABLE')

    const recs = await endpoints.investigationRecommendations(inv.investigation_id)
    expect(recs.every((r) => r.status === 'PROPOSED' && r.generator_type === 'DETERMINISTIC_FALLBACK')).toBe(true)
    const audit = await endpoints.audit(inv.investigation_id)
    const done = audit.find((e) => e.action === 'AGENT_RUN_COMPLETED')
    expect(JSON.parse(done!.input_json!).generator).toBe('DETERMINISTIC_FALLBACK') // what the timeline's origin banner reads
    expect(audit.some((e) => e.tool_name === 'hotspot_summary')).toBe(true)

    const queue = await endpoints.recommendations({ status: 'PROPOSED', investigationId: inv.investigation_id })
    expect(queue.map((q) => q.recommendation_id).sort()).toEqual(recs.map((r) => r.recommendation_id).sort())
    expect(queue[0].investigation_title).toBe('[CONTRACT] live workflow')

    const target = recs[0].recommendation_id
    as(analyst)
    expect((await failure(endpoints.decide(target, { decision: 'APPROVED' }))).status).toBe(403) // role
    as(reviewers[0])
    expect((await failure(endpoints.decide(target, { decision: 'REJECTED' }))).status).toBe(422) // comment required to reject
    const approved = await endpoints.decide(target, { decision: 'APPROVED', comment: 'contract test' })
    expect(approved.status).toBe('APPROVED')
    expect(approved.review).toMatchObject({ reviewer: reviewers[0].id, decision: 'APPROVED' })
    as(reviewers[1])
    const conflict = await failure(endpoints.decide(target, { decision: 'REJECTED', comment: 'too late' }))
    expect([conflict.status, conflict.code]).toEqual([409, 'ALREADY_DECIDED'])
  })

  it('LLM-only mode is refused when no model is configured (never a silent fallback)', async () => {
    if (llmConfigured) return // a real provider is configured here; this guard is covered by the backend tests
    as(analyst)
    const inv = await endpoints.createInvestigation({ title: '[CONTRACT] llm-only guard', question: 'Is LLM-only refused?' })
    const refused = await failure(endpoints.run(inv.investigation_id, { mode: 'llm', days: 30, category: null, max_hotspots: 1 }))
    expect([refused.status, refused.code]).toEqual([409, 'LLM_NOT_CONFIGURED'])
    expect((await endpoints.investigation(inv.investigation_id)).status).toBe('OPEN') // nothing was consumed
  })

  it('validation failures arrive as field errors (422)', async () => {
    as(analyst)
    const err = await failure(endpoints.createInvestigation({ title: 'x', question: 'y' }))
    expect(err.status).toBe(422)
    expect(err.code).toBe('VALIDATION_ERROR')
    expect(err.fieldErrors.map((f) => f.field).sort()).toEqual(['question', 'title'])
  })
})
