import { creds, expect, signIn, test } from './fixtures'

test.describe('authentication against the real backend', () => {
  test('a wrong token gets a real 401, is explained, and nothing is stored', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveURL(/\/login$/)
    await page.getByLabel('Access token').fill('not-a-valid-token-0123456789')
    await page.getByRole('button', { name: 'Sign in' }).click()
    const notice = page.getByTestId('error-notice')
    await expect(notice).toBeVisible()
    await expect(notice).toHaveAttribute('data-status', '401')
    await expect(notice).toContainText('Sign-in required')
    await expect(page).toHaveURL(/\/login$/)
    expect(await page.evaluate(() => window.sessionStorage.length)).toBe(0)
    await expect(page.getByLabel('Access token')).toHaveValue('') // the rejected value is cleared
  })

  test('the token field is masked', async ({ page }) => {
    await page.goto('/login')
    await expect(page.getByLabel('Access token')).toHaveAttribute('type', 'password')
    await expect(page.getByLabel('Access token')).toHaveAttribute('autocomplete', 'off')
  })

  test('the token lives only in this tab’s sessionStorage: not in the URL, DOM, localStorage or cookies', async ({ page }) => {
    await signIn(page, creds.analyst)
    const state = await page.evaluate((token) => ({
      session: Object.keys(window.sessionStorage),
      localCount: window.localStorage.length,
      cookie: document.cookie,
      inUrl: window.location.href.includes(token),
      inDom: document.documentElement.outerHTML.includes(token),
      inInputs: Array.from(document.querySelectorAll('input,textarea')).some((el) => (el as HTMLInputElement).value.includes(token)),
    }), creds.analyst.token)
    expect(state.session).toEqual(['civiclens.session-token'])
    expect(state.localCount).toBe(0)
    expect(state.cookie).toBe('')
    expect([state.inUrl, state.inDom, state.inInputs]).toEqual([false, false, false])
    await expect(page.getByTestId('user-role')).toHaveText('analyst')
  })

  test('the token is only ever sent to the API, as a bearer header', async ({ page }) => {
    const seen: Array<{ url: string; auth: boolean; hasToken: boolean }> = []
    page.on('request', (request) => {
      const header = request.headers().authorization ?? ''
      seen.push({ url: request.url(), auth: header.startsWith('Bearer '), hasToken: request.url().includes(creds.analyst.token) })
    })
    await signIn(page, creds.analyst)
    await page.getByRole('link', { name: 'Complaints', exact: true }).click()
    await expect(page.getByTestId('complaints-view')).toBeVisible()
    expect(seen.filter((r) => r.hasToken)).toEqual([]) // never in a URL
    const withAuth = seen.filter((r) => r.auth)
    expect(withAuth.length).toBeGreaterThan(0)
    expect(withAuth.every((r) => new URL(r.url).pathname.startsWith('/api/'))).toBe(true) // never to any other path or host
    expect(seen.filter((r) => /tile\.openstreetmap\.org/.test(r.url) && r.auth)).toEqual([])
  })

  test('a protected deep link redirects to sign-in and returns to the page afterwards', async ({ page }) => {
    await signIn(page, creds.reviewerA, '/review')
    await expect(page).toHaveURL(/\/review$/)
    await expect(page.getByTestId('review-view')).toBeVisible()
  })

  test('signing out clears the session, and protected pages ask for sign-in again', async ({ page }) => {
    await signIn(page, creds.analyst)
    await page.getByRole('button', { name: 'Sign out' }).click()
    await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
    expect(await page.evaluate(() => window.sessionStorage.length)).toBe(0)
    await page.goto('/investigations')
    await expect(page).toHaveURL(/\/login$/)
  })

  test('a token that stops working returns the user to sign-in with an explanation', async ({ page }) => {
    await signIn(page, creds.analyst)
    await expect(page.getByTestId('overview')).toBeVisible()
    await page.evaluate(() => window.sessionStorage.setItem('civiclens.session-token', 'revoked-token-0000000000000000'))
    await page.getByRole('button', { name: 'Refresh' }).click() // the real API answers 401
    await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
    await expect(page.getByText('Signed out')).toBeVisible()
    expect(await page.evaluate(() => window.sessionStorage.length)).toBe(0)
  })

  test('each role sees only the controls it may use', async ({ page }) => {
    await signIn(page, creds.analyst, '/investigations')
    await expect(page.getByRole('button', { name: 'New investigation' })).toBeVisible()
    await page.getByRole('link', { name: 'Complaints', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Report a complaint' })).toBeVisible()
    await page.getByRole('button', { name: 'Sign out' }).click()

    await signIn(page, creds.reviewerA, '/investigations')
    await expect(page.getByText('Read-only for your role')).toBeVisible()
    await expect(page.getByRole('button', { name: 'New investigation' })).toHaveCount(0)
    await page.getByRole('link', { name: 'Complaints', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Report a complaint' })).toHaveCount(0)
  })
})
