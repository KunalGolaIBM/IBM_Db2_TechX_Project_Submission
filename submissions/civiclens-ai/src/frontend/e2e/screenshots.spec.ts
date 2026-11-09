import { createHash } from 'node:crypto'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { expect, test as base, type BrowserContext, type Locator, type Page } from '@playwright/test'
import { apiGet, apiPost, creds, signIn, type Creds } from './fixtures'

/**
 * Evidence screenshots. Everything in them is the REAL application: the production build, the real FastAPI backend, real IBM Db2 rows
 * (synthetic demo data, clearly labelled) and real OpenStreetMap tiles. Nothing is mocked, composited or edited.
 *
 *   - Run it against a freshly seeded demo workflow (python scripts/seed_demo_workflow.py), then reset (scripts/cleanup_test_data.py).
 *   - Read-only views are captured first; the workflow, review and error states follow (they change data, which is then reset).
 *   - Bearer tokens never appear: the sign-in field is a password input, and tokens are not rendered anywhere in the UI.
 *
 * Output: docs/screenshots/*.png and docs/screenshots/manifest.json (what each file shows, size, SHA-256, capture time).
 */
const OUT = path.resolve(process.cwd(), process.env.SCREENSHOT_DIR ?? '../../docs/screenshots')
const DB_DOWN = process.env.E2E_DB_DOWN_API
const NO_AUTH = process.env.E2E_NO_AUTH_API
const DESKTOP = { width: 1440, height: 900 }
const PHONE = { width: 390, height: 844 }

const EXPECTED_CONSOLE = [/Failed to load resource: the server responded with a status of (4|5)\d\d/, /net::ERR_[A-Z_]+/]

// Same guard as the functional tests (a CSP violation or React error fails the run) but WITHOUT stubbing the basemap.
const test = base.extend<{ page: Page }>({
  page: async ({ page }, provide) => {
    const problems: string[] = []
    page.on('console', (msg) => {
      if (msg.type() !== 'error' || EXPECTED_CONSOLE.some((re) => re.test(msg.text()))) return
      problems.push(`console.error: ${msg.text().slice(0, 300)}`)
    })
    page.on('pageerror', (error) => problems.push(`pageerror: ${String(error).slice(0, 300)}`))
    await provide(page)
    expect(problems, 'unexpected browser console errors').toEqual([])
  },
})

interface ManifestEntry {
  file: string
  caption: string
  signedInAs: string | null
  viewportCssPx: { width: number; height: number }
  deviceScaleFactor: number
  pixels: { width: number; height: number }
  bytes: number
  sha256: string
  capturedAt: string
}
const manifest: ManifestEntry[] = []

interface ShootOptions {
  caption: string
  as: Creds | null
  /** Grow the viewport to the page height (capped) so the whole page is captured with its sticky sidebar spanning it. */
  full?: boolean
  maxHeight?: number
  /** Expected state of the backend connection pill for a signed-in page (default: connected). */
  pill?: 'ok' | 'issue'
  /** The page contains the Leaflet map: wait for its tiles again after the viewport changes. */
  map?: boolean
  /** Things the caption promises. The shot fails unless each is on screen, so a screenshot cannot quietly miss its subject. */
  mustShow?: Locator[]
}

async function waitForTiles(page: Page): Promise<void> {
  await page.waitForFunction(
    () => {
      const tiles = [...document.querySelectorAll('img.leaflet-tile')] as HTMLImageElement[]
      return tiles.length > 0 && tiles.every((tile) => tile.complete && tile.naturalWidth > 0)
    },
    undefined,
    { timeout: 45_000 },
  )
}

/** Tiles loaded, then any pan/zoom finished and its new tiles loaded too. */
async function settleMap(page: Page): Promise<void> {
  await waitForTiles(page)
  await page.waitForTimeout(900)
  await waitForTiles(page)
}

