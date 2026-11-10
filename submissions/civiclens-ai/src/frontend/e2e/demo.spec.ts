import { spawnSync } from 'node:child_process'
import { copyFileSync, mkdirSync, mkdtempSync, rmSync, statSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { expect, test, type Page } from '@playwright/test'
import { apiGet, creds } from './fixtures'

/**
 * A silent, captioned screen recording of the REAL application (production build, real FastAPI, real IBM Db2, real
 * OpenStreetMap tiles). Nothing is mocked or edited; the captions are text overlays added by this script, and they only describe
 * what the app is actually doing. No language model is configured, so nothing in the recording is LLM output, and the captions say so.
 *
 * Safe by construction: the browser session is signed in OFF CAMERA (the sign-in screen is never shown, so no token is typed, pasted
 * or displayed), the token is never rendered anywhere in the UI, and a recording only contains pixels.
 *
 *   npm run demo        ->  docs/demo/civiclens-demo.mp4  (needs the demo workflow seeded first; see docs/DEMO.md)
 */
const OUT_DIR = path.resolve(process.cwd(), process.env.DEMO_DIR ?? '../../docs/demo')
const SIZE = { width: 1280, height: 720 }
const KEY = 'civiclens.session-token' // where the app keeps its (per-tab) token

const caption = async (page: Page, text: string, hold = 5500) => {
  await page.evaluate((t) => {
    let el = document.getElementById('demo-caption')
    if (!el) {
      el = document.createElement('div')
      el.id = 'demo-caption'
      Object.assign(el.style, {
        position: 'fixed', left: '50%', bottom: '26px', transform: 'translateX(-50%)', zIndex: '2147483647', width: 'max-content',
        maxWidth: '1060px', padding: '13px 22px', borderRadius: '12px', background: 'rgba(12,13,16,0.94)', color: '#f4f4f5',
        font: '600 19px/1.4 Inter, system-ui, sans-serif', border: '1px solid #cc7233', textAlign: 'center',
        boxShadow: '0 10px 34px rgba(0,0,0,.55)', pointerEvents: 'none',
      })
      document.body.appendChild(el)
    }
    el.textContent = t
    el.style.display = 'block'
  }, text)
  await page.waitForTimeout(hold)
}
/** A caption that describes a page must not stay on screen while the next page is still loading. */
const hide = (page: Page) =>
  page.evaluate(() => {
    const el = document.getElementById('demo-caption')
    if (el) el.style.display = 'none'
  })

const centre = async (locator: ReturnType<Page['locator']>, wait = 1500) => {
  await locator.evaluate((el) => el.scrollIntoView({ behavior: 'smooth', block: 'center' }))
  await locator.page().waitForTimeout(wait) // the smooth scroll must have finished before anything is captioned
}
const top = async (page: Page) => {
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }))
  await page.waitForTimeout(800)
}
const nav = async (page: Page, name: string) => {
  await hide(page)
  await page.getByRole('navigation', { name: 'Primary', exact: true }).getByRole('link', { name }).click()
}
const settleMap = async (page: Page) => {
  await page.waitForFunction(
    () => {
      const tiles = [...document.querySelectorAll('img.leaflet-tile')] as HTMLImageElement[]
      return tiles.length > 0 && tiles.every((tile) => tile.complete && tile.naturalWidth > 0)
    },
    undefined,
    { timeout: 45_000 },
  )
  await page.waitForTimeout(900)
}

