import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { TOKENS, analyst, overview } from '../fixtures'
import { apiError, authed, server } from '../msw'
import { renderApp, TOKEN_KEY } from '../render'

const signInWith = async (user: ReturnType<typeof import('@testing-library/user-event').default.setup>, token: string) => {
  await user.type(await screen.findByLabelText('Access token'), token)
  await user.click(screen.getByRole('button', { name: 'Sign in' }))
}

describe('authentication flow', () => {
  it('sends an anonymous visitor to the sign-in screen from any page', async () => {
    await renderApp('/review')
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.getByLabelText('Access token')).toHaveAttribute('type', 'password') // masked in the UI and in screenshots
  })

  it('verifies the token with the server, then stores it for this tab only', async () => {
    const { user } = await renderApp('/')
    await signInWith(user, TOKENS.analyst)
    expect(await screen.findByTestId('overview')).toBeInTheDocument()
    expect(screen.getByTestId('user-id')).toHaveTextContent('alice')
    expect(screen.getByTestId('user-role')).toHaveTextContent('analyst')
    expect(window.sessionStorage.getItem(TOKEN_KEY)).toBe(TOKENS.analyst)
    expect(window.localStorage.length).toBe(0)
  })

  it('rejects a wrong token (401), shows why, stores nothing and clears the field', async () => {
    const { user } = await renderApp('/')
    await signInWith(user, 'not-a-real-token')
    const notice = await screen.findByTestId('error-notice')
    expect(notice).toHaveAttribute('data-status', '401')
    expect(notice).toHaveTextContent('Sign-in required')
    expect(window.sessionStorage.getItem(TOKEN_KEY)).toBeNull()
    expect(screen.getByLabelText('Access token')).toHaveValue('')
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeDisabled()
  })

  it('tells the user when the server has no authentication configured (503, fail closed)', async () => {
    server.use(http.get('http://api.test/api/me', () => apiError(503, 'AUTH_NOT_CONFIGURED', 'Authentication is not configured.')))
    const { user } = await renderApp('/')
    await signInWith(user, 'anything')
    const notice = await screen.findByTestId('error-notice')
    expect(notice).toHaveAttribute('data-status', '503')
    expect(notice).toHaveTextContent('Authentication is not configured')
  })

  it('signs out an expired stored token and explains it', async () => {
    window.sessionStorage.setItem(TOKEN_KEY, 'revoked-token')
    await renderApp('/')
    expect(await screen.findByText('Signed out')).toBeInTheDocument()
    expect(window.sessionStorage.getItem(TOKEN_KEY)).toBeNull()
  })

  it('returns to sign-in if the token is revoked mid-session (a later request gets 401)', async () => {
    await renderApp('/', { as: 'analyst' })
    expect(await screen.findByTestId('overview')).toBeInTheDocument()
    server.use(http.get('http://api.test/api/overview', () => apiError(401, 'UNAUTHENTICATED', 'revoked')))
    screen.getByRole('button', { name: 'Refresh' }).click()
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.getByText('Signed out')).toBeInTheDocument()
    expect(window.sessionStorage.getItem(TOKEN_KEY)).toBeNull()
  })

  it('offers Retry (and keeps the session) when the API is unreachable at startup', async () => {
    window.sessionStorage.setItem(TOKEN_KEY, TOKENS.analyst)
    let up = false
    server.use(
      http.get('http://api.test/api/me', authed(() => (up ? HttpResponse.json(analyst) : HttpResponse.error()))),
    )
    // authed() would 401 an unreachable call, so swap in a handler that fails at the network level first
    server.use(http.get('http://api.test/api/me', ({ request }) => (up && request.headers.get('authorization') ? HttpResponse.json(analyst) : HttpResponse.error())))
    const { user } = await renderApp('/')
    const notice = await screen.findByTestId('error-notice')
    expect(notice).toHaveAttribute('data-code', 'NETWORK_ERROR')
    expect(window.sessionStorage.getItem(TOKEN_KEY)).toBe(TOKENS.analyst)
    up = true
    await user.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByTestId('overview')).toBeInTheDocument()
  })

  it('signing out clears the token and the cached data', async () => {
    const { user } = await renderApp('/', { as: 'analyst' })
    await screen.findByTestId('overview')
    await user.click(screen.getByRole('button', { name: 'Sign out' }))
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(window.sessionStorage.getItem(TOKEN_KEY)).toBeNull()
    expect(screen.queryByText('Signed out')).toBeNull() // a manual sign-out is not reported as an expiry
  })

  it('does not show the previous user data to the next user (cache cleared)', async () => {
    server.use(http.get('http://api.test/api/overview', authed(() => HttpResponse.json(overview()))))
    const { user } = await renderApp('/', { as: 'analyst' })
    await screen.findByTestId('overview')
    await user.click(screen.getByRole('button', { name: 'Sign out' }))
    await screen.findByRole('heading', { name: 'Sign in' })
    await waitFor(() => expect(screen.queryByTestId('overview')).toBeNull())
  })
})