async function shoot(page: Page, file: string, options: ShootOptions): Promise<void> {
  const settle = async () => {
    await page.evaluate(() => document.fonts.ready)
    await expect(page.locator('.animate-spin')).toHaveCount(0) // nothing is mid-load
    if (options.as) await expect(page.getByTestId('connection-pill')).toHaveAttribute('data-state', options.pill ?? 'ok')
  }
  await settle()
  const original = page.viewportSize()!
  if (options.full) {
    for (let pass = 0; pass < 2; pass++) {
      const height = await page.evaluate(() => document.documentElement.scrollHeight)
      await page.setViewportSize({ width: original.width, height: Math.min(Math.max(height, original.height), options.maxHeight ?? 4400) })
      await page.waitForTimeout(250)
    }
    if (options.map) await settleMap(page)
    await settle()
  }
  for (const locator of options.mustShow ?? []) await expect(locator).toBeInViewport({ ratio: 0.9 })
  const viewport = page.viewportSize()!
  const target = path.join(OUT, file)
  await page.screenshot({ path: target, animations: 'disabled', caret: 'hide' })
  if (options.full) await page.setViewportSize(original)

  const bytes = readFileSync(target)
  manifest.push({
    file,
    caption: options.caption,
    signedInAs: options.as ? `${options.as.id} (${options.as.role})` : null,
    viewportCssPx: viewport,
    deviceScaleFactor: 2,
    pixels: { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) },
    bytes: bytes.length,
    sha256: createHash('sha256').update(bytes).digest('hex'),
    capturedAt: new Date().toISOString(),
  })
}

async function retarget(page: Page, target: string): Promise<void> {
  await page.route('**/api/**', (route) => {
    const url = new URL(route.request().url())
    return route.continue({ url: `${target}${url.pathname}${url.search}` })
  })
}

interface Investigation { investigation_id: number; title: string; status: string }
interface Recommendation { recommendation_id: number; status: string; generator_type: string; summary: string; evidence_ids: number[] }
interface Complaint { complaint_id: number; category: string; is_synthetic: boolean }

const queueItem = (page: Page, id: number) => page.locator(`[data-testid=queue-item][data-recommendation-id="${id}"]`)

async function openRecommendation(page: Page, who: Creds, id: number): Promise<void> {
  await signIn(page, who, '/review')
  await queueItem(page, id).click()
  await expect(page.getByTestId('review-detail')).toHaveAttribute('data-recommendation-id', String(id))
  await expect(page.getByTestId('review-detail').getByTestId('evidence-row').first()).toBeVisible() // the evidence has loaded
}

async function decide(page: Page, id: number, button: 'Approve' | 'Reject', confirm: 'Confirm approval' | 'Confirm rejection') {
  await page.getByRole('button', { name: button, exact: true }).click()
  await expect(page.getByRole('dialog', { name: new RegExp(`${button} recommendation #${id}\\?`) })).toBeVisible()
  await page.getByRole('button', { name: confirm }).click()
}

async function demoInvestigation(page: Page, titleStart: string): Promise<Investigation> {
  const all = await apiGet<Investigation[]>(page.request, creds.analyst, '/api/investigations?limit=100')
  const found = all.find((i) => i.title.startsWith(titleStart))
  expect(found, `the demo workflow is not seeded ("${titleStart}" missing): run scripts/seed_demo_workflow.py first`).toBeTruthy()
  return found!
}

async function seededPendingRuleBased(page: Page): Promise<Recommendation> {
  const queue = await apiGet<Recommendation[]>(page.request, creds.reviewerA, '/api/recommendations?status=PROPOSED&limit=100')
  const found = queue.find((r) => r.generator_type === 'DETERMINISTIC_FALLBACK')
  expect(found, 'no pending rule-based recommendation: seed the demo workflow first').toBeTruthy()
  return found!
}

test.beforeAll(() => mkdirSync(OUT, { recursive: true }))

test.afterAll(async () => {
  const body = {
    about:
      'Real screenshots of the running CivicLens AI dashboard (production build, real FastAPI backend, real IBM Db2, real OpenStreetMap tiles). ' +
      'Complaint data is SYNTHETIC and labelled so in the UI. No file here is edited, composited or mocked. Regenerate with `npm run screenshots`.',
    viewportCssPx: { desktop: DESKTOP, phone: PHONE },
    deviceScaleFactor: 2,
    shots: manifest,
  }
  writeFileSync(path.join(OUT, 'manifest.json'), `${JSON.stringify(body, null, 2)}\n`)
})

