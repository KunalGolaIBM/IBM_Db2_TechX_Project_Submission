import { apiGet, creds, expect, formatInt, signIn, test } from './fixtures'

interface Overview {
  complaints: {
    total: number
    synthetic: number
    real: number
    by_category: Array<{ category: string; count: number }>
    by_severity: Array<{ severity: number; count: number }>
    trend: Array<{ date: string; count: number }>
  }
  investigations: { total: number; active: number }
  recommendations: { total: number; pending_review: number; by_status: Record<string, number>; by_generator: Record<string, number> }
  hotspots: { total: number; items: Array<{ geo_cell: string; category: string; complaint_count: number }> }
  system: { database: { product: string; version: string; database: string }; llm: { configured: boolean } }
}

test.describe('intelligence overview: every figure comes from the backend', () => {
  test('the KPI tiles equal what the API reports', async ({ page }) => {
    await signIn(page, creds.analyst)
    const o = await apiGet<Overview>(page.request, creds.analyst, '/api/overview')
    expect(o.complaints.total, 'the demo database must contain complaints').toBeGreaterThan(0)
    await expect(page.getByTestId('kpi-complaints-value')).toHaveText(formatInt(o.complaints.total))
    await expect(page.getByTestId('kpi-investigations-value')).toHaveText(formatInt(o.investigations.active))
    await expect(page.getByTestId('kpi-pending-value')).toHaveText(formatInt(o.recommendations.pending_review))
    await expect(page.getByTestId('kpi-hotspots-value')).toHaveText(formatInt(o.hotspots.total))
    await expect(page.getByTestId('provenance-split')).toHaveText(`${formatInt(o.complaints.synthetic)} synthetic, ${formatInt(o.complaints.real)} real`)
  })

  test('the charts plot the API’s numbers', async ({ page }) => {
    await signIn(page, creds.analyst)
    const o = await apiGet<Overview>(page.request, creds.analyst, '/api/overview')
    for (const chart of ['chart-category', 'chart-severity', 'chart-provenance']) {
      await expect(page.getByTestId(chart)).toBeVisible()
    }
    await expect(page.getByTestId('chart-category').getByTestId('bar-row').first()).toBeVisible()
    await expect(page.getByTestId('chart-severity').getByTestId('column').first()).toBeVisible()

    const bars = await page.getByTestId('chart-category').getByTestId('bar-row').evaluateAll((rows) =>
      rows.map((r) => [r.getAttribute('data-key'), Number(r.getAttribute('data-value'))]),
    )
    expect(Object.fromEntries(bars)).toEqual(Object.fromEntries(o.complaints.by_category.map((c) => [c.category, c.count])))

    const columns = await page.getByTestId('chart-severity').getByTestId('column').evaluateAll((cols) =>
      cols.map((c) => [c.getAttribute('data-key'), Number(c.getAttribute('data-value'))]),
    )
    expect(Object.fromEntries(columns)).toEqual(Object.fromEntries(o.complaints.by_severity.map((s) => [String(s.severity), s.count])))

    if (o.recommendations.total > 0) await expect(page.getByTestId('chart-provenance').getByTestId('segment').first()).toBeVisible()
    const segments = await page.getByTestId('chart-provenance').getByTestId('segment').evaluateAll((segs) =>
      segs.map((s) => [s.getAttribute('data-key'), Number(s.getAttribute('data-value'))]),
    )
    const expected = Object.entries(o.recommendations.by_generator).filter(([, n]) => n > 0)
    expect(Object.fromEntries(segments)).toEqual(Object.fromEntries(expected))

    for (const status of ['APPROVED', 'REJECTED']) {
      await expect(page.getByTestId(`rec-status-${status}`)).toHaveText(formatInt(o.recommendations.by_status[status] ?? 0))
    }
    await expect(page.getByTestId('hotspot-row')).toHaveCount(o.hotspots.items.length)
  })

  test('the table twin of the trend chart lists the same 30 days the API returned', async ({ page }) => {
    await signIn(page, creds.analyst)
    const o = await apiGet<Overview>(page.request, creds.analyst, '/api/overview')
    const card = page.getByTestId('chart-trend')
    await card.getByRole('button', { name: 'View as table' }).click()
    const counts = await card.locator('tbody tr td:nth-child(2)').allTextContents()
    expect(counts.map(Number)).toEqual(o.complaints.trend.map((p) => p.count))
    await card.getByRole('button', { name: 'View chart' }).click()
    await expect(card.getByTestId('trend-chart')).toBeVisible()
  })

  test('synthetic data is labelled, and the Db2 server is shown from the live system', async ({ page }) => {
    await signIn(page, creds.analyst)
    const o = await apiGet<Overview>(page.request, creds.analyst, '/api/overview')
    if (o.complaints.synthetic > 0) await expect(page.getByTestId('synthetic-banner')).toContainText('SYNTHETIC')
    const db = page.getByTestId('status-db')
    await expect(db).toContainText(`${o.system.database.product} ${o.system.database.version}`)
    await expect(db).toContainText(o.system.database.database)
    await expect(page.getByTestId('connection-pill')).toHaveAttribute('data-state', 'ok')
  })

  test('with no language model configured, the page says so and does not credit AI with anything', async ({ page }) => {
    await signIn(page, creds.analyst)
    const o = await apiGet<Overview>(page.request, creds.analyst, '/api/overview')
    test.skip(o.system.llm.configured, 'a language model is configured on this server')
    await expect(page.getByTestId('status-llm')).toContainText('No language model configured')
    await expect(page.getByTestId('status-llm')).toHaveAttribute('data-tone', 'warn')
    if (o.recommendations.total > 0) await expect(page.getByTestId('no-llm-note')).toContainText(/written by a language model/)
  })

  test('hovering and keyboard focus both reveal a bar’s value in a tooltip', async ({ page }) => {
    await signIn(page, creds.analyst)
    const first = page.getByTestId('chart-category').getByTestId('bar-row').first()
    await first.hover()
    await expect(page.getByTestId('chart-tooltip')).toContainText('complaints')
    await page.mouse.move(0, 0)
    await expect(page.getByTestId('chart-tooltip')).toHaveCount(0)
    await first.focus()
    await expect(page.getByTestId('chart-tooltip')).toContainText('% of total')
  })

  test('Refresh re-reads the database and updates the timestamp', async ({ page }) => {
    await signIn(page, creds.analyst)
    const before = await page.getByTestId('updated-at').textContent()
    await page.waitForTimeout(1100) // the clock shows seconds
    const response = page.waitForResponse((r) => r.url().includes('/api/overview') && r.status() === 200)
    await page.getByRole('button', { name: 'Refresh' }).click()
    await response
    await expect(page.getByTestId('updated-at')).not.toHaveText(before ?? '')
  })
})
