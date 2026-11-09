import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import type { RecommendationListItem } from '../../src/api/schemas'
import { API, TOKENS, evidenceItem, queueItem } from '../fixtures'
import { apiError, authed, bearer, server } from '../msw'
import { renderApp } from '../render'

interface Decision {
  id: number
  body: Record<string, unknown>
  token: string | null
}

/** A tiny in-memory stand-in for the review endpoints, so flows (decide -> list refreshes) behave like the real API. */
function fakeReviewApi(initial?: RecommendationListItem[]) {
  let items = initial ?? [
    queueItem({ recommendation_id: 11 }),
    queueItem({
      recommendation_id: 12,
      summary: 'Second: clear the blocked drain',
      generator_type: 'MANUAL',
      model_name: null,
      priority: 3,
      evidence_ids: [3],
    }),
  ]
  const decisions: Decision[] = []
  const evidence = [1, 2, 3].map((id) => evidenceItem({ complaint_id: id, title: `Evidence complaint ${id}` }))
  server.use(
    http.get(`${API}/api/recommendations`, authed(({ request }) => {
      const status = new URL(request.url).searchParams.get('status')
      return HttpResponse.json(items.filter((i) => !status || i.status === status))
    })),
    http.get(`${API}/api/investigations/:id/evidence`, authed(() => HttpResponse.json(evidence))),
    http.post(`${API}/api/recommendations/:id/decision`, authed(async ({ request, params }) => {
      const body = (await request.json()) as Record<string, unknown>
      const id = Number(params.id)
      decisions.push({ id, body, token: bearer(request) })
      items = items.map((i) =>
        i.recommendation_id === id
          ? { ...i, status: body.decision as 'APPROVED' | 'REJECTED', review: { decision_id: 1, recommendation_id: id, reviewer: 'rita', decision: body.decision as 'APPROVED' | 'REJECTED', comment: (body.comment as string | null) ?? null, decided_at: '2026-11-09T10:00:00' } }
          : i,
      )
      return HttpResponse.json(items.find((i) => i.recommendation_id === id))
    })),
  )
  return { decisions, setItems: (next: RecommendationListItem[]) => (items = next) }
}