// ---------------------------------------------------------------------------------------------------------------------
// 1. Read-only views, in the freshly seeded state
// ---------------------------------------------------------------------------------------------------------------------
test.describe('desktop: reading the data', () => {
  test('sign-in', async ({ page }) => {
    await page.goto('/login')
    await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
    await shoot(page, '01-sign-in.png', { as: null, caption: 'Sign-in: the access token goes in a password field and is kept for the browser tab only.' })
  })

  test('intelligence overview', async ({ page }) => {
    await signIn(page, creds.analyst, '/')
    await expect(page.getByTestId('overview')).toBeVisible()
    for (const chart of ['chart-category', 'chart-severity', 'chart-provenance', 'trend-chart']) await expect(page.getByTestId(chart)).toBeVisible()
    await expect(page.getByTestId('hotspot-row').first()).toBeVisible()
    await shoot(page, '02-intelligence-overview.png', {
      as: creds.analyst,
      full: true,
      caption: 'Intelligence overview: every figure is an aggregate query over IBM Db2; synthetic records are counted and labelled separately.',
    })
  })

  test('geographic intelligence', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 })
    await signIn(page, creds.analyst, '/map')
    const complaints = await apiGet<Complaint[]>(page.request, creds.analyst, '/api/complaints?limit=200')
    await expect(page.getByTestId('map')).toHaveAttribute('data-marker-count', String(complaints.length))
    await expect(page.locator('path.cl-hotspot').first()).toBeVisible()
    await settleMap(page)
    await shoot(page, '03-geographic-intelligence.png', {
      as: creds.analyst,
      full: true,
      map: true,
      mustShow: [page.getByTestId('map'), page.getByTestId('map-legend'), page.locator('.leaflet-control-attribution')],
      caption: 'Geographic intelligence: OpenStreetMap basemap, one marker per complaint (dashed ring = synthetic) and Db2-aggregated hotspot cells.',
    })

    const group = page.getByRole('group', { name: 'Filter by category' })
    await group.getByRole('button', { name: /^Water leak/ }).click()
    await expect(page.getByTestId('map-count')).toContainText(/Showing \d+ complaints and 1 hotspot(?!s)/)
    await page.getByTestId('hotspot-item').first().click()
    await expect(page.getByTestId('hotspot-item').first()).toHaveAttribute('aria-pressed', 'true')
    await expect(page.locator('path.cl-hotspot[stroke-width="3"]')).toHaveCount(1) // the selected cell is drawn heavier
    await settleMap(page)
    await shoot(page, '04-geographic-hotspot-selected.png', {
      as: creds.analyst,
      full: true,
      map: true,
      mustShow: [page.getByTestId('map'), page.locator('path.cl-hotspot[stroke-width="3"]')],
      caption: 'Category filter (water leak) applied and the hotspot selected: the map centres on the Db2 grid cell and its complaints.',
    })
  })

  test('complaints', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 })
    await signIn(page, creds.analyst, '/complaints')
    await expect(page.getByTestId('complaint-row').first()).toBeVisible()
    await shoot(page, '05-complaints.png', {
      as: creds.analyst,
      caption: 'Complaint browser: search, category and record-type filters, severity, and SYNTHETIC badges on every demo record.',
    })
    await page.getByTestId('complaint-row').first().getByRole('button').click()
    await expect(page.getByTestId('complaint-detail')).toBeVisible()
    await shoot(page, '06-complaint-detail.png', { as: creds.analyst, caption: 'A complaint record opened from the browser, with a link to its place on the map.' })
  })

  test('investigations list', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 800 })
    await signIn(page, creds.analyst, '/investigations')
    await expect(page.getByTestId('investigation-row').first()).toBeVisible()
    await shoot(page, '07-investigations.png', { as: creds.analyst, caption: 'Investigation workspace: investigations in every lifecycle state.' })
  })

  test('investigation with results and audit trail', async ({ page }) => {
    const demo = await demoInvestigation(page, 'Citywide hotspot triage')
    await signIn(page, creds.analyst, `/investigations/${demo.investigation_id}`)
    await expect(page.getByTestId('workspace')).toBeVisible()
    await expect(page.getByTestId('evidence-row').first()).toBeVisible()
    await expect(page.getByTestId('audit-entry').first()).toBeVisible()
    await expect(page.getByTestId('recommendation').first()).toBeVisible()
    await shoot(page, '08-investigation-results.png', {
      as: creds.analyst,
      full: true,
      caption:
        'An investigated case: evidence from Db2, the audited tool calls the rule-based investigator made, its recommendations (labelled "Rule-based · no LLM") and the reviewers\' decisions.',
    })
  })

  test('investigation ready to run (no language model configured)', async ({ page }) => {
    const open = await demoInvestigation(page, 'Garbage collection gaps')
    await signIn(page, creds.analyst, `/investigations/${open.investigation_id}`)
    await expect(page.getByTestId('run-card')).toBeVisible()
    await expect(page.getByText('No language model is configured on this server')).toBeVisible()
    await shoot(page, '09-investigation-run-options.png', {
      as: creds.analyst,
      full: true,
      caption: 'An open investigation: the run options say plainly that no language model is configured, so Auto mode will use the labelled rule-based fallback.',
    })
  })

  test('human review queue', async ({ page }) => {
    await signIn(page, creds.reviewerA, '/review')
    await expect(page.getByTestId('queue-item').first()).toBeVisible()
    await expect(page.getByTestId('review-detail').getByTestId('evidence-row').first()).toBeVisible()
    await expect(page.getByTestId('decision-panel')).toBeVisible()
    await shoot(page, '10-human-review-queue.png', {
      as: creds.reviewerA,
      full: true,
      caption: 'Human review as a reviewer: the proposal, who or what wrote it, the evidence behind it, and the decision controls.',
    })

    await page.getByRole('button', { name: 'Approved', exact: true }).click()
    await expect(page.getByTestId('queue-item').first()).toHaveAttribute('data-status', 'APPROVED')
    await expect(page.getByTestId('review-outcome')).toBeVisible()
    await shoot(page, '11-human-review-decided.png', {
      as: creds.reviewerA,
      caption: 'A decided recommendation: the reviewer, the time and the comment are recorded and the decision cannot be changed.',
    })
  })

  test('human review as an analyst (read-only)', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 800 })
    await signIn(page, creds.analyst, '/review')
    await expect(page.getByText(/Only reviewers can approve or reject/)).toBeVisible()
    await expect(page.getByTestId('queue-item').first()).toBeVisible()
    await shoot(page, '12-human-review-analyst-readonly.png', {
      as: creds.analyst,
      caption: 'An analyst can read the review queue but is shown no approve or reject controls (and the server would refuse them: 403).',
    })
  })

  test('agent transparency', async ({ page }) => {
    await signIn(page, creds.analyst, '/transparency')
    await expect(page.getByTestId('transparency-view')).toBeVisible()
    await expect(page.getByTestId('author-row').first()).toBeVisible()
    await expect(page.getByTestId('transparency-activity')).toBeVisible()
    await shoot(page, '13-agent-transparency.png', {
      as: creds.analyst,
      full: true,
      caption:
        'Agent transparency: no language model is configured, so every recommendation is shown as rule-based or manual; the guard rails and the audited tool activity are listed.',
    })
  })
})

