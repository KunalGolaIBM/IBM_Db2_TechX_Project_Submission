import { creds, expect, signIn, test } from './fixtures'

/**
 * Real 503s and network failures. Two extra FastAPI processes are started for these tests:
 *   E2E_DB_DOWN_API  a backend whose IBM Db2 port is wrong (the API is up, the database is not)
 *   E2E_NO_AUTH_API  a backend with no access tokens configured (it must fail closed)
 * The browser's /api/* calls are re-targeted to them with route.continue({ url }); the responses are the real servers'.
 */
const DB_DOWN = process.env.E2E_DB_DOWN_API
const NO_AUTH = process.env.E2E_NO_AUTH_API

async function retarget(page: import('@playwright/test').Page, target: string) {
  await page.route('**/api/**', (route) => {
    const url = new URL(route.request().url())
    return route.continue({ url: `${target}${url.pathname}${url.search}` })
  })
}

test.describe('failure states shown against real misbehaving servers', () => {
  test('503 database outage: the API answers but Db2 is unreachable; the UI explains it and recovers on Retry', async ({ page }) => {
    test.skip(!DB_DOWN, 'set E2E_DB_DOWN_API to a backend started with a wrong DB2_PORT')
    await retarget(page, DB_DOWN!)
    await signIn(page, creds.analyst) // /api/me needs no database, so sign-in works
    const notice = page.getByTestId('error-notice')
    await expect(notice).toBeVisible()
    await expect(notice).toHaveAttribute('data-status', '503')
    await expect(notice).toHaveAttribute('data-code', 'DB_UNAVAILABLE')
    await expect(notice).toContainText('Database unavailable')
    await expect(notice).not.toContainText(/localhost|db2inst1|59999|CIVICDB/i) // the body leaks nothing about the server
    await expect(page.getByTestId('connection-pill')).toHaveAttribute('data-state', 'issue')
    await expect(page.getByTestId('kpi-complaints-value')).toHaveCount(0) // no numbers are shown when they cannot be trusted

    await page.unroute('**/api/**') // the database "comes back" (traffic returns to the healthy backend)
    await notice.getByRole('button', { name: 'Retry' }).click()
    await expect(page.getByTestId('kpi-complaints-value')).toBeVisible()
    await expect(page.getByTestId('connection-pill')).toHaveAttribute('data-state', 'ok')
  })

  test('503 authentication not configured: the server fails closed and the sign-in screen says why', async ({ page }) => {
    test.skip(!NO_AUTH, 'set E2E_NO_AUTH_API to a backend started without CIVICLENS_AUTH_TOKENS')
    await retarget(page, NO_AUTH!)
    await page.goto('/login')
    await page.getByLabel('Access token').fill(creds.analyst.token)
    await page.getByRole('button', { name: 'Sign in' }).click()
    const notice = page.getByTestId('error-notice')
    await expect(notice).toBeVisible()
    await expect(notice).toHaveAttribute('data-status', '503')
    await expect(notice).toHaveAttribute('data-code', 'AUTH_NOT_CONFIGURED')
    await expect(notice).toContainText('Authentication is not configured')
    expect(await page.evaluate(() => window.sessionStorage.length)).toBe(0)
  })

  test('the API being unreachable is reported as such, keeps the session, and Retry recovers', async ({ page }) => {
    await signIn(page, creds.analyst)
    await expect(page.getByTestId('overview')).toBeVisible()
    await page.route('**/api/**', (route) => route.abort('connectionrefused'))
    await page.getByRole('button', { name: 'Refresh' }).click()
    const notice = page.getByTestId('error-notice')
    await expect(notice).toBeVisible()
    await expect(notice).toHaveAttribute('data-code', 'NETWORK_ERROR')
    await expect(notice).toContainText('Cannot reach the API')
    expect(await page.evaluate(() => window.sessionStorage.length)).toBe(1) // still signed in
    await expect(page.getByTestId('kpi-complaints-value')).toBeVisible() // the last good figures stay visible while stale

    await page.unroute('**/api/**')
    await notice.getByRole('button', { name: 'Retry' }).click()
    await expect(page.getByTestId('error-notice')).toHaveCount(0)
  })
})
