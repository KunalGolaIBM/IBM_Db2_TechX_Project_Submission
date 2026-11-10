import type { Page } from '@playwright/test'
import { apiGet, creds, expect, seedPendingRecommendation, signIn, test } from './fixtures'

interface Rec {
  recommendation_id: number
  investigation_id: number
  status: string
  generator_type: string
  evidence_ids: number[]
  review: null | { reviewer: string; decision: string; comment: string | null }
}
interface Audit { action: string; actor_id: string; success: boolean }

const item = (page: Page, id: number) => page.locator(`[data-testid=queue-item][data-recommendation-id="${id}"]`)
const decide = async (page: Page, id: number, button: 'Approve' | 'Reject', confirm: 'Confirm approval' | 'Confirm rejection') => {
  await page.getByRole('button', { name: button, exact: true }).click()
  await expect(page.getByRole('dialog', { name: new RegExp(`${button} recommendation #${id}\\?`) })).toBeVisible()
  await page.getByRole('button', { name: confirm }).click()
}

test.describe('human review with real reviewers (real backend + Db2)', () => {
  test('a reviewer sees the recommendation with its generator, explanation and the evidence behind it', async ({ page, request }) => {
    const { recommendationId } = await seedPendingRecommendation(request, 'review read')
    await signIn(page, creds.reviewerA, '/review')
    await expect(item(page, recommendationId)).toBeVisible()
    await expect(item(page, recommendationId).getByTestId('generator-badge')).toHaveText('Rule-based · no LLM')
    await item(page, recommendationId).click()

    const detail = page.getByTestId('review-detail')
    await expect(detail).toHaveAttribute('data-recommendation-id', String(recommendationId))
    await expect(detail.getByTestId('generator-explanation')).toContainText('No AI model was involved')
    await expect(detail.getByTestId('recommendation-rationale')).toContainText('[RULE-BASED, NO LLM]')
    const rec = await apiGet<Rec>(request, creds.reviewerA, `/api/recommendations/${recommendationId}`)
    await expect(detail.getByTestId('evidence-row')).toHaveCount(rec.evidence_ids.length)
    await expect(page.getByTestId('decision-panel')).toContainText(`You are acting as ${creds.reviewerA.id}`)
  })

  test('approve: confirm first, then Db2 records the decision, the reviewer and the audit entry atomically', async ({ page, request }) => {
    const { recommendationId, investigationId } = await seedPendingRecommendation(request, 'approve')
    await signIn(page, creds.reviewerA, '/review')
    await item(page, recommendationId).click()
    await page.getByLabel('Comment').fill('E2E approval: crew assigned')
    await decide(page, recommendationId, 'Approve', 'Confirm approval')

    await expect(page.getByTestId('success-notice')).toContainText(`Recommendation #${recommendationId} approved`)
    await expect(item(page, recommendationId)).toHaveCount(0) // it left the pending queue

    const rec = await apiGet<Rec>(request, creds.reviewerA, `/api/recommendations/${recommendationId}`)
    expect(rec.status).toBe('APPROVED')
    expect(rec.review).toMatchObject({ reviewer: creds.reviewerA.id, decision: 'APPROVED', comment: 'E2E approval: crew assigned' })
    const audit = await apiGet<Audit[]>(request, creds.reviewerA, `/api/investigations/${investigationId}/audit`)
    expect(audit.find((a) => a.action === 'REVIEW_APPROVED')).toMatchObject({ actor_id: creds.reviewerA.id, success: true })
    const inv = await apiGet<{ status: string }>(request, creds.reviewerA, `/api/investigations/${investigationId}`)
    expect(inv.status).toBe('CLOSED') // nothing left to review

    await page.getByRole('button', { name: 'Approved', exact: true }).click()
    await expect(item(page, recommendationId)).toBeVisible()
    await item(page, recommendationId).click()
    await expect(page.getByTestId('review-outcome')).toContainText(`Approved by ${creds.reviewerA.id}`)
    await expect(page.getByTestId('decision-panel')).toHaveCount(0) // a decided recommendation cannot be decided again
  })

  test('reject: a comment is required (checked before anything is sent), then it is recorded', async ({ page, request }) => {
    const { recommendationId } = await seedPendingRecommendation(request, 'reject')
    await signIn(page, creds.reviewerB, '/review')
    await item(page, recommendationId).click()
    await page.getByRole('button', { name: 'Reject', exact: true }).click()
    await expect(page.getByText(/comment of at least 3 characters is required to reject/i)).toBeVisible()
    await expect(page.getByRole('dialog')).toHaveCount(0)
    expect((await apiGet<Rec>(request, creds.reviewerB, `/api/recommendations/${recommendationId}`)).status).toBe('PROPOSED')

    await page.getByLabel('Comment').fill('E2E rejection: already scheduled')
    await decide(page, recommendationId, 'Reject', 'Confirm rejection')
    await expect(page.getByTestId('success-notice')).toContainText(`Recommendation #${recommendationId} rejected`)
    const rec = await apiGet<Rec>(request, creds.reviewerB, `/api/recommendations/${recommendationId}`)
    expect(rec.review).toMatchObject({ reviewer: creds.reviewerB.id, decision: 'REJECTED', comment: 'E2E rejection: already scheduled' })
  })

  test('409: two reviewers race for the same recommendation; the second is told it was already decided', async ({ page, request, browser }, testInfo) => {
    const { recommendationId } = await seedPendingRecommendation(request, 'race')
    const baseURL = testInfo.project.use.baseURL as string
    const contextB = await browser.newContext({ baseURL, colorScheme: 'dark' })
    const pageB = await contextB.newPage()
    try {
      // reviewer B opens the recommendation first, and keeps that (soon stale) view open
      await signIn(pageB, creds.reviewerB, '/review')
      await item(pageB, recommendationId).click()
      await expect(pageB.getByTestId('review-detail')).toHaveAttribute('data-recommendation-id', String(recommendationId))

      // reviewer A decides it
      await signIn(page, creds.reviewerA, '/review')
      await item(page, recommendationId).click()
      await decide(page, recommendationId, 'Approve', 'Confirm approval')
      await expect(page.getByTestId('success-notice')).toBeVisible()

      // reviewer B still sees it as pending and tries to reject it
      await pageB.getByLabel('Comment').fill('E2E: too late')
      await decide(pageB, recommendationId, 'Reject', 'Confirm rejection')
      const notice = pageB.getByTestId('error-notice')
      await expect(notice).toBeVisible()
      await expect(notice).toHaveAttribute('data-status', '409')
      await expect(notice).toHaveAttribute('data-code', 'ALREADY_DECIDED')
      await expect(notice).toContainText('Another reviewer decided this recommendation first')
      await expect(pageB.getByTestId('success-notice')).toHaveCount(0)
      await expect(item(pageB, recommendationId)).toHaveCount(0) // B's list refreshed after the conflict
    } finally {
      await contextB.close()
    }
    const rec = await apiGet<Rec>(request, creds.reviewerA, `/api/recommendations/${recommendationId}`)
    expect(rec.review).toMatchObject({ reviewer: creds.reviewerA.id, decision: 'APPROVED' }) // exactly one decision, A's
    expect(rec.status).toBe('APPROVED')
  })

  // The next three provoke real server errors by changing the request on the wire. The responses are the real
  // backend's; only the request is altered (the UI itself would never send these).
  test('403: an analyst token on the decision request is refused by the real server, and nothing changes', async ({ page, request }) => {
    const { recommendationId } = await seedPendingRecommendation(request, 'forbidden')
    await signIn(page, creds.reviewerA, '/review')
    await item(page, recommendationId).click()
    await page.route('**/api/recommendations/*/decision', (route) =>
      route.continue({ headers: { ...route.request().headers(), authorization: `Bearer ${creds.analyst.token}` } }),
    )
    await decide(page, recommendationId, 'Approve', 'Confirm approval')
    const notice = page.getByTestId('error-notice')
    await expect(notice).toBeVisible()
    await expect(notice).toHaveAttribute('data-status', '403')
    await expect(notice).toHaveAttribute('data-code', 'FORBIDDEN')
    await expect(notice).toContainText('Your role is not allowed to do this')
    await expect(page.getByTestId('success-notice')).toHaveCount(0)
    expect((await apiGet<Rec>(request, creds.reviewerA, `/api/recommendations/${recommendationId}`)).status).toBe('PROPOSED')
  })

  test('401: a rejected token during review returns the user to sign-in', async ({ page, request }) => {
    const { recommendationId } = await seedPendingRecommendation(request, 'unauthenticated')
    await signIn(page, creds.reviewerA, '/review')
    await item(page, recommendationId).click()
    await page.route('**/api/recommendations/*/decision', (route) =>
      route.continue({ headers: { ...route.request().headers(), authorization: 'Bearer not-a-valid-token-0000000000' } }),
    )
    await decide(page, recommendationId, 'Approve', 'Confirm approval')
    await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
    await expect(page.getByText('Signed out')).toBeVisible()
    expect((await apiGet<Rec>(request, creds.reviewerB, `/api/recommendations/${recommendationId}`)).status).toBe('PROPOSED')
  })

  test('422: a decision body the server rejects is explained field by field', async ({ page, request }) => {
    const { recommendationId } = await seedPendingRecommendation(request, 'invalid')
    await signIn(page, creds.reviewerA, '/review')
    await item(page, recommendationId).click()
    await page.route('**/api/recommendations/*/decision', (route) => route.continue({ postData: JSON.stringify({ decision: 'REJECTED' }) }))
    await decide(page, recommendationId, 'Approve', 'Confirm approval')
    const notice = page.getByTestId('error-notice')
    await expect(notice).toBeVisible()
    await expect(notice).toHaveAttribute('data-status', '422')
    await expect(notice).toHaveAttribute('data-code', 'VALIDATION_ERROR')
    await expect(notice).toContainText('comment of at least 3 characters is required to reject')
    expect((await apiGet<Rec>(request, creds.reviewerA, `/api/recommendations/${recommendationId}`)).status).toBe('PROPOSED')
  })

  test('an analyst can read the queue but has no decision controls', async ({ page, request }) => {
    const { recommendationId } = await seedPendingRecommendation(request, 'analyst readonly')
    await signIn(page, creds.analyst, '/review')
    await expect(item(page, recommendationId)).toBeVisible()
    await expect(page.getByText(/Only reviewers can approve or reject/)).toBeVisible()
    await expect(page.getByRole('button', { name: 'Approve', exact: true })).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Reject', exact: true })).toHaveCount(0)
  })
})