// ---------------------------------------------------------------------------------------------------------------------
// 2. The same app on a phone (390 x 844 CSS px)
// ---------------------------------------------------------------------------------------------------------------------
test.describe('phone layout', () => {
  test.use({ viewport: PHONE })

  test('overview, map, review and workspace', async ({ page }) => {
    await signIn(page, creds.analyst, '/')
    await expect(page.getByTestId('overview')).toBeVisible()
    for (const chart of ['chart-category', 'chart-severity', 'chart-provenance']) await expect(page.getByTestId(chart)).toBeVisible()
    await shoot(page, '14-phone-overview.png', { as: creds.analyst, full: true, maxHeight: 4200, caption: 'Phone: the overview reflows to one column; charts stay readable and keep their data tables.' })

    await page.goto('/map')
    await expect(page.locator('path.cl-hotspot').first()).toBeVisible()
    await settleMap(page)
    await shoot(page, '15-phone-map.png', {
      as: creds.analyst,
      full: true,
      map: true,
      maxHeight: 2400,
      mustShow: [page.getByTestId('map')],
      caption: 'Phone: the filters start collapsed so the map is on the first screen; hotspot cells and complaint markers are plotted on it.',
    })

    const demo = await demoInvestigation(page, 'Citywide hotspot triage')
    await page.goto(`/investigations/${demo.investigation_id}`)
    await expect(page.getByTestId('recommendation').first()).toBeVisible()
    await shoot(page, '16-phone-investigation.png', { as: creds.analyst, full: true, maxHeight: 3800, caption: 'Phone: an investigation with evidence, recommendations and the audit trail.' })
  })

  test('review as a reviewer', async ({ page }) => {
    await signIn(page, creds.reviewerA, '/review')
    await expect(page.getByTestId('queue-item').first()).toBeVisible()
    await expect(page.getByTestId('review-detail').getByTestId('evidence-row').first()).toBeVisible()
    await shoot(page, '17-phone-review.png', { as: creds.reviewerA, full: true, maxHeight: 4400, caption: 'Phone: the review queue and a recommendation with its decision controls.' })
  })
})

