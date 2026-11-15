import { useEffect, useState } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Analytics } from '@vercel/analytics/react';
import AtmosphericBackground from '../components/AtmosphericBackground';
import { useAuth } from '../hooks/useAuth';
import ThemeToggle from '../components/ThemeToggle';
import { missionService } from '../services/missionService';
import { hasMissionToExecute } from '../lib/executeHighlight';

const NAV_LINKS = [
  { to: '/home', label: 'Capture', icon: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
    </svg>
  )},
  { to: '/mission', label: 'Plan', icon: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
    </svg>
  )},
  { to: '/execute', label: 'Execute', icon: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 010 1.972l-11.54 6.347c-.75.412-1.667-.13-1.667-.986V5.653z" />
    </svg>
  )},
  { to: '/journey', label: 'Journey', icon: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 6.75V15m6-6v8.25m.503 3.498l4.875-2.437c.381-.19.622-.58.622-1.006V4.82c0-.836-.88-1.38-1.628-1.006l-3.869 1.934c-.317.159-.69.159-1.006 0L9.503 3.252a1.125 1.125 0 00-1.006 0L3.622 5.689C3.24 5.88 3 6.27 3 6.695V19.18c0 .836.88 1.38 1.628 1.006l3.869-1.934c.317-.159.69-.159 1.006 0l4.994 2.497c.317.158.69.158 1.006 0z" />
    </svg>
  )},
  { to: '/odyssey', label: 'Odyssey', icon: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.562.562 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z" />
    </svg>
  )},
];

// Routes that use the full app shell (nav + dark background)
const APP_ROUTES = ['/home', '/mission', '/execute', '/journey', '/odyssey'];

export default function RootLayout() {
  const location  = useLocation();
  const navigate  = useNavigate();
  const { user, isAuthenticated, loading: authLoading, signOut } = useAuth();
  const [missionReady, setMissionReady] = useState(false);

  // Execute only stands out once there is something to execute.
  useEffect(() => {
    let cancelled = false;
    missionService.getMissions()
      .then(missions => { if (!cancelled) setMissionReady(hasMissionToExecute(missions)); })
      .catch(() => { if (!cancelled) setMissionReady(false); });
    return () => { cancelled = true; };
  }, [location.pathname]);

  const isLanding  = location.pathname === '/';
  const isAuthPage = location.pathname === '/auth';
  const isAppRoute = APP_ROUTES.some(r => location.pathname.startsWith(r));

  // Apply dark app-mode body class for all app routes (authenticated or not)
  useEffect(() => {
    if (isAppRoute) {
      document.body.classList.add('app-mode');
    } else {
      document.body.classList.remove('app-mode');
    }
    return () => document.body.classList.remove('app-mode');
  }, [isAppRoute]);

  // Landing — manages its own layout entirely
  if (isLanding) return <><Outlet /><Analytics /></>;

  // Auth page — minimal dark container
  if (isAuthPage) {
    return (
      <div className="min-h-screen flex flex-col" style={{ backgroundColor: 'var(--color-app-bg)' }}>
        <AtmosphericBackground />
        <main className="flex-grow w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Outlet />
        </main>
        <Analytics />
      </div>
    );
  }

  const handleSignOut = async () => {
    try {
      await signOut();
      navigate('/auth');
    } catch (err) {
      console.error('Failed to sign out:', err);
    }
  };

  // Full app shell — used for all core product routes
  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ backgroundColor: 'var(--color-app-bg)', color: 'var(--color-app-text)' }}
    >
      <AtmosphericBackground />

      {/* Top navigation */}
      <header
        className="app-navigation sticky top-0 z-50 backdrop-blur-md"
        style={{
          borderBottom: '1px solid var(--color-app-border)',
        }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-14 items-center">

            {/* Brand */}
            <Link
              to="/"
              className="text-sm font-display font-bold tracking-[0.22em] transition-opacity hover:opacity-80"
              style={{ color: 'var(--color-app-mission)', letterSpacing: '0.22em' }}
            >
              ODYSSEY
            </Link>

            {/* Nav links — always visible on app routes */}
            <nav className="flex items-center gap-1">
              {NAV_LINKS.map(({ to, label, icon }) => {
                const active    = location.pathname === to;
                const isExecute = to === '/execute' && missionReady;
                return (
                  <Link
                    key={to}
                    to={to}
                    className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-all"
                    style={{
                      color: active
                        ? (isExecute ? '#fff' : 'var(--color-app-mission)')
                        : (isExecute ? 'var(--color-app-mission)' : 'var(--color-app-text-muted)'),
                      backgroundColor: active
                        ? (isExecute ? 'var(--color-app-mission)' : 'var(--color-app-mission-glow)')
                        : (isExecute ? 'var(--color-app-mission-light)' : 'transparent'),
                      border: isExecute && !active ? '1px solid color-mix(in srgb, var(--color-app-mission) 25%, transparent)' : 'none',
                    }}
                  >
                    {icon}
                    <span className="hidden sm:inline">{label}</span>
                  </Link>
                );
              })}
            </nav>

            {/* Right side: auth-aware user area */}
            <div className="flex items-center gap-2">
              <ThemeToggle />
              {/* Auth loading — show nothing to avoid flicker */}
              {authLoading ? null : isAuthenticated ? (
                <>
                  <span
                    className="text-xs hidden md:block truncate max-w-[140px]"
                    style={{ color: 'var(--color-app-text-dim)' }}
                    title={user?.email}
                  >
                    {user?.email}
                  </span>
                  <button
                    onClick={handleSignOut}
                    className="px-3 py-1.5 text-xs font-medium rounded-lg transition-all cursor-pointer border-none"
                    style={{ color: 'var(--color-app-text-muted)', backgroundColor: 'transparent' }}
                    onMouseEnter={e => {
                      (e.currentTarget as HTMLButtonElement).style.color = '#E8E2D9';
                      (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'color-mix(in srgb, var(--color-app-danger) 12%, transparent)';
                    }}
                    onMouseLeave={e => {
                      (e.currentTarget as HTMLButtonElement).style.color = 'var(--color-app-text-muted)';
                      (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'transparent';
                    }}
                  >
                    Sign out
                  </button>
                </>
              ) : (
                /* Anonymous user — soft "Sign in to save" prompt */
                <Link
                  to="/auth"
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
                  style={{
                    color: 'var(--color-app-text-dim)',
                    border: '1px solid rgba(30,60,100,0.4)',
                  }}
                  onMouseEnter={e => {
                    (e.currentTarget as HTMLAnchorElement).style.color = 'var(--color-app-text-muted)';
                    (e.currentTarget as HTMLAnchorElement).style.borderColor = 'color-mix(in srgb, var(--color-app-mission) 35%, transparent)';
                  }}
                  onMouseLeave={e => {
                    (e.currentTarget as HTMLAnchorElement).style.color = 'var(--color-app-text-dim)';
                    (e.currentTarget as HTMLAnchorElement).style.borderColor = 'rgba(30,60,100,0.4)';
                  }}
                >
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9" />
                  </svg>
                  <span className="hidden sm:inline">Sign in to save</span>
                </Link>
              )}
            </div>

          </div>
        </div>
      </header>

      <main className="flex-grow w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>
      <Analytics />
    </div>
  );
}
