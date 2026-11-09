import { creds, expect, seedPendingRecommendation, seriousA11yViolations, signIn, test } from './fixtures'

/** axe-core in the real browser (production build): WCAG 2.0/2.1 A + AA, failing on serious or critical findings. */
const PAGES: Array<[string, string, string]> = [
  ['overview', '/', 'overview'],
  ['geographic intelligence', '/map', 'geo-view'],
  ['complaints', '/complaints', 'complaints-view'],
  ['investigations', '/investigations', 'investigations-view'],
  ['agent transparency', '/transparency', 'transparency-view'],
]

test.describe('accessibility (axe-core, WCAG A/AA)', () => {
  test('sign-in screen', async ({ page }) => {
    await page.goto('/login')
    await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
    expect(await seriousA11yViolations(page)).toEqual([])
  })

  for (const [name, route, marker] of PAGES) {
    test(`${name}`, async ({ page }) => {
      await signIn(page, creds.analyst, route)
      await expect(page.getByTestId(marker)).toBeVisible()
      if (route === '/map') await expect(page.getByTestId('map')).toHaveAttribute('data-marker-count', /\d+/)
      await page.waitForLoadState('networkidle')
      expect(await seriousA11yViolations(page)).toEqual([])
    })
  }

  test('human review with a recommendation selected (as a reviewer)', async ({ page, request }) => {
    const { recommendationId } = await seedPendingRecommendation(request, 'a11y review')
    await signIn(page, creds.reviewerA, '/review')
    await page.locator(`[data-testid=queue-item][data-recommendation-id="${recommendationId}"]`).click()
    await expect(page.getByTestId('decision-panel')).toBeVisible()
    expect(await seriousA11yViolations(page)).toEqual([])
  })

  test('investigation workspace with evidence, recommendations and the audit timeline', async ({ page, request }) => {
    const { investigationId } = await seedPendingRecommendation(request, 'a11y workspace')
    await signIn(page, creds.analyst, `/investigations/${investigationId}`)
    await expect(page.getByTestId('audit-timeline')).toBeVisible()
    await expect(page.getByTestId('recommendation').first()).toBeVisible()
    expect(await seriousA11yViolations(page)).toEqual([])
  })

  test('dialogs: complaint detail and new investigation', async ({ page }) => {
    await signIn(page, creds.analyst, '/complaints')
    await page.getByTestId('complaint-row').first().getByRole('button').click()
    await expect(page.getByRole('dialog')).toBeVisible()
    expect(await seriousA11yViolations(page)).toEqual([])
    await page.keyboard.press('Escape')
    await page.getByRole('link', { name: 'Investigation workspace' }).click()
    await page.getByRole('button', { name: 'New investigation' }).click()
    await expect(page.getByRole('dialog', { name: 'New investigation' })).toBeVisible()
    expect(await seriousA11yViolations(page)).toEqual([])
  })

  test('the charts expose a table view that is also accessible', async ({ page }) => {
    await signIn(page, creds.analyst)
    for (const card of ['chart-category', 'chart-trend', 'chart-severity', 'chart-provenance']) {
      await page.getByTestId(card).getByRole('button', { name: 'View as table' }).click()
    }
    expect(await seriousA11yViolations(page)).toEqual([])
  })

  test('keyboard: Tab reaches the skip link first, then the navigation', async ({ page }) => {
    await signIn(page, creds.analyst)
    await page.keyboard.press('Tab')
    await expect(page.getByRole('link', { name: 'Skip to main content' })).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(page.locator('#main')).toBeFocused()
  })
})