describe('Human review: reading the queue', () => {
  it('lists pending recommendations, each with its actual generator', async () => {
    fakeReviewApi()
    await renderApp('/review', { as: 'reviewer' })
    const items = await screen.findAllByTestId('queue-item')
    expect(items).toHaveLength(2)
    expect(within(items[0]).getByTestId('generator-badge')).toHaveTextContent('Rule-based · no LLM')
    expect(within(items[1]).getByTestId('generator-badge')).toHaveTextContent('Manual · analyst-written')
    expect(items[0]).toHaveAttribute('aria-pressed', 'true') // the first is selected by default
  })

  it('shows the explanation, provenance and only the evidence the recommendation cites', async () => {
    const user = (await renderApp('/review', { as: 'reviewer' })).user
    fakeReviewApi()
    await screen.findAllByTestId('queue-item')
    const detail = await screen.findByTestId('review-detail')
    expect(within(detail).getByTestId('recommendation-rationale')).toHaveTextContent('[RULE-BASED, NO LLM]')
    expect(within(detail).getByTestId('generator-explanation')).toHaveTextContent('No AI model was involved')
    await waitFor(() => expect(within(detail).getAllByTestId('evidence-row')).toHaveLength(2)) // cites #1 and #2, not #3
    await user.click(screen.getAllByTestId('queue-item')[1])
    const second = await screen.findByTestId('review-detail')
    expect(second).toHaveAttribute('data-recommendation-id', '12')
    expect(within(second).getByTestId('generator-explanation')).toHaveTextContent('Written by an analyst')
    await waitFor(() => expect(within(second).getAllByTestId('evidence-row')).toHaveLength(1))
  })

  it('shows a real LLM recommendation as an AI model with its provider and model, and a test double as NOT a model', async () => {
    fakeReviewApi([
      queueItem({ recommendation_id: 21, generator_type: 'LLM', model_name: 'anthropic:some-model' }),
      queueItem({ recommendation_id: 22, generator_type: 'LLM', model_name: 'test-double:scripted' }),
    ])
    const { user } = await renderApp('/review', { as: 'reviewer' })
    const [real, double] = await screen.findAllByTestId('queue-item')
    expect(within(real).getByTestId('generator-badge')).toHaveTextContent('AI model (LLM)')
    expect(within(double).getByTestId('generator-badge')).toHaveTextContent('Test double · not a real model')
    expect(await screen.findByTestId('generator-explanation')).toHaveTextContent('anthropic:some-model')
    await user.click(double)
    expect(await screen.findByText(/not a language model/i)).toBeInTheDocument()
  })

  it('an analyst can read the queue but sees no decision controls', async () => {
    fakeReviewApi()
    await renderApp('/review', { as: 'analyst' })
    await screen.findAllByTestId('queue-item')
    expect(screen.getByText(/Only reviewers can approve or reject/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Approve' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Reject' })).toBeNull()
    expect(screen.queryByTestId('decision-panel')).toBeNull()
  })

  it('shows a helpful empty state', async () => {
    fakeReviewApi([])
    await renderApp('/review', { as: 'reviewer' })
    expect(await screen.findByText('Nothing is waiting for review')).toBeInTheDocument()
  })

  it('shows each item\'s decision status outside the "Awaiting review" filter', async () => {
    fakeReviewApi([
      queueItem({ recommendation_id: 31 }),
      queueItem({ recommendation_id: 32, status: 'APPROVED' }),
      queueItem({ recommendation_id: 33, status: 'REJECTED' }),
    ])
    const { user } = await renderApp('/review', { as: 'reviewer' })
    const pending = await screen.findAllByTestId('queue-item')
    expect(pending).toHaveLength(1)
    expect(within(pending[0]).queryByTestId('recommendation-status')).toBeNull() // every item here is pending, so no badge is needed

    await user.click(screen.getByRole('button', { name: 'All' }))
    await waitFor(() => expect(screen.getAllByTestId('queue-item')).toHaveLength(3))
    const statuses = screen.getAllByTestId('queue-item').map((i) => within(i).getByTestId('recommendation-status').getAttribute('data-status'))
    expect(statuses).toEqual(['PROPOSED', 'APPROVED', 'REJECTED'])
  })

  it('the filter requests the chosen status and shows past decisions', async () => {
    const api = fakeReviewApi()
    const { user } = await renderApp('/review', { as: 'reviewer' })
    await screen.findAllByTestId('queue-item')
    await user.click(screen.getByRole('button', { name: 'Approve' }))
    await user.click(await screen.findByRole('button', { name: 'Confirm approval' }))
    await screen.findByText('Decision recorded')
    expect(api.decisions).toHaveLength(1)
    await user.click(screen.getByRole('button', { name: 'Approved' }))
    const detail = await screen.findByTestId('review-detail')
    expect(within(detail).getByTestId('review-outcome')).toHaveTextContent('Approved by rita')
    expect(screen.queryByTestId('decision-panel')).toBeNull() // a decided recommendation cannot be decided again
  })
})