// ---------------------------------------------------------------------------------------------------------------------
// 3. The workflow, driven through the UI (changes data)
// ---------------------------------------------------------------------------------------------------------------------
let workflowInvestigationId = 0
let workflowRecommendationId = 0

test.describe('desktop: the investigation workflow, then review', () => {
  test('create an investigation, attach evidence, run it', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 800 })
    await signIn(page, creds.analyst, '/investigations')
    await page.getByRole('button', { name: 'New investigation' }).click()
    const dialog = page.getByRole('dialog', { name: 'New investigation' })
    await dialog.getByLabel('Title').fill('Water leak follow-up (SYNTHETIC demo)')
    await dialog.getByLabel('Question').fill('Do the repeated water leaks in one grid cell point to a failing supply main?')
    await shoot(page, '18-new-investigation.png', { as: creds.analyst, caption: 'Creating an investigation: a title and the question it should answer.' })
    await dialog.getByRole('button', { name: 'Create investigation' }).click()
    await expect(page).toHaveURL(/\/investigations\/\d+$/)
    workflowInvestigationId = Number(page.url().split('/').pop())
    await expect(page.getByTestId('investigation-title')).toHaveText('Water leak follow-up (SYNTHETIC demo)')

    await page.getByRole('button', { name: 'Attach evidence' }).click()
    const picker = page.getByRole('dialog', { name: 'Attach evidence' })
    await picker.getByLabel('Category').selectOption('WATER_LEAK')
    const boxes = picker.getByTestId('picker-checkbox')
    await expect(boxes.first()).toBeVisible()
    for (let i = 0; i < 6; i++) await boxes.nth(i).check()
    await shoot(page, '19-attach-evidence.png', { as: creds.analyst, caption: 'Attaching evidence: complaints are picked from the database; synthetic records are badged and attached ones are marked.' })
    await picker.getByRole('button', { name: /Attach 6 selected/ }).click()
    await expect(page.getByText('Attached 6 complaints as evidence.')).toBeVisible()

    const runCard = page.getByTestId('run-card')
    await runCard.getByLabel('Category').selectOption('WATER_LEAK')
    await runCard.getByLabel('Max hotspots').selectOption('1')
    await runCard.getByRole('button', { name: 'Run investigation' }).click() // Auto mode: no LLM is configured, so the labelled fallback runs
    await expect(page.getByTestId('run-result')).toBeVisible({ timeout: 90_000 })
    await expect(page.getByTestId('recommendation').first()).toBeVisible()
    await expect(page.getByTestId('audit-entry').first()).toBeVisible()
    await shoot(page, '20-investigation-run-result.png', {
      as: creds.analyst,
      full: true,
      caption:
        'After Auto mode ran: the result says the rule-based fallback was used and why, the evidence, audited tool calls and the proposed recommendation (still awaiting a reviewer).',
    })

    const recs = await apiGet<Recommendation[]>(page.request, creds.analyst, `/api/investigations/${workflowInvestigationId}/recommendations`)
    expect(recs.length).toBeGreaterThan(0)
    expect(recs.every((r) => r.generator_type === 'DETERMINISTIC_FALLBACK' && r.status === 'PROPOSED')).toBe(true)
    workflowRecommendationId = recs[0].recommendation_id
  })

  test('a reviewer approves it: confirmation, then the recorded decision', async ({ page }) => {
    expect(workflowRecommendationId, 'the workflow test must have run first').toBeGreaterThan(0)
    await page.setViewportSize({ width: 1440, height: 1000 })
    await openRecommendation(page, creds.reviewerA, workflowRecommendationId)
    await page.getByLabel('Comment').fill('Evidence is consistent across several dates. Dispatch the water crew.')
    await page.getByRole('button', { name: 'Approve', exact: true }).click()
    await expect(page.getByRole('dialog', { name: new RegExp(`Approve recommendation #${workflowRecommendationId}\\?`) })).toBeVisible()
    await shoot(page, '21-review-confirm.png', { as: creds.reviewerA, caption: 'Approving asks for confirmation and states who the decision will be recorded as.' })
    await page.getByRole('button', { name: 'Confirm approval' }).click()
    await expect(page.getByTestId('success-notice')).toContainText(`Recommendation #${workflowRecommendationId} approved`)
    await shoot(page, '22-review-approved.png', { as: creds.reviewerA, mustShow: [page.getByTestId('success-notice')], caption: 'Success: the decision, the reviewer and the time are recorded in Db2 and in the audit log.' })
  })
})

