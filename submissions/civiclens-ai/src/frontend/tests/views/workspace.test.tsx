import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import type { AuditEntry, EvidenceItem, Investigation, Recommendation } from '../../src/api/schemas'
import { API, auditEntry, complaint, evidenceItem, investigation, recommendation, runResult } from '../fixtures'
import { apiError, authed, server } from '../msw'
import { renderApp } from '../render'

interface Calls {
  attach: Array<Record<string, unknown>>
  run: Array<Record<string, unknown>>
  propose: Array<Record<string, unknown>>
}

function fakeWorkspace(
  opts: {
    investigation?: Partial<Investigation>
    evidence?: EvidenceItem[]
    recs?: Recommendation[]
    audit?: AuditEntry[]
  } = {},
): Calls {
  const calls: Calls = { attach: [], run: [], propose: [] }
  const inv = investigation(opts.investigation)
  let evidence = opts.evidence ?? []
  server.use(
    http.get(`${API}/api/investigations/:id`, authed(() => HttpResponse.json(inv))),
    http.get(`${API}/api/investigations/:id/evidence`, authed(() => HttpResponse.json(evidence))),
    http.get(`${API}/api/investigations/:id/recommendations`, authed(() => HttpResponse.json(opts.recs ?? []))),
    http.get(`${API}/api/investigations/:id/audit`, authed(() => HttpResponse.json(opts.audit ?? []))),
    http.get(`${API}/api/complaints`, () =>
      HttpResponse.json([
        complaint({ complaint_id: 12, title: 'Complaint twelve' }),
        complaint({ complaint_id: 15, title: 'Complaint fifteen', category: 'DRAINAGE' }),
        complaint({ complaint_id: 21, title: 'Complaint twenty-one', is_synthetic: false }),
      ]),
    ),
    http.post(`${API}/api/investigations/:id/evidence`, authed(async ({ request }) => {
      const body = (await request.json()) as { complaint_ids: number[] }
      calls.attach.push(body)
      if (body.complaint_ids.includes(999999)) {
        return apiError(422, 'UNKNOWN_COMPLAINT_IDS', 'Some complaint ids do not exist.', { unknown_ids: [999999] })
      }
      evidence = [...evidence, ...body.complaint_ids.map((id) => evidenceItem({ complaint_id: id, title: `Complaint ${id}` }))]
      return HttpResponse.json(evidence)
    })),
    http.post(`${API}/api/investigations/:id/run`, authed(async ({ request }) => {
      calls.run.push((await request.json()) as Record<string, unknown>)
      return HttpResponse.json(runResult())
    })),
    http.post(`${API}/api/investigations/:id/recommendations`, authed(async ({ request }) => {
      calls.propose.push((await request.json()) as Record<string, unknown>)
      return HttpResponse.json(recommendation({ generator_type: 'MANUAL', model_name: null }), { status: 201 })
    })),
  )
  return calls
}

