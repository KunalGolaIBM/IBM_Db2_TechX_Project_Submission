import { useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { setUnauthorizedHandler } from '../api/client'
import { endpoints } from '../api/endpoints'
import { ApiError, isApiError } from '../api/errors'
import type { Me } from '../api/schemas'
import { tokenStore } from './tokenStore'

export type Session =
  | { status: 'loading' }
  | { status: 'anonymous'; expired: boolean }
  | { status: 'authenticated'; me: Me }
  | { status: 'error'; error: ApiError }

interface AuthContextValue {
  session: Session
  /** Validates the token with the server BEFORE storing it. Throws ApiError on failure. */
  login: (token: string) => Promise<void>
  logout: (reason?: 'manual' | 'expired') => void
  retry: () => void
  can: (capability: string) => boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [session, setSession] = useState<Session>(() =>
    tokenStore.get() ? { status: 'loading' } : { status: 'anonymous', expired: false },
  )
  const [attempt, setAttempt] = useState(0)

  const logout = useCallback(
    (reason: 'manual' | 'expired' = 'manual') => {
      tokenStore.clear()
      queryClient.clear()
      setSession({ status: 'anonymous', expired: reason === 'expired' })
    },
    [queryClient],
  )

  // Verify a token left over from this tab's earlier page load.
  useEffect(() => {
    if (!tokenStore.get()) return
    let cancelled = false
    endpoints
      .me()
      .then((me) => !cancelled && setSession({ status: 'authenticated', me }))
      .catch((error: unknown) => {
        if (cancelled) return
        if (isApiError(error) && error.status === 401) {
          logout('expired')
        } else if (isApiError(error)) {
          setSession({ status: 'error', error })
        }
      })
    return () => {
      cancelled = true
    }
  }, [attempt, logout])

  // Any later 401 (revoked or rotated token) returns the user to the sign-in screen.
  useEffect(() => {
    setUnauthorizedHandler(() => logout('expired'))
    return () => setUnauthorizedHandler(null)
  }, [logout])

  const login = useCallback(async (token: string) => {
    const candidate = token.trim()
    const me = await endpoints.me(candidate)
    tokenStore.set(candidate)
    setSession({ status: 'authenticated', me })
  }, [])

  const retry = useCallback(() => {
    setSession({ status: 'loading' })
    setAttempt((n) => n + 1)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      login,
      logout,
      retry,
      can: (capability) => session.status === 'authenticated' && session.me.capabilities.includes(capability),
    }),
    [session, login, logout, retry],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}

/** For components that only render when authenticated. */
export function useMe(): Me {
  const { session } = useAuth()
  if (session.status !== 'authenticated') throw new Error('useMe requires an authenticated session')
  return session.me
}
