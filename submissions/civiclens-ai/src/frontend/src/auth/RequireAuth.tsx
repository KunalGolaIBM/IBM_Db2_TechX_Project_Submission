import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { ErrorNotice } from '../components/Notices'
import { Button, LoadingBlock } from '../components/ui'
import { useAuth } from './AuthContext'

/** Gate for everything except the sign-in screen. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { session, retry, logout } = useAuth()
  const location = useLocation()

  if (session.status === 'loading') {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <LoadingBlock label="Checking your session" />
      </div>
    )
  }
  if (session.status === 'error') {
    return (
      <div className="mx-auto flex min-h-dvh max-w-xl flex-col justify-center gap-4 px-4">
        <ErrorNotice error={session.error} onRetry={retry} />
        <Button onClick={() => logout('manual')}>Sign out</Button>
      </div>
    )
  }
  if (session.status === 'anonymous') {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  }
  return <>{children}</>
}
