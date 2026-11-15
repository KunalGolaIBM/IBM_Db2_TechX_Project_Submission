import React, { useState } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export default function Auth() {
  const { isAuthenticated, loading: authLoading, signUp, signInWithPassword, signInWithGoogle } = useAuth();
  const [email,        setEmail]        = useState('');
  const [password,     setPassword]     = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [authMode, setAuthMode] = useState<'signin' | 'signup'>('signin');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isGoogleSubmitting, setIsGoogleSubmitting] = useState(false);
  const [error,        setError]        = useState<string | null>(null);
  const [success,      setSuccess]      = useState<string | null>(null);

  // Detect whether the page was opened via a magic-link callback.
  // In that case the URL will contain a hash with access_token (implicit flow)
  // or a ?code= query param (PKCE flow). Show a loading spinner while the
  // supabase-js client exchanges the token and fires SIGNED_IN.
  const callbackError = typeof window !== 'undefined'
    ? new URLSearchParams(window.location.search).get('error_description') ||
      new URLSearchParams(window.location.hash.replace(/^#/, '')).get('error_description')
    : null;

  const isCallback = typeof window !== 'undefined' && !callbackError && (
    window.location.hash.includes('access_token') ||
    new URLSearchParams(window.location.search).has('code')
  );

  // Already authenticated — go straight to the app.
  if (!authLoading && isAuthenticated) {
    return <Navigate to="/home" replace />;
  }

  if (callbackError) {
    return (
      <div className="flex justify-center items-start pt-16 pb-24 px-4">
        <div className="w-full max-w-md rounded-xl p-8 text-center" style={{ backgroundColor: 'var(--color-app-surface)', border: '1px solid var(--color-app-border)' }}>
          <p className="text-sm" style={{ color: 'var(--color-status-urgent)' }}>{callbackError}</p>
          <a href="/auth" className="inline-block mt-5 text-sm underline underline-offset-2" style={{ color: 'var(--color-app-mission)' }}>
            Return to sign in
          </a>
        </div>
      </div>
    );
  }

  // Still resolving the session (initial load or mid-callback exchange).
  if (authLoading || isCallback) {
    return (
      <div className="flex justify-center items-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-4">
          <div
            className="w-10 h-10 border-2 rounded-full animate-spin"
            style={{ borderColor: 'var(--color-app-mission)', borderTopColor: 'transparent' }}
          />
          <p className="text-sm" style={{ color: 'var(--color-app-text-muted)' }}>
            {isCallback ? 'Signing you in…' : 'Loading…'}
          </p>
        </div>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password) return;
    setIsSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      if (authMode === 'signup') {
        const { session } = await signUp(email.trim(), password);
        if (!session) {
          setSuccess('Account created. Check your email to confirm your account, then sign in.');
        }
      } else {
        await signInWithPassword(email.trim(), password);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : `Unable to ${authMode === 'signup' ? 'create your account' : 'sign in'}. Please try again.`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setIsGoogleSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      await signInWithGoogle();
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to sign in with Google. Please try again.'
      );
      setIsGoogleSubmitting(false);
    }
  };

  return (
    <div className="flex justify-center items-start pt-16 pb-24 px-4">
      <div
        className="w-full max-w-md rounded-xl p-8"
        style={{
          backgroundColor: 'var(--color-app-surface)',
          border: '1px solid var(--color-app-border)',
        }}
      >
        {/* Header */}
        <div className="text-center mb-8">
          <p
            className="text-xs font-semibold tracking-[0.2em] uppercase mb-3"
            style={{ color: 'var(--color-app-mission)' }}
          >
            Authentication
          </p>
          <h1
            className="font-display text-3xl mb-2"
            style={{ color: 'var(--color-app-text)' }}
          >
            Begin Your Odyssey
          </h1>
          <p className="text-sm" style={{ color: 'var(--color-app-text-muted)' }}>
            {authMode === 'signup' ? 'Create your account with email and password.' : 'Sign in with your email and password.'}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
            {success && (
              <div className="rounded-lg p-3 text-sm" style={{ backgroundColor: 'color-mix(in srgb, var(--color-app-success) 10%, transparent)', border: '1px solid color-mix(in srgb, var(--color-app-success) 25%, transparent)', color: 'var(--color-app-success)' }}>
                {success}
              </div>
            )}
            {error && (
              <div
                className="rounded-lg p-3 text-sm"
                style={{
                  backgroundColor: 'color-mix(in srgb, var(--color-app-danger) 10%, transparent)',
                  border: '1px solid color-mix(in srgb, var(--color-app-danger) 25%, transparent)',
                  color: 'var(--color-status-urgent)',
                }}
              >
                {error}
              </div>
            )}

            <div>
              <label
                htmlFor="email"
                className="block text-xs font-semibold uppercase tracking-wider mb-2"
                style={{ color: 'var(--color-app-text-muted)' }}
              >
                Email Address
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                disabled={isSubmitting || isGoogleSubmitting}
                className="app-input w-full"
                autoComplete="email"
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="block text-xs font-semibold uppercase tracking-wider mb-2"
                style={{ color: 'var(--color-app-text-muted)' }}
              >
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  required
                  minLength={6}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  disabled={isSubmitting}
                  className="app-input w-full pr-11"
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(current => !current)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  title={showPassword ? 'Hide password' : 'Show password'}
                  className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 inline-flex items-center justify-center rounded-md cursor-pointer border-none bg-transparent"
                  style={{ color: 'var(--color-app-text-muted)' }}
                >
                  {showPassword ? (
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M3 3l18 18M10.58 10.58a2 2 0 0 0 2.83 2.83M9.88 4.24A10.76 10.76 0 0 1 12 4c5.05 0 8.4 4.5 9.5 6.2a3.36 3.36 0 0 1 0 3.6 18.4 18.4 0 0 1-2.1 2.53M6.23 6.23C4.45 7.43 3.1 9.12 2.5 10.2a3.36 3.36 0 0 0 0 3.6C3.6 15.5 6.95 20 12 20c1.61 0 3.05-.43 4.3-1.1" />
                    </svg>
                  ) : (
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M2.5 12s3.35-6 9.5-6 9.5 6 9.5 6-3.35 6-9.5 6-9.5-6-9.5-6Z" />
                      <circle cx="12" cy="12" r="2.5" />
                    </svg>
                  )}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting || isGoogleSubmitting || !email.trim() || !password}
              className="w-full py-3 px-4 text-sm font-medium rounded-lg transition-all flex items-center justify-center gap-2 cursor-pointer border-none disabled:opacity-50 disabled:pointer-events-none"
              style={{ backgroundColor: 'var(--color-app-mission)', color: '#fff' }}
            >
              {isSubmitting ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>{authMode === 'signup' ? 'Creating account…' : 'Signing in…'}</span>
                </>
              ) : (
                authMode === 'signup' ? 'Create account' : 'Sign in'
              )}
            </button>

            <div className="flex items-center gap-3" aria-hidden="true">
              <div className="h-px flex-1" style={{ backgroundColor: 'var(--color-app-border)' }} />
              <span className="text-xs" style={{ color: 'var(--color-app-text-dim)' }}>or</span>
              <div className="h-px flex-1" style={{ backgroundColor: 'var(--color-app-border)' }} />
            </div>

            <button
              type="button"
              onClick={handleGoogleSignIn}
              disabled={isSubmitting || isGoogleSubmitting}
              className="w-full py-3 px-4 text-sm font-medium rounded-lg transition-all flex items-center justify-center gap-2 cursor-pointer border disabled:opacity-50 disabled:pointer-events-none"
              style={{
                backgroundColor: 'var(--color-app-surface)',
                borderColor: 'var(--color-app-border)',
                color: 'var(--color-app-text)',
              }}
            >
              {isGoogleSubmitting ? (
                <div className="w-4 h-4 border-2 rounded-full animate-spin" style={{ borderColor: 'var(--color-app-mission)', borderTopColor: 'transparent' }} />
              ) : (
                <svg className="w-4 h-4" viewBox="0 0 24 24" aria-hidden="true">
                  <path fill="#4285F4" d="M21.35 12.23c0-.72-.06-1.42-.18-2.09H12v3.96h5.24a4.48 4.48 0 0 1-1.94 2.94v2.45h3.14c1.84-1.69 2.91-4.18 2.91-7.26Z" />
                  <path fill="#34A853" d="M12 21.67c2.63 0 4.84-.87 6.46-2.36l-3.14-2.45c-.87.58-1.98.92-3.32.92-2.55 0-4.71-1.72-5.49-4.03H3.27v2.53A9.75 9.75 0 0 0 12 21.67Z" />
                  <path fill="#FBBC05" d="M6.51 13.75A5.86 5.86 0 0 1 6.2 12c0-.61.11-1.2.31-1.75V7.72H3.27A9.76 9.76 0 0 0 2.25 12c0 1.57.38 3.06 1.02 4.28l3.24-2.53Z" />
                  <path fill="#EA4335" d="M12 6.22c1.43 0 2.71.49 3.73 1.46l2.8-2.8C16.84 3.3 14.63 2.33 12 2.33a9.75 9.75 0 0 0-8.73 5.39l3.24 2.53c.78-2.31 2.94-4.03 5.49-4.03Z" />
                </svg>
              )}
              <span>{isGoogleSubmitting ? 'Redirecting…' : 'Continue with Google'}</span>
            </button>

            <p className="text-center text-sm" style={{ color: 'var(--color-app-text-muted)' }}>
              {authMode === 'signup' ? 'Already have an account?' : 'Need an account?'}{' '}
              <button
                type="button"
                onClick={() => { setAuthMode(current => current === 'signin' ? 'signup' : 'signin'); setError(null); setSuccess(null); setPassword(''); }}
                className="font-medium underline underline-offset-2 cursor-pointer border-none bg-transparent p-0"
                style={{ color: 'var(--color-app-mission)' }}
              >
                {authMode === 'signup' ? 'Sign in' : 'Create one'}
              </button>
            </p>
          </form>
      </div>
    </div>
  );
}
