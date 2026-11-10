import { creds, expect, signIn, test } from './fixtures'

const VIEWPORTS = [
  { name: 'phone', width: 390, height: 844 },
  { name: 'tablet', width: 820, height: 1180 },
]
/** [name, route, test id that proves the page's data (and so its tables) has rendered] */
const ROUTES: Array<[string, string, string]> = [
  ['overview', '/', 'activity-row'],
  ['map', '/map', 'map'],
  ['complaints', '/complaints', 'complaint-row'],
  ['investigations', '/investigations', 'investigation-row'],
  ['review', '/review', 'evidence-row'],
  ['transparency', '/transparency', 'author-row'],
]

/** Containers (other than the intentionally scrollable tab strip) whose content is wider than they are. */
const sidewaysScrollers = (page: import('@playwright/test').Page) =>
  page.evaluate(() =>
    [...document.querySelectorAll('*')]
      .filter(
        (el) =>
          el.scrollWidth > el.clientWidth + 1 &&
          ['auto', 'scroll'].includes(getComputedStyle(el).overflowX) &&
          !el.closest('nav'),
      )
      .map((el) => `${el.tagName.toLowerCase()}[${el.getAttribute('data-testid') ?? el.textContent?.trim().slice(0, 30)}]`),
  )

test.describe('responsive layout', () => {
  for (const vp of VIEWPORTS) {
    test(`${vp.name} (${vp.width}px): no page needs horizontal scrolling, and navigation stays reachable`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height })
      await page.goto('/login')
      expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1)
      await signIn(page, creds.analyst)
      await expect(page.getByRole('navigation', { name: 'Primary (compact)' })).toBeVisible()
      await expect(page.getByRole('navigation', { name: 'Primary', exact: true })).toBeHidden() // the sidebar is desktop-only
      for (const [name, route, ready] of ROUTES) {
        await page.getByRole('navigation', { name: 'Primary (compact)' }).locator(`a[href="${route}"]`).click()
        await expect(page.getByTestId(ready).first()).toBeVisible()
        await page.waitForLoadState('networkidle')
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
        expect(overflow, `${name} overflows horizontally by ${overflow}px`).toBeLessThanOrEqual(1)
        // tables show fewer columns instead of scrolling sideways, so nothing is hidden behind an invisible scroll
        expect(await sidewaysScrollers(page), `${name}: a container scrolls sideways`).toEqual([])
      }
    })
  }

  test('phone: the map is on the first screen, the filters start collapsed and open on demand', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await signIn(page, creds.analyst, '/map')
    await expect(page.getByTestId('map')).toHaveAttribute('data-marker-count', /\d+/)
    const box = await page.getByTestId('map').boundingBox()
    expect(box!.width).toBeGreaterThan(300)
    expect(box!.height).toBeGreaterThan(300)
    await expect(page.getByRole('button', { name: 'Zoom in' })).toBeVisible()
    await expect(page.getByTestId('map')).toBeInViewport({ ratio: 0.25 }) // not pushed below the fold by a wall of filters
    await expect(page.getByTestId('map-count')).toBeInViewport() // what is shown stays stated even while the filters are collapsed

    const group = page.getByRole('group', { name: 'Filter by category' })
    await expect(group).toBeHidden()
    const toggle = page.getByTestId('filters-toggle')
    await expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await toggle.click()
    await expect(group).toBeVisible()
    await group.getByRole('button', { name: /^Water leak/ }).click()
    await expect(toggle).toContainText('1') // one filter is active
    await toggle.click()
    await expect(group).toBeHidden()
    await expect(page.getByTestId('map-count')).toContainText('Showing') // the filter still applies while collapsed
  })

  test('desktop: the filters are always visible and there is no toggle', async ({ page }) => {
    await signIn(page, creds.analyst, '/map')
    await expect(page.getByRole('group', { name: 'Filter by category' })).toBeVisible()
    await expect(page.getByTestId('filters-toggle')).toBeHidden()
  })

  test('phone: dialogs fit the screen and can be closed', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await signIn(page, creds.analyst, '/investigations')
    await page.getByRole('button', { name: 'New investigation' }).click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    const box = await dialog.boundingBox()
    expect(box!.width).toBeLessThanOrEqual(390)
    expect(box!.y + box!.height).toBeLessThanOrEqual(844 + 1)
    await dialog.getByRole('button', { name: 'Close dialog' }).click()
    await expect(dialog).toHaveCount(0)
  })
})
