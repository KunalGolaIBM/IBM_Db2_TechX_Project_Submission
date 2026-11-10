import { KeyRound, ShieldCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { BrandMark } from '../components/Brand'
import { ErrorNotice, InfoNotice } from '../components/Notices'
import { Button, Card, TextInput } from '../components/ui'

export function LoginView() {
  const { session, login } = useAuth()
  const location = useLocation()
  const [token, setToken] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  if (session.status === 'authenticated') {
    const from = (location.state as { from?: string } | null)?.from
    return <Navigate to={from && from !== '/login' ? from : '/'} replace />
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (!token.trim()) return
    setBusy(true)
    setError(null)
    try {
      await login(token)
    } catch (e) {
      setError(e)
      setToken('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="flex min-h-dvh items-center justify-center bg-ink-950 px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <BrandMark className="size-14" />
          <h1 className="text-2xl font-semibold tracking-tight text-fg">
            CivicLens <span className="text-copper-400">AI</span>
          </h1>
          <p className="text-sm text-fg-2">Urban infrastructure intelligence, backed by IBM Db2.</p>
        </div>

        <Card className="p-6">
          <h2 className="text-lg font-semibold text-fg">Sign in</h2>
          <p className="mt-1 text-sm leading-6 text-fg-2">
            Enter the access token issued to you by the operator. The server verifies it; it is kept only in this browser
            tab and is sent only to the CivicLens API.
          </p>

          {session.status === 'anonymous' && session.expired && (
            <InfoNotice className="mt-4" title="Signed out">
              Your session ended because the server no longer accepts this token. Sign in again.
            </InfoNotice>
          )}
          {session.status === 'error' && <ErrorNotice className="mt-4" error={session.error} />}

          <form onSubmit={onSubmit} className="mt-5 flex flex-col gap-4" noValidate>
            <TextInput
              label="Access token"
              type="password"
              name="access-token"
              autoComplete="off"
              autoCapitalize="off"
              spellCheck={false}
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="Paste your token"
              required
              data-autofocus
            />
            {error !== null && <ErrorNotice error={error} />}
            <Button type="submit" variant="primary" size="lg" loading={busy} disabled={!token.trim()} icon={<KeyRound className="size-4" aria-hidden />}>
              Sign in
            </Button>
          </form>
        </Card>

        <div className="mt-6 grid grid-cols-1 gap-3 text-[13px] leading-5 text-fg-2 sm:grid-cols-2">
          <p>
            <ShieldCheck className="mr-1.5 inline size-4 text-copper-400" aria-hidden />
            <strong className="font-semibold text-fg">Analysts</strong> create investigations, attach evidence and run the
            investigator.
          </p>
          <p>
            <ShieldCheck className="mr-1.5 inline size-4 text-copper-400" aria-hidden />
            <strong className="font-semibold text-fg">Reviewers</strong> approve or reject recommendations. Nobody reviews their
            own investigation.
          </p>
        </div>
      </div>
    </main>
  )
}