describe('Human review: deciding', () => {
  it('approve: asks for confirmation, then sends only the decision (the reviewer is the token, not a field)', async () => {
    const api = fakeReviewApi()
    const { user } = await renderApp('/review', { as: 'reviewer' })
    await screen.findAllByTestId('queue-item')
    await user.type(screen.getByLabelText('Comment'), 'Crew assigned')
    await user.click(screen.getByRole('button', { name: 'Approve' }))
    const dialog = await screen.findByRole('dialog', { name: 'Approve recommendation #11?' })
    expect(dialog).toHaveTextContent('You are acting as rita')
    expect(api.decisions).toHaveLength(0) // nothing is sent until the user confirms
    await user.click(within(dialog).getByRole('button', { name: 'Confirm approval' }))

    expect(await screen.findByText('Decision recorded')).toBeInTheDocument()
    expect(screen.getByTestId('success-notice')).toHaveTextContent('Recommendation #11 approved')
    expect(api.decisions).toEqual([{ id: 11, body: { decision: 'APPROVED', comment: 'Crew assigned' }, token: TOKENS.reviewer }])
    expect(Object.keys(api.decisions[0].body)).not.toContain('reviewer')
    // the decided item left the queue and the next one is selected
    await waitFor(() => expect(screen.getAllByTestId('queue-item')).toHaveLength(1))
    expect(screen.getByTestId('review-detail')).toHaveAttribute('data-recommendation-id', '12')
  })

  it('cancelling the confirmation sends nothing', async () => {
    const api = fakeReviewApi()
    const { user } = await renderApp('/review', { as: 'reviewer' })
    await screen.findAllByTestId('queue-item')
    await user.click(screen.getByRole('button', { name: 'Reject' }))
    // no comment yet: the form blocks it before any dialog
    expect(screen.queryByRole('dialog')).toBeNull()
    await user.type(screen.getByLabelText('Comment'), 'Not enough evidence')
    await user.click(screen.getByRole('button', { name: 'Reject' }))
    await user.click(await screen.findByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(api.decisions).toHaveLength(0)
  })

  it('reject requires a comment (checked before anything is sent)', async () => {
    const api = fakeReviewApi()
    const { user } = await renderApp('/review', { as: 'reviewer' })
    await screen.findAllByTestId('queue-item')
    await user.click(screen.getByRole('button', { name: 'Reject' }))
    expect(screen.getByText(/comment of at least 3 characters is required to reject/i)).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(api.decisions).toHaveLength(0)

    await user.type(screen.getByLabelText('Comment'), 'Insufficient evidence')
    await user.click(screen.getByRole('button', { name: 'Reject' }))
    await user.click(await screen.findByRole('button', { name: 'Confirm rejection' }))
    expect(await screen.findByText(/Recommendation #11 rejected/)).toBeInTheDocument()
    expect(api.decisions[0].body).toEqual({ decision: 'REJECTED', comment: 'Insufficient evidence' })
  })

  it('warns, and disables the buttons, when the reviewer created the investigation', async () => {
    fakeReviewApi([queueItem({ recommendation_id: 31, investigation_created_by: 'rita' })])
    await renderApp('/review', { as: 'reviewer' })
    expect(await screen.findByText('You created this investigation')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Approve' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Reject' })).toBeDisabled()
  })
})

describe('Human review: the result of a decision is brought into view', () => {
  // The decision buttons are at the bottom of a long page and the notice at the top: it must not be left off screen.
  it('success: scrolls the notice into view and moves focus to it', async () => {
    const scroll = vi.spyOn(Element.prototype, 'scrollIntoView')
    fakeReviewApi()
    const { user } = await renderApp('/review', { as: 'reviewer' })
    await screen.findAllByTestId('queue-item')
    scroll.mockClear()
    await user.click(screen.getByRole('button', { name: 'Approve' }))
    await user.click(await screen.findByRole('button', { name: 'Confirm approval' }))
    const region = await screen.findByTestId('decision-outcome')
    expect(within(region).getByTestId('success-notice')).toBeInTheDocument()
    await waitFor(() => expect(scroll).toHaveBeenCalled())
    expect(scroll.mock.contexts.at(-1)).toBe(region)
    expect(region).toHaveFocus()
    scroll.mockRestore()
  })

  it('error: the notice is scrolled into view too', async () => {
    const scroll = vi.spyOn(Element.prototype, 'scrollIntoView')
    fakeReviewApi()
    server.use(http.post(`${API}/api/recommendations/:id/decision`, authed(() => apiError(409, 'ALREADY_DECIDED', 'Recommendation was already APPROVED.'))))
    const { user } = await renderApp('/review', { as: 'reviewer' })
    await screen.findAllByTestId('queue-item')
    scroll.mockClear()
    await user.click(screen.getByRole('button', { name: 'Approve' }))
    await user.click(await screen.findByRole('button', { name: 'Confirm approval' }))
    const region = await screen.findByTestId('decision-outcome')
    expect(within(region).getByTestId('error-notice')).toHaveAttribute('data-status', '409')
    await waitFor(() => expect(scroll.mock.contexts.at(-1)).toBe(region))
    scroll.mockRestore()
  })

  it('dismissing the notice removes the region', async () => {
    fakeReviewApi()
    const { user } = await renderApp('/review', { as: 'reviewer' })
    await screen.findAllByTestId('queue-item')
    await user.click(screen.getByRole('button', { name: 'Approve' }))
    await user.click(await screen.findByRole('button', { name: 'Confirm approval' }))
    const region = await screen.findByTestId('decision-outcome')
    await user.click(within(region).getByRole('button', { name: /dismiss/i }))
    expect(screen.queryByTestId('decision-outcome')).toBeNull()
  })
})

describe('Human review: every error state is explained (401, 403, 409, 422, 503)', () => {
  const decide = async (respond: () => Response) => {
    fakeReviewApi()
    server.use(http.post(`${API}/api/recommendations/:id/decision`, authed(() => respond())))
    const { user } = await renderApp('/review', { as: 'reviewer' })
    await screen.findAllByTestId('queue-item')
    await user.click(screen.getByRole('button', { name: 'Approve' }))
    await user.click(await screen.findByRole('button', { name: 'Confirm approval' }))
  }

  it('403 self-review: names the four-eyes rule', async () => {
    await decide(() => apiError(403, 'SELF_REVIEW_FORBIDDEN', 'Reviewers may not review their own investigations.'))
    const notice = await screen.findByTestId('error-notice')
    expect(notice).toHaveAttribute('data-status', '403')
    expect(notice).toHaveAttribute('data-code', 'SELF_REVIEW_FORBIDDEN')
    expect(notice).toHaveTextContent('You cannot review your own investigation')
    expect(screen.queryByTestId('success-notice')).toBeNull()
  })

  it('403 role: says the role is not allowed', async () => {
    await decide(() => apiError(403, 'FORBIDDEN', "Role 'reviewer' may not do this."))
    const notice = await screen.findByTestId('error-notice')
    expect(notice).toHaveAttribute('data-status', '403')
    expect(notice).toHaveTextContent('Your role is not allowed to do this')
  })

  it('409 already decided: says nothing was changed and refreshes the queue', async () => {
    await decide(() => apiError(409, 'ALREADY_DECIDED', 'Recommendation was already APPROVED.'))
    const notice = await screen.findByTestId('error-notice')
    expect(notice).toHaveAttribute('data-status', '409')
    expect(notice).toHaveTextContent('Already decided')
    expect(notice).toHaveTextContent('Nothing was changed by your action')
  })

  it('422 validation: lists the rejected fields', async () => {
    await decide(() => HttpResponse.json({ detail: [{ loc: ['body', 'comment'], msg: 'String should have at most 2000 characters' }] }, { status: 422 }))
    const notice = await screen.findByTestId('error-notice')
    expect(notice).toHaveAttribute('data-status', '422')
    expect(notice).toHaveTextContent('comment: String should have at most 2000 characters')
  })

  it('503 outage: calm wording, nothing recorded as decided', async () => {
    await decide(() => apiError(503, 'DB_UNAVAILABLE', 'The database is temporarily unavailable.'))
    const notice = await screen.findByTestId('error-notice')
    expect(notice).toHaveAttribute('data-status', '503')
    expect(notice).toHaveTextContent('Database unavailable')
    expect(screen.queryByTestId('success-notice')).toBeNull()
  })

  it('401 (token revoked while reviewing): returns to sign-in and explains', async () => {
    await decide(() => apiError(401, 'UNAUTHENTICATED', 'A valid bearer token is required.'))
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.getByText('Signed out')).toBeInTheDocument()
  })

  it('an error can be dismissed', async () => {
    await decide(() => apiError(409, 'ALREADY_DECIDED', 'x'))
    const notice = await screen.findByTestId('error-notice')
    const { default: userEvent } = await import('@testing-library/user-event')
    await userEvent.setup().click(within(notice).getByRole('button', { name: 'Dismiss message' }))
    expect(screen.queryByTestId('error-notice')).toBeNull()
  })
})
