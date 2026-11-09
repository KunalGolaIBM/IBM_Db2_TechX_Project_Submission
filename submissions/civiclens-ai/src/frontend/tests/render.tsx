import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { App } from '../src/App'
import { AuthProvider } from '../src/auth/AuthContext'
import { TOKENS } from './fixtures'

export const TOKEN_KEY = 'civiclens.session-token'

export function testQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0, refetchInterval: false }, mutations: { retry: false } },
  })
}

/** Renders the whole application at `route`, optionally already signed in as a role. */
export async function renderApp(route = '/', options: { as?: keyof typeof TOKENS | null } = {}) {
  if (options.as) window.sessionStorage.setItem(TOKEN_KEY, TOKENS[options.as])
  const user = userEvent.setup()
  const client = testQueryClient()
  const utils = render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  if (options.as) await screen.findByTestId('user-chip')
  return { user, client, ...utils }
}