test('CivicLens AI: the demo walkthrough', async ({ browser }, testInfo) => {
  test.setTimeout(900_000)
  mkdirSync(OUT_DIR, { recursive: true })
  const work = mkdtempSync(path.join(tmpdir(), 'civiclens-demo-'))
  const baseURL = testInfo.project.use.baseURL as string
  const context = await browser.newContext({
    baseURL, colorScheme: 'dark', locale: 'en-GB', timezoneId: 'UTC', viewport: SIZE, deviceScaleFactor: 1,
    recordVideo: { dir: work, size: SIZE },
  })
  // Sign-in happens off camera: before any page script runs, the session for the chosen role is placed in this tab's sessionStorage.
  // The token lives only in this Node process and in the tab; it is never typed, shown or logged.
  await context.addInitScript(
    ({ key, tokens }) => {
      const role = window.localStorage.getItem('demo-role')
      if (role && tokens[role] && !window.sessionStorage.getItem(key)) window.sessionStorage.setItem(key, tokens[role])
    },
    { key: KEY, tokens: { analyst: creds.analyst.token, reviewer: creds.reviewerA.token } as Record<string, string> },
  )
  const setup = await context.newPage() // a throwaway page, not part of the saved recording
  await setup.goto('/favicon.svg')
  await setup.evaluate(() => window.localStorage.setItem('demo-role', 'analyst'))
  await setup.close()

  const page = await context.newPage()
  const demoState = { investigationId: 0, recommendationId: 0 }
  try {
    // ---- 1. the problem -----------------------------------------------------------------------------------------------------------------
    await page.goto('/')
    await expect(page.getByTestId('user-id')).toHaveText(creds.analyst.id)
    await expect(page.getByTestId('overview')).toBeVisible()
    for (const chart of ['chart-category', 'chart-severity', 'chart-provenance']) await expect(page.getByTestId(chart)).toBeVisible()
    await expect(page.getByTestId('connection-pill')).toHaveAttribute('data-state', 'ok')
    await caption(page, 'The problem: a city receives thousands of infrastructure complaints. Many are duplicates, and clusters stay hidden when you read ticket by ticket.', 7500)
    await centre(page.getByTestId('chart-category'))
    await caption(page, 'CivicLens AI keeps every complaint in IBM Db2. Every number here is a Db2 aggregate computed when the page loaded. All data is synthetic.', 6500)

    // ---- 2. the Db2 architecture ---------------------------------------------------------------------------------------------------------
    await centre(page.getByTestId('operational-status'))
    await caption(page, 'Architecture: this browser dashboard talks only to a FastAPI service. The service talks to IBM Db2 12.1 through ibm_db with parameterized SQL. The browser never touches the database.', 8000)
    await caption(page, 'Everything the investigator does is a fixed, audited Db2 query. A language model, if one were configured, could never write SQL.', 6500)

    // ---- 3. geographic hotspot detection ---------------------------------------------------------------------------------------------------
    await nav(page, 'Geographic intelligence')
    await expect(page.getByTestId('map')).toHaveAttribute('data-marker-count', /\d+/)
    await expect(page.locator('path.cl-hotspot').first()).toBeVisible()
    await settleMap(page)
    await caption(page, 'Geographic intelligence: one marker per complaint (dashed ring = synthetic). The rectangles are the grid cells Db2 counted with GROUP BY cell and category.', 7500)
    await hide(page)
    await page.getByRole('group', { name: 'Filter by category' }).getByRole('button', { name: /^Water leak/ }).click()
    await page.getByTestId('hotspot-item').first().click()
    await settleMap(page)
    await caption(page, 'A hotspot is 3 or more complaints of one category in one cell within 30 days. Select it and the map centres on exactly the cell Db2 found.', 7500)

    // ---- 4. investigation and evidence retrieval ---------------------------------------------------------------------------------------------
    await nav(page, 'Investigation workspace')
    await expect(page.getByTestId('investigation-row').first()).toBeVisible()
    await caption(page, 'Investigation workspace: each investigation is a question, the evidence gathered from Db2, and an audit trail.', 5500)
    await hide(page)
    await page.getByTestId('investigation-row').filter({ hasText: 'Citywide hotspot triage' }).getByRole('link').click()
    await expect(page.getByTestId('workspace')).toBeVisible()
    await expect(page.getByTestId('evidence-row').first()).toBeVisible()
    await centre(page.getByTestId('audit-card'), 1800)
    await caption(page, 'Every tool call the investigator made is audited: which tool, which arguments, how many rows. Here they were issued by the rule-based investigator, not by a language model, and the page says so.', 8500)

    // a new investigation, live
    await nav(page, 'Investigation workspace')
    await page.getByRole('button', { name: 'New investigation' }).click()
    const dialog = page.getByRole('dialog', { name: 'New investigation' })
    await dialog.getByLabel('Title').pressSequentially('Water leak follow-up (SYNTHETIC demo)', { delay: 28 })
    await dialog.getByLabel('Question').pressSequentially('Do the repeated water leaks in one grid cell point to a failing supply main?', { delay: 18 })
    await caption(page, 'Now a new investigation, live: a title and the question it should answer.', 3500)
    await dialog.getByRole('button', { name: 'Create investigation' }).click()
    await expect(page).toHaveURL(/\/investigations\/\d+$/)
    demoState.investigationId = Number(page.url().split('/').pop())

    await page.getByRole('button', { name: 'Attach evidence' }).click()
    const picker = page.getByRole('dialog', { name: 'Attach evidence' })
    await picker.getByLabel('Category').selectOption('WATER_LEAK')
    const boxes = picker.getByTestId('picker-checkbox')
    await expect(boxes.first()).toBeVisible()
    await caption(page, 'Evidence retrieval: the analyst picks real complaints from Db2. A recommendation may only cite evidence attached to the investigation.', 4500)
    for (let i = 0; i < 6; i++) {
      await boxes.nth(i).check()
      await page.waitForTimeout(250)
    }
    await picker.getByRole('button', { name: /Attach 6 selected/ }).click()
    await expect(page.getByText('Attached 6 complaints as evidence.')).toBeVisible()

    const runCard = page.getByTestId('run-card')
    await centre(runCard, 1100)
    await expect(page.getByText('No language model is configured on this server')).toBeVisible()
    await caption(page, 'Run options: Auto, LLM only, or Rule-based only. No language model is configured on this server, so Auto will use the labelled rule-based fallback.', 7500)
    await runCard.getByLabel('Category').selectOption('WATER_LEAK')
    await runCard.getByLabel('Max hotspots').selectOption('1')
    await runCard.getByRole('button', { name: 'Run investigation' }).click()
    await expect(page.getByTestId('run-result')).toBeVisible({ timeout: 90_000 })
    await expect(page.getByTestId('recommendations-card').getByTestId('recommendation').first()).toBeVisible()
    await expect(page.getByTestId('audit-card').getByTestId('audit-entry').last()).toBeVisible()
    await page.waitForTimeout(1200) // let the evidence, audit trail and recommendations finish refreshing
    await centre(page.getByTestId('run-result'))
    await caption(page, 'The result says it plainly: rule-based, "NO LLM WAS USED", and why the fallback ran. Nothing is passed off as AI.', 7500)

    // ---- 5. recommendation generation and provenance -----------------------------------------------------------------------------------------
    const rec = page.getByTestId('recommendations-card').getByTestId('recommendation').first()
    await expect(rec).toBeVisible()
    await centre(rec, 1100)
    await caption(page, 'Recommendation and provenance: it names its author ("Rule-based · no LLM"), cites its evidence, starts as "Awaiting review", and its score is a data-volume heuristic, not a model probability.', 9000)
    const stored = await apiGet<Array<{ recommendation_id: number }>>(page.request, creds.analyst, `/api/investigations/${demoState.investigationId}/recommendations`)
    expect(stored.length).toBeGreaterThan(0)
    demoState.recommendationId = stored[0].recommendation_id

    // ---- 6. human review and audit history ---------------------------------------------------------------------------------------------------
    await caption(page, 'Human review: the system can only propose. A different person, signed in as a reviewer, decides.', 4500)
    await page.evaluate((key) => {
      window.localStorage.setItem('demo-role', 'reviewer')
      window.sessionStorage.removeItem(key)
    }, KEY)
    await hide(page)
    await page.goto('/review')
    await expect(page.getByTestId('user-id')).toHaveText(creds.reviewerA.id)
    await page.locator(`[data-testid=queue-item][data-recommendation-id="${demoState.recommendationId}"]`).click()
    await expect(page.getByTestId('review-detail')).toHaveAttribute('data-recommendation-id', String(demoState.recommendationId))
    await expect(page.getByTestId('review-detail').getByTestId('evidence-row').first()).toBeVisible()
    await caption(page, 'The reviewer reads the explanation, who wrote it, and the evidence behind it.', 5500)
    await centre(page.getByTestId('decision-panel'), 1100)
    await page.getByLabel('Comment').pressSequentially('Evidence is consistent across several dates. Dispatch the water crew.', { delay: 14 })
    await page.getByRole('button', { name: 'Approve', exact: true }).click()
    await expect(page.getByRole('dialog', { name: new RegExp(`Approve recommendation #${demoState.recommendationId}\\?`) })).toBeVisible()
    await caption(page, 'Approving asks for confirmation and states who the decision will be recorded as. It cannot be changed afterwards.', 6000)
    await page.getByRole('button', { name: 'Confirm approval' }).click()
    await expect(page.getByTestId('success-notice')).toContainText(`Recommendation #${demoState.recommendationId} approved`)
    await caption(page, 'Recorded in Db2 in one transaction: the decision, the reviewer, the time and an audit entry.', 6000)

    await hide(page)
    await page.goto(`/investigations/${demoState.investigationId}`)
    await expect(page.getByTestId('audit-entry').first()).toBeVisible()
    await page.waitForTimeout(800)
    await centre(page.getByTestId('audit-timeline').getByTestId('audit-entry').last(), 1100)
    await caption(page, 'Audit history: who did what and when, from "Investigation created" to "Review: approved by rita". It is append-only in Db2.', 8000)

    // ---- 7. real LLM output versus deterministic fallback ------------------------------------------------------------------------------------------
    await nav(page, 'Agent transparency')
    await expect(page.getByTestId('transparency-view')).toBeVisible()
    await expect(page.getByTestId('author-row').first()).toBeVisible()
    await top(page)
    await caption(page, 'Real LLM output versus deterministic fallback: this page counts every recommendation by its actual stored author.', 5500)
    await centre(page.getByTestId('llm-status'), 900)
    await caption(page, 'No language model is configured on this server, so none of the recommendations was written by one. Real-LLM verification is BLOCKED: no provider credentials exist.', 8500)
    await centre(page.getByTestId('generator-card-LLM'), 900)
    await caption(page, 'If a real model had run, its output would appear here as "AI model (LLM)" with its provider and model. Rule-based and analyst-written output can never be shown as AI.', 8500)
    await centre(page.getByTestId('latest-recommendations'), 900)
    await caption(page, 'Each recommendation keeps its true author and status. Guard rails: allow-listed read-only tools, no model-written SQL, evidence must be grounded, proposals only.', 7500)
    await top(page)
    await caption(page, 'CivicLens AI · IBM Db2 TechX Summit 2026 · all complaint data is synthetic · nothing in this recording was produced by an LLM', 6000)
  } finally {
    const video = page.video()
    await context.close() // finalises the recording
    if (video) {
      const webm = path.join(work, 'demo.webm')
      await video.saveAs(webm)
      const mp4 = path.join(OUT_DIR, 'civiclens-demo.mp4')
      const encode = spawnSync(
        'ffmpeg',
        ['-y', '-loglevel', 'error', '-i', webm, '-c:v', 'libx264', '-preset', 'slow', '-crf', '30', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-an', mp4],
        { encoding: 'utf8' },
      )
      if (encode.status === 0) {
        console.log(`demo recording: ${mp4} (${(statSync(mp4).size / 1048576).toFixed(1)} MB)`)
      } else {
        copyFileSync(webm, path.join(OUT_DIR, 'civiclens-demo.webm')) // no ffmpeg: keep the browser's own format
        console.log('ffmpeg not available: kept the .webm recording')
      }
    }
    rmSync(work, { recursive: true, force: true })
  }
})