describe('Investigation workspace: reading', () => {
  it('shows the investigation, its question and where it is in the lifecycle', async () => {
    fakeWorkspace({ investigation: { status: 'PENDING_REVIEW' } })
    await renderApp('/investigations/7', { as: 'analyst' })
    expect(await screen.findByTestId('investigation-title')).toHaveTextContent('Pothole cluster triage')
    expect(screen.getByText(/Which neighbourhoods should repair crews visit first/)).toBeInTheDocument()
    expect(screen.getByTestId('investigation-status')).toHaveAttribute('data-status', 'PENDING_REVIEW')
    const steps = screen.getByTestId('step-tracker')
    expect(within(steps).getByText('Pending review').closest('li')).toHaveAttribute('aria-current', 'step')
  })

  it('shows a failed run as a stopped step', async () => {
    fakeWorkspace({ investigation: { status: 'FAILED' } })
    await renderApp('/investigations/7', { as: 'analyst' })
    const steps = await screen.findByTestId('step-tracker')
    expect(within(steps).getByText('Failed')).toBeInTheDocument()
  })

  it('lists the attached evidence with provenance markers', async () => {
    fakeWorkspace({ evidence: [evidenceItem({ complaint_id: 1 }), evidenceItem({ complaint_id: 2, title: 'Real report', is_synthetic: false })] })
    await renderApp('/investigations/7', { as: 'analyst' })
    const rows = await screen.findAllByTestId('evidence-row')
    expect(rows).toHaveLength(2)
    expect(within(rows[0]).getByTestId('synthetic-badge')).toBeInTheDocument()
    expect(within(rows[1]).queryByTestId('synthetic-badge')).toBeNull()
  })

  it('words the stored evidence note in plain language instead of showing a raw enum', async () => {
    fakeWorkspace({ evidence: [evidenceItem({ complaint_id: 1 })] })
    await renderApp('/investigations/7', { as: 'analyst' })
    const [row] = await screen.findAllByTestId('evidence-row')
    expect(row).toHaveTextContent('Cited by the rule-based run (no LLM)')
    expect(row).not.toHaveTextContent('DETERMINISTIC_FALLBACK')
  })

  it('collapses a long evidence list to the first rows and expands on request', async () => {
    const many = Array.from({ length: 22 }, (_, i) => evidenceItem({ complaint_id: i + 1, title: `Complaint ${i + 1}` }))
    fakeWorkspace({ evidence: many })
    const { user } = await renderApp('/investigations/7', { as: 'analyst' })
    expect(await screen.findAllByTestId('evidence-row')).toHaveLength(8)
    const status = screen.getByTestId('evidence-collapse')
    expect(status).toHaveTextContent('Showing 8 of 22 complaints')
    const toggle = within(status).getByRole('button', { name: /Show all 22/ })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await user.click(toggle)
    expect(screen.getAllByTestId('evidence-row')).toHaveLength(22)
    expect(within(screen.getByTestId('evidence-collapse')).getByRole('button', { name: /Show fewer/ })).toHaveAttribute('aria-expanded', 'true')
    await user.click(within(screen.getByTestId('evidence-collapse')).getByRole('button', { name: /Show fewer/ }))
    expect(screen.getAllByTestId('evidence-row')).toHaveLength(8)
  })

  it('does not collapse a list that is only slightly over the limit (hiding one row saves nothing)', async () => {
    fakeWorkspace({ evidence: Array.from({ length: 9 }, (_, i) => evidenceItem({ complaint_id: i + 1 })) })
    await renderApp('/investigations/7', { as: 'analyst' })
    expect(await screen.findAllByTestId('evidence-row')).toHaveLength(9)
    expect(screen.queryByTestId('evidence-collapse')).toBeNull()
  })

  it('shows every recommendation with its generator, priority, confidence and evidence', async () => {
    fakeWorkspace({
      recs: [
        recommendation({ recommendation_id: 11 }),
        recommendation({ recommendation_id: 12, generator_type: 'LLM', model_name: 'anthropic:some-model', priority: 2, confidence: 0.8, evidence_ids: [3, 4] }),
      ],
    })
    await renderApp('/investigations/7', { as: 'analyst' })
    const [rules, llm] = await screen.findAllByTestId('recommendation')
    expect(within(rules).getByTestId('generator-badge')).toHaveTextContent('Rule-based · no LLM')
    expect(within(rules).getByTestId('priority-badge')).toHaveTextContent('P1')
    expect(within(rules).getByRole('meter')).toHaveAccessibleName('Rule-based score (not a model probability)')
    expect(within(llm).getByTestId('generator-badge')).toHaveTextContent('AI model (LLM)')
    expect(within(llm).getByRole('meter')).toHaveAccessibleName('Model-reported confidence')
    expect(within(llm).getByTestId('evidence-ids')).toHaveTextContent('#3')
    expect(within(llm).getByTestId('evidence-ids')).toHaveTextContent('#4')
  })

  it('shows tool activity from the audit log and who issued the tool calls', async () => {
    fakeWorkspace({
      audit: [
        auditEntry({ audit_id: 1, actor_type: 'USER', actor_id: 'alice', action: 'INVESTIGATION_CREATED', tool_name: null, input_json: '{"title": "x"}', output_summary: 'status=OPEN' }),
        auditEntry({ audit_id: 2, tool_name: 'hotspot_summary', output_summary: '3 rows' }),
        auditEntry({ audit_id: 3, tool_name: 'search_complaints', output_summary: '9 rows', input_json: '{"category": "POTHOLE", "geo_cell": "C5499_15535"}' }),
        auditEntry({ audit_id: 4, action: 'AGENT_RUN_COMPLETED', tool_name: null, input_json: '{"generator": "DETERMINISTIC_FALLBACK", "recommendations": 1}', output_summary: 'status=PENDING_REVIEW' }),
      ],
    })
    const { user } = await renderApp('/investigations/7', { as: 'analyst' })
    const entries = await screen.findAllByTestId('audit-entry')
    expect(entries).toHaveLength(4)
    expect(screen.getByTestId('audit-summary')).toHaveTextContent('4 audit entries · 2 tool calls')
    const origin = screen.getByTestId('tool-activity-origin')
    expect(origin).toHaveTextContent('Tool calls in this run were issued by')
    expect(origin).toHaveTextContent('Rule-based · no LLM')
    expect(origin).toHaveTextContent('not made by a language model')
    expect(within(entries[2]).getByText('geo_cell')).toBeInTheDocument()

    await user.click(screen.getByLabelText('Tool activity only'))
    expect(screen.getAllByTestId('audit-entry').map((e) => e.getAttribute('data-tool'))).toEqual(['hotspot_summary', 'search_complaints'])
  })

  it('survives truncated audit JSON (the server truncates long payloads)', async () => {
    fakeWorkspace({ audit: [auditEntry({ input_json: '{"category": "POTHOLE", "ids": [1, 2, 3' })] })
    await renderApp('/investigations/7', { as: 'analyst' })
    expect(await screen.findByTestId('audit-entry')).toHaveTextContent('Tool call')
  })

  it('a bad id shows not-found; a missing investigation shows the 404 from the API', async () => {
    const bad = await renderApp('/investigations/abc', { as: 'analyst' })
    expect(await screen.findByText('Page not found')).toBeInTheDocument()
    bad.unmount()
    server.use(http.get(`${API}/api/investigations/:id`, authed(() => apiError(404, 'INVESTIGATION_NOT_FOUND', 'Investigation not found.'))))
    await renderApp('/investigations/999', { as: 'analyst' })
    const notice = await screen.findByTestId('error-notice')
    expect(notice).toHaveAttribute('data-status', '404')
    expect(notice).toHaveTextContent('Investigation not found.')
  })
})

