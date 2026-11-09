import AxeBuilder from '@axe-core/playwright'
import { expect, test as base, type APIRequestContext, type Page } from '@playwright/test'

export interface Creds {
  id: string
  role: string
  token: string
}

/** Parse "id:role:token,..." from the environment. Tokens are never logged or asserted by value. */
function loadCredentials(): { analyst: Creds; reviewerA: Creds; reviewerB: Creds } {
  const all = (process.env.CIVICLENS_AUTH_TOKENS ?? '')
    .split(',')
    .map((entry) => entry.trim().split(':'))
    .filter((p) => p.length >= 3)
    .map(([id, role, ...rest]) => ({ id, role, token: rest.join(':') }))
  const analyst = all.find((c) => c.role === 'analyst')
  const reviewers = all.filter((c) => c.role === 'reviewer')
  if (!analyst || reviewers.length < 2) {
    throw new Error('CIVICLENS_AUTH_TOKENS must define one analyst and two reviewers (id:role:token).')
  }
  return { analyst, reviewerA: reviewers[0], reviewerB: reviewers[1] }
}
export const creds = loadCredentials()

// 1x1 transparent PNG, served for map tiles in functional tests (the real tile CDN is not hammered by test runs).
const TRANSPARENT_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==',
  'base64',
)
export const TILE_URL = 'https://tile.openstreetmap.org/**'

export async function stubTiles(page: Page): Promise<void> {
  await page.route(TILE_URL, (route) => route.fulfill({ status: 200, contentType: 'image/png', body: TRANSPARENT_PNG }))
}

/** Console messages that are expected noise: the browser reports every non-2xx fetch as a console error. */
const EXPECTED_CONSOLE = [/Failed to load resource: the server responded with a status of (4|5)\d\d/, /net::ERR_[A-Z_]+/]

export const test = base.extend<{ page: Page }>({
  page: async ({ page }, provide) => {
    const problems: string[] = []
    page.on('console', (msg) => {
      if (msg.type() !== 'error') return
      if (EXPECTED_CONSOLE.some((re) => re.test(msg.text()))) return
      problems.push(`console.error: ${msg.text().slice(0, 300)}`)
    })
    page.on('pageerror', (error) => problems.push(`pageerror: ${String(error).slice(0, 300)}`))
    await stubTiles(page)
    await provide(page)
    // a CSP violation, a React error or an uncaught exception anywhere in the workflow fails the test
    expect(problems, 'unexpected browser console errors').toEqual([])
  },
})
export { expect }

export async function signIn(page: Page, who: Creds, landing = '/'): Promise<void> {
  await page.goto(landing)
  await page.getByLabel('Access token').fill(who.token)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByTestId('user-chip')).toBeVisible()
  await expect(page.getByTestId('user-id')).toHaveText(who.id)
}

export const authHeader = (who: Creds) => ({ Authorization: `Bearer ${who.token}` })

/** Ask the real API directly (through the same proxy the app uses), independent of the UI under test. */
export async function apiGet<T = unknown>(request: APIRequestContext, who: Creds, path: string): Promise<T> {
  const response = await request.get(path, { headers: authHeader(who) })
  expect(response.ok(), `GET ${path} -> ${response.status()}`).toBeTruthy()
  return (await response.json()) as T
}

export async function apiPost<T = unknown>(request: APIRequestContext, who: Creds, path: string, data: unknown): Promise<T> {
  const response = await request.post(path, { headers: authHeader(who), data })
  expect(response.ok(), `POST ${path} -> ${response.status()}`).toBeTruthy()
  return (await response.json()) as T
}

export const unique = (label: string): string => `[E2E] ${label} ${Date.now().toString(36)}`

/** Build a pending recommendation entirely through the real API (setup for review tests). */
export async function seedPendingRecommendation(request: APIRequestContext, label: string) {
  const inv = await apiPost<{ investigation_id: number }>(request, creds.analyst, '/api/investigations', {
    title: unique(label),
    question: 'End-to-end review fixture',
  })
  const run = await apiPost<{ recommendation_ids: number[] }>(request, creds.analyst, `/api/investigations/${inv.investigation_id}/run`, {
    mode: 'fallback',
    days: 365,
    max_hotspots: 1,
  })
  expect(run.recommendation_ids.length).toBeGreaterThan(0)
  return { investigationId: inv.investigation_id, recommendationId: run.recommendation_ids[0] }
}

/** Serious/critical WCAG A/AA violations for the current page (via axe-core in the real browser). */
export async function seriousA11yViolations(page: Page, options: { exclude?: string[] } = {}) {
  // @axe-core/playwright ships its own (newer) playwright-core typings; it only needs basic page APIs at runtime.
  type AxePage = ConstructorParameters<typeof AxeBuilder>[0]['page']
  let builder = new AxeBuilder({ page: page as unknown as AxePage }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
  for (const selector of options.exclude ?? []) builder = builder.exclude(selector)
  const results = await builder.analyze()
  return results.violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => ({ id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.slice(0, 3).map((n) => n.target.join(' ')) }))
}

export const formatInt = (n: number): string => n.toLocaleString('en-US')