// ---------------------------------------------------------------------------------------------------------------------
// 4. Failure states, each provoked against the real backend (changes the request on the wire; the response is the server's)
// ---------------------------------------------------------------------------------------------------------------------
test.describe('desktop: error states from the real backend', () => {
  test('409: two reviewers race for the same recommendation', async ({ page, request, browser }, testInfo) => {
    await page.setViewportSize({ width: 1440, height: 1000 })
    const all = await apiGet<Complaint[]>(request, creds.analyst, '/api/complaints?limit=200&synthetic=true')
    const ids = all.filter((c) => c.category === 'GARBAGE').slice(0, 3).map((c) => c.complaint_id)
    const inv = await apiPost<Investigation>(request, creds.analyst, '/api/investigations', {
      title: 'Overflowing bins near the market (SYNTHETIC demo)',
      question: 'Do the repeated bin overflows need a second collection on market days?',
    })
    await apiPost(request, creds.analyst, `/api/investigations/${inv.investigation_id}/evidence`, { complaint_ids: ids })
    const rec = await apiPost<Recommendation>(request, creds.analyst, `/api/investigations/${inv.investigation_id}/recommendations`, {
      summary: 'Add a second bin collection on market days',
      rationale: 'Three overflowing-bin complaints were filed near the market. Written by an analyst from the attached complaints; no automated analysis was used.',
      priority: 2,
      confidence: 0.65,
      evidence_ids: ids,
    })

    const baseURL = testInfo.project.use.baseURL as string
    const contextB: BrowserContext = await browser.newContext({ baseURL, colorScheme: 'dark', locale: 'en-GB', timezoneId: 'UTC', viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 2 })
    const pageB = await contextB.newPage()
    try {
      await openRecommendation(pageB, creds.reviewerB, rec.recommendation_id) // B opens it first and keeps that (soon stale) view
      await openRecommendation(page, creds.reviewerA, rec.recommendation_id)
      await decide(page, rec.recommendation_id, 'Approve', 'Confirm approval') // A decides it
      await expect(page.getByTestId('success-notice')).toBeVisible()

      await pageB.getByLabel('Comment').fill('Already covered by the market-day schedule.')
      await decide(pageB, rec.recommendation_id, 'Reject', 'Confirm rejection') // B acts on a stale view
      const notice = pageB.getByTestId('error-notice')
      await expect(notice).toHaveAttribute('data-status', '409')
      await expect(notice).toHaveAttribute('data-code', 'ALREADY_DECIDED')
      await shoot(pageB, '23-error-409-already-decided.png', {
        as: creds.reviewerB,
        mustShow: [notice],
        caption: '409: reviewer B acted on a stale view; Db2\'s compare-and-set refused the second decision and the first one stands.',
      })
    } finally {
      await contextB.close()
    }
  })

  test('403: a role that may not decide is refused by the server', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 })
    const pending = await seededPendingRuleBased(page)
    await openRecommendation(page, creds.reviewerA, pending.recommendation_id)
    await page.route('**/api/recommendations/*/decision', (route) =>
      route.continue({ headers: { ...route.request().headers(), authorization: `Bearer ${creds.analyst.token}` } }),
    )
    await decide(page, pending.recommendation_id, 'Approve', 'Confirm approval')
    const notice = page.getByTestId('error-notice')
    await expect(notice).toHaveAttribute('data-status', '403')
    await shoot(page, '24-error-403-forbidden.png', { as: creds.reviewerA, mustShow: [notice], caption: '403: the request carried an analyst token; the server refused it and nothing changed.' })
  })

  test('422: a decision the server rejects is explained', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 })
    const pending = await seededPendingRuleBased(page)
    await openRecommendation(page, creds.reviewerA, pending.recommendation_id)
    await page.route('**/api/recommendations/*/decision', (route) => route.continue({ postData: JSON.stringify({ decision: 'REJECTED' }) }))
    await decide(page, pending.recommendation_id, 'Approve', 'Confirm approval')
    const notice = page.getByTestId('error-notice')
    await expect(notice).toHaveAttribute('data-status', '422')
    await expect(notice).toContainText('comment of at least 3 characters is required to reject')
    await shoot(page, '25-error-422-validation.png', { as: creds.reviewerA, mustShow: [notice], caption: '422: a rejection without a comment is refused by the server, with the reason in words.' })
  })

  test('401: a rejected token returns the user to sign-in', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    const pending = await seededPendingRuleBased(page)
    await openRecommendation(page, creds.reviewerA, pending.recommendation_id)
    await page.route('**/api/recommendations/*/decision', (route) =>
      route.continue({ headers: { ...route.request().headers(), authorization: 'Bearer not-a-valid-token-0000000000' } }),
    )
    await decide(page, pending.recommendation_id, 'Approve', 'Confirm approval')
    await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
    await expect(page.getByText('Signed out')).toBeVisible()
    await shoot(page, '26-error-401-signed-out.png', { as: null, caption: '401: the server rejected the token, so the session ended and the user is asked to sign in again.' })
  })

  test('503: the API is up but IBM Db2 is not', async ({ page }) => {
    expect(DB_DOWN, 'set E2E_DB_DOWN_API to a backend started with a wrong DB2_PORT').toBeTruthy()
    await page.setViewportSize({ width: 1440, height: 800 })
    await retarget(page, DB_DOWN!)
    await signIn(page, creds.analyst)
    const notice = page.getByTestId('error-notice')
    await expect(notice).toHaveAttribute('data-code', 'DB_UNAVAILABLE')
    await expect(page.getByTestId('connection-pill')).toHaveAttribute('data-state', 'issue')
    await shoot(page, '27-error-503-database-unavailable.png', {
      as: creds.analyst,
      pill: 'issue',
      caption: '503: the API answers but the database does not. The message is generic (no host, port or credentials) and no unreliable figures are shown.',
    })
  })

  test('503: authentication is not configured, so the server fails closed', async ({ page }) => {
    expect(NO_AUTH, 'set E2E_NO_AUTH_API to a backend started without CIVICLENS_AUTH_TOKENS').toBeTruthy()
    await page.setViewportSize({ width: 1440, height: 800 })
    await retarget(page, NO_AUTH!)
    await page.goto('/login')
    await page.getByLabel('Access token').fill('demo-token-not-a-real-credential')
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page.getByTestId('error-notice')).toHaveAttribute('data-code', 'AUTH_NOT_CONFIGURED')
    await shoot(page, '28-error-503-auth-not-configured.png', {
      as: null,
      caption: '503: a backend with no access tokens configured refuses everyone instead of letting them in.',
    })
  })
})