describe('Investigation workspace: attaching evidence', () => {
  it('attaches by ID and refreshes the evidence list', async () => {
    const calls = fakeWorkspace()
    const { user } = await renderApp('/investigations/7', { as: 'analyst' })
    await user.type(await screen.findByLabelText('Attach by complaint ID'), '12, #15 12')
    await user.click(screen.getByRole('button', { name: 'Attach' }))
    expect(await screen.findByText('Attached 2 complaints as evidence.')).toBeInTheDocument()
    expect(calls.attach).toEqual([{ complaint_ids: [12, 15] }])
    await waitFor(() => expect(screen.getAllByTestId('evidence-row')).toHaveLength(2))
  })

  it('catches malformed IDs in the browser without sending anything', async () => {
    const calls = fakeWorkspace()
    const { user } = await renderApp('/investigations/7', { as: 'analyst' })
    await user.type(await screen.findByLabelText('Attach by complaint ID'), '12, abc')
    await user.click(screen.getByRole('button', { name: 'Attach' }))
    expect(screen.getByText('Not a valid complaint ID: abc')).toBeInTheDocument()
    expect(calls.attach).toHaveLength(0)
  })

  it('422: shows the server rejecting a complaint ID that does not exist, naming it', async () => {
    fakeWorkspace()
    const { user } = await renderApp('/investigations/7', { as: 'analyst' })
    await user.type(await screen.findByLabelText('Attach by complaint ID'), '999999')
    await user.click(screen.getByRole('button', { name: 'Attach' }))
    const notice = await screen.findByTestId('error-notice')
    expect(notice).toHaveAttribute('data-status', '422')
    expect(notice).toHaveAttribute('data-code', 'UNKNOWN_COMPLAINT_IDS')
    expect(notice).toHaveTextContent('Complaint #999999')
    expect(screen.queryAllByTestId('evidence-row')).toHaveLength(0) // nothing was saved
  })

  it('the picker lists complaints, marks attached ones, and attaches the selection', async () => {
    const calls = fakeWorkspace({ evidence: [evidenceItem({ complaint_id: 12 })] })
    const { user } = await renderApp('/investigations/7', { as: 'analyst' })
    await user.click(await screen.findByRole('button', { name: 'Attach evidence' }))
    const dialog = await screen.findByRole('dialog', { name: 'Attach evidence' })
    const boxes = await within(dialog).findAllByTestId('picker-checkbox')
    expect(boxes).toHaveLength(3)
    expect(boxes[0]).toBeDisabled() // #12 is already attached
    expect(within(dialog).getByText('Already attached')).toBeInTheDocument()
    expect(within(dialog).getByRole('button', { name: /Attach\s*selected/ })).toBeDisabled()

    await user.click(boxes[1])
    await user.click(boxes[2])
    await user.click(within(dialog).getByRole('button', { name: 'Attach 2 selected' }))
    expect(await screen.findByText('Attached 2 complaints as evidence.')).toBeInTheDocument()
    expect(calls.attach).toEqual([{ complaint_ids: [15, 21] }])
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('the picker filters by search text', async () => {
    fakeWorkspace()
    const { user } = await renderApp('/investigations/7', { as: 'analyst' })
    await user.click(await screen.findByRole('button', { name: 'Attach evidence' }))
    const dialog = await screen.findByRole('dialog')
    await within(dialog).findAllByTestId('picker-checkbox')
    await user.type(within(dialog).getByLabelText('Search'), 'fifteen')
    expect(within(dialog).getAllByTestId('picker-checkbox')).toHaveLength(1)
  })

  it('a reviewer cannot attach evidence or propose (no controls)', async () => {
    fakeWorkspace()
    await renderApp('/investigations/7', { as: 'reviewer' })
    await screen.findByTestId('workspace')
    expect(screen.queryByRole('button', { name: 'Attach evidence' })).toBeNull()
    expect(screen.queryByLabelText('Attach by complaint ID')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Propose manually' })).toBeNull()
    expect(screen.getByText(/Only analysts can run investigations/)).toBeInTheDocument()
  })

  it('a closed investigation accepts no new evidence or runs', async () => {
    fakeWorkspace({ investigation: { status: 'CLOSED', closed_at: '2026-11-09T10:00:00' } })
    await renderApp('/investigations/7', { as: 'analyst' })
    await screen.findByTestId('workspace')
    expect(screen.queryByRole('button', { name: 'Attach evidence' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Run investigation' })).toBeNull()
    expect(screen.getByText('This investigation is closed')).toBeInTheDocument()
  })
})

describe('Investigation workspace: running it', () => {
  it('rule-based run: sends the parameters and presents the result as NOT an AI result', async () => {
    const calls = fakeWorkspace()
    const { user } = await renderApp('/investigations/7', { as: 'analyst' })
    await user.click(await screen.findByLabelText(/Rule-based only/))
    await user.click(screen.getByRole('button', { name: 'Run investigation' }))
    const result = await screen.findByTestId('run-result')
    expect(calls.run).toEqual([{ mode: 'fallback', days: 30, category: null, max_hotspots: 3 }])
    expect(within(result).getByTestId('generator-badge')).toHaveTextContent('Rule-based · no LLM')
    expect(within(result).getByTestId('run-notice')).toHaveTextContent('NO LLM WAS USED')
    expect(within(result).getByTestId('fallback-reason')).toHaveTextContent('No LLM provider configured')
    expect(result).not.toHaveTextContent('AI model (LLM)')
    expect(within(result).getByTestId('generator-explanation')).toHaveTextContent('No AI model was involved')
    expect(screen.getByText('Run finished: 1 recommendation proposed.')).toBeInTheDocument()
  })

  it('sends the chosen look-back window, category and hotspot limit', async () => {
    const calls = fakeWorkspace()
    const { user } = await renderApp('/investigations/7', { as: 'analyst' })
    const days = await screen.findByLabelText('Look-back window (days)')
    await user.clear(days)
    await user.type(days, '90')
    await user.selectOptions(screen.getByLabelText('Category'), 'POTHOLE')
    await user.selectOptions(screen.getByLabelText('Max hotspots'), '5')
    await user.click(screen.getByRole('button', { name: 'Run investigation' }))
    await screen.findByTestId('run-result')
    expect(calls.run).toEqual([{ mode: 'auto', days: 90, category: 'POTHOLE', max_hotspots: 5 }])
  })

  it('auto mode without an LLM: explains up front that the fallback will be used', async () => {
    fakeWorkspace()
    await renderApp('/investigations/7', { as: 'analyst' })
    expect(await screen.findByText('No language model is configured on this server')).toBeInTheDocument()
    expect(screen.getByText(/Auto mode will use the rule-based fallback/)).toBeInTheDocument()
  })

  it('LLM-only without an LLM: warns first, then shows the 409 when run (never a silent fallback)', async () => {
    fakeWorkspace()
    server.use(http.post(`${API}/api/investigations/:id/run`, authed(() => apiError(409, 'LLM_NOT_CONFIGURED', 'No LLM provider is configured (LLM_PROVIDER=none).', { llm_configured: false }))))
    const { user } = await renderApp('/investigations/7', { as: 'analyst' })
    await user.click(await screen.findByLabelText(/LLM only/))
    expect(screen.getByText(/LLM-only mode will be refused with LLM_NOT_CONFIGURED/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Run investigation' }))
    const notice = await screen.findByTestId('error-notice')
    expect(notice).toHaveAttribute('data-status', '409')
    expect(notice).toHaveAttribute('data-code', 'LLM_NOT_CONFIGURED')
    expect(notice).toHaveTextContent('No LLM is configured on the server')
    expect(screen.queryByTestId('run-result')).toBeNull()
  })

  it('a real LLM run is labelled as an AI model, with its provider and model', async () => {
    fakeWorkspace()
    server.use(
      http.post(`${API}/api/investigations/:id/run`, authed(() =>
        HttpResponse.json(runResult({ generator: 'LLM', model_name: 'anthropic:some-model', llm_configured: true, fallback_reason: null, notice: "Recommendations were generated by the LLM 'anthropic:some-model' using audited Db2 tools." })),
      )),
    )
    const { user } = await renderApp('/investigations/7', { as: 'analyst' })
    await user.click(await screen.findByRole('button', { name: 'Run investigation' }))
    const result = await screen.findByTestId('run-result')
    expect(within(result).getByTestId('generator-badge')).toHaveTextContent('AI model (LLM)')
    expect(within(result).getByTestId('generator-explanation')).toHaveTextContent('anthropic:some-model')
    expect(within(result).queryByTestId('fallback-reason')).toBeNull()
    expect(result).not.toHaveTextContent('NO LLM WAS USED')
  })

  it('409: running an investigation that is no longer runnable', async () => {
    fakeWorkspace()
    server.use(http.post(`${API}/api/investigations/:id/run`, authed(() => apiError(409, 'INVESTIGATION_NOT_RUNNABLE', 'Investigation is not runnable.'))))
    const { user } = await renderApp('/investigations/7', { as: 'analyst' })
    await user.click(await screen.findByRole('button', { name: 'Run investigation' }))
    const notice = await screen.findByTestId('error-notice')
    expect(notice).toHaveAttribute('data-code', 'INVESTIGATION_NOT_RUNNABLE')
    expect(notice).toHaveTextContent('This investigation cannot be run')
  })

  it('502: an agent failure is reported as the agent failing', async () => {
    fakeWorkspace()
    server.use(http.post(`${API}/api/investigations/:id/run`, authed(() => apiError(502, 'EVIDENCE_REJECTED', 'Every recommendation cited ungrounded evidence.'))))
    const { user } = await renderApp('/investigations/7', { as: 'analyst' })
    await user.click(await screen.findByRole('button', { name: 'Run investigation' }))
    const notice = await screen.findByTestId('error-notice')
    expect(notice).toHaveAttribute('data-status', '502')
    expect(notice).toHaveTextContent('The investigation agent could not finish')
  })

  it('refuses an invalid look-back window in the browser', async () => {
    const calls = fakeWorkspace()
    const { user } = await renderApp('/investigations/7', { as: 'analyst' })
    const days = await screen.findByLabelText('Look-back window (days)')
    await user.clear(days)
    await user.type(days, '0')
    expect(screen.getByText('Enter a whole number from 1 to 365.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Run investigation' })).toBeDisabled()
    expect(calls.run).toHaveLength(0)
  })
})

describe('Investigation workspace: manual recommendations', () => {
  it('needs a summary, an explanation and attached evidence before anything is sent', async () => {
    const calls = fakeWorkspace({ evidence: [evidenceItem({ complaint_id: 12, title: 'Complaint twelve' })] })
    const { user } = await renderApp('/investigations/7', { as: 'analyst' })
    await user.click(await screen.findByRole('button', { name: 'Propose manually' }))
    const dialog = await screen.findByRole('dialog', { name: 'Propose a recommendation' })
    expect(dialog).toHaveTextContent('recorded as a manual recommendation')
    await user.click(within(dialog).getByRole('button', { name: 'Propose' }))
    expect(within(dialog).getByText(/Summary must be at least 5 characters/)).toBeInTheDocument()
    expect(within(dialog).getByText(/Explanation must be at least 10 characters/)).toBeInTheDocument()
    expect(within(dialog).getByText('Select at least one piece of attached evidence.')).toBeInTheDocument()
    expect(calls.propose).toHaveLength(0)
  })

  it('submits a valid manual proposal citing attached evidence', async () => {
    const calls = fakeWorkspace({ evidence: [evidenceItem({ complaint_id: 12, title: 'Complaint twelve' })] })
    const { user } = await renderApp('/investigations/7', { as: 'analyst' })
    await user.click(await screen.findByRole('button', { name: 'Propose manually' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Summary'), 'Clear the blocked drain')
    await user.type(within(dialog).getByLabelText('Explanation'), 'The cited complaint shows recurring waterlogging.')
    await user.selectOptions(within(dialog).getByLabelText('Priority'), '2')
    await user.click(within(dialog).getByLabelText(/#12/))
    await user.click(within(dialog).getByRole('button', { name: 'Propose' }))
    expect(await screen.findByText('Manual recommendation proposed. It is awaiting review.')).toBeInTheDocument()
    expect(calls.propose).toEqual([
      { summary: 'Clear the blocked drain', rationale: 'The cited complaint shows recurring waterlogging.', priority: 2, confidence: 0.5, evidence_ids: [12] },
    ])
  })

  it('422: evidence that is not attached is rejected by the server and shown', async () => {
    fakeWorkspace({ evidence: [evidenceItem({ complaint_id: 12, title: 'Complaint twelve' })] })
    server.use(
      http.post(`${API}/api/investigations/:id/recommendations`, authed(() => apiError(422, 'EVIDENCE_NOT_ATTACHED', 'Evidence ids are not attached to this investigation.', { unattached_ids: [12] }))),
    )
    const { user } = await renderApp('/investigations/7', { as: 'analyst' })
    await user.click(await screen.findByRole('button', { name: 'Propose manually' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Summary'), 'Clear the blocked drain')
    await user.type(within(dialog).getByLabelText('Explanation'), 'The cited complaint shows recurring waterlogging.')
    await user.click(within(dialog).getByLabelText(/#12/))
    await user.click(within(dialog).getByRole('button', { name: 'Propose' }))
    const notice = await within(dialog).findByTestId('error-notice')
    expect(notice).toHaveAttribute('data-code', 'EVIDENCE_NOT_ATTACHED')
    expect(notice).toHaveTextContent('Complaint #12')
  })
})

describe('Investigations list', () => {
  it('lists investigations with status and creator, and filters by status on the server', async () => {
    const requested: Array<string | null> = []
    server.use(
      http.get(`${API}/api/investigations`, authed(({ request }) => {
        requested.push(new URL(request.url).searchParams.get('status'))
        return HttpResponse.json([investigation({ investigation_id: 7 }), investigation({ investigation_id: 8, title: 'Second one', status: 'CLOSED', closed_at: '2026-11-09T10:00:00' })])
      })),
    )
    const { user } = await renderApp('/investigations', { as: 'analyst' })
    const rows = await screen.findAllByTestId('investigation-row')
    expect(rows).toHaveLength(2)
    expect(within(rows[1]).getByTestId('investigation-status')).toHaveAttribute('data-status', 'CLOSED')
    await user.click(screen.getByRole('button', { name: 'Closed' }))
    await waitFor(() => expect(requested).toContain('CLOSED'))
  })

  it('creates an investigation (validated first) and opens it', async () => {
    let posted: Record<string, unknown> | null = null
    server.use(
      http.post(`${API}/api/investigations`, authed(async ({ request }) => {
        posted = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(investigation({ investigation_id: 42, title: 'Brand new one' }), { status: 201 })
      })),
      http.get(`${API}/api/investigations/42`, authed(() => HttpResponse.json(investigation({ investigation_id: 42, title: 'Brand new one' })))),
    )
    fakeWorkspace()
    server.use(http.get(`${API}/api/investigations/42`, authed(() => HttpResponse.json(investigation({ investigation_id: 42, title: 'Brand new one' })))))
    const { user } = await renderApp('/investigations', { as: 'analyst' })
    await user.click(await screen.findByRole('button', { name: 'New investigation' }))
    const dialog = await screen.findByRole('dialog', { name: 'New investigation' })
    await user.click(within(dialog).getByRole('button', { name: 'Create investigation' }))
    expect(within(dialog).getByText(/Title must be at least 3 characters/)).toBeInTheDocument()
    expect(posted).toBeNull()

    await user.type(within(dialog).getByLabelText('Title'), 'Brand new one')
    await user.type(within(dialog).getByLabelText('Question'), 'What is going on?')
    await user.click(within(dialog).getByRole('button', { name: 'Create investigation' }))
    expect(await screen.findByTestId('investigation-title')).toHaveTextContent('Brand new one')
    expect(posted).toEqual({ title: 'Brand new one', question: 'What is going on?' })
  })

  it('a reviewer sees the list read-only', async () => {
    await renderApp('/investigations', { as: 'reviewer' })
    await screen.findAllByTestId('investigation-row')
    expect(screen.queryByRole('button', { name: 'New investigation' })).toBeNull()
    expect(screen.getByText('Read-only for your role')).toBeInTheDocument()
  })

  it('shows the error when the list cannot be loaded (503)', async () => {
    server.use(http.get(`${API}/api/investigations`, authed(() => apiError(503, 'DB_UNAVAILABLE', 'down'))))
    await renderApp('/investigations', { as: 'analyst' })
    expect(await screen.findByTestId('error-notice')).toHaveAttribute('data-status', '503')
  })
})
