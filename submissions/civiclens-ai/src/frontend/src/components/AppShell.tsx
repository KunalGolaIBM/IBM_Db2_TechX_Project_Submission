import {
  Eye,
  FolderSearch,
  Inbox,
  LayoutDashboard,
  LogOut,
  Map as MapIcon,
  ShieldCheck,
  type LucideIcon,
} from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
import { useOverview } from '../api/queries'
import { useAuth, useMe } from '../auth/AuthContext'
import { cn } from '../lib/cn'
import { Wordmark } from './Brand'
import { Button, Chip } from './ui'

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  end?: boolean
}
const NAV: NavItem[] = [
  { to: '/', label: 'Intelligence overview', icon: LayoutDashboard, end: true },
  { to: '/map', label: 'Geographic intelligence', icon: MapIcon },
  { to: '/complaints', label: 'Complaints', icon: Inbox },
  { to: '/investigations', label: 'Investigation workspace', icon: FolderSearch },
  { to: '/review', label: 'Human review', icon: ShieldCheck },
  { to: '/transparency', label: 'Agent transparency', icon: Eye },
]

function NavList({ pending, horizontal = false }: { pending: number; horizontal?: boolean }) {
  return (
    <ul className={cn(horizontal ? 'flex gap-1 px-3 py-2' : 'flex flex-col gap-0.5 px-3')}>
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <li key={to} className={horizontal ? 'shrink-0' : undefined}>
          <NavLink
            to={to}
            end={end}
            className={({ isActive }) =>
              cn(
                'group flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm whitespace-nowrap transition-colors',
                isActive ? 'bg-copper-500/16 font-medium text-fg' : 'text-fg-2 hover:bg-ink-800 hover:text-fg',
              )
            }
          >
            {({ isActive }) => (
              <>
                <Icon className={cn('size-[18px]', isActive ? 'text-copper-400' : 'text-fg-3 group-hover:text-fg-2')} aria-hidden />
                {label}
                {to === '/review' && pending > 0 && (
                  <span
                    data-testid={horizontal ? 'nav-pending-count-compact' : 'nav-pending-count'}
                    className="ml-auto rounded-full bg-copper-400 px-1.5 text-[11px] leading-5 font-semibold text-ink-950 tabular-nums"
                    aria-label={`${pending} awaiting review`}
                  >
                    {pending}
                  </span>
                )}
              </>
            )}
          </NavLink>
        </li>
      ))}
    </ul>
  )
}

/** Live backend/Db2 status, derived from the overview request (no separate probe). */
function ConnectionPill() {
  const q = useOverview()
  if (q.isPending) {
    return (
      <Chip data-testid="connection-pill" data-state="checking">
        Checking<span className="hidden sm:inline"> backend</span>…
      </Chip>
    )
  }
  if (q.isError && !q.data) {
    return (
      <Chip tone="warn" data-testid="connection-pill" data-state="issue">
        <span className="hidden sm:inline">Backend issue</span>
        <span className="sm:hidden">Issue</span>
      </Chip>
    )
  }
  const db = q.data?.system.database
  return (
    <Chip tone="good" title={db ? `${db.product} ${db.version}` : undefined} data-testid="connection-pill" data-state="ok">
      <span className="size-1.5 rounded-full bg-good" aria-hidden />
      <span className="hidden sm:inline">Db2 connected</span>
      <span className="sm:hidden">Db2</span>
    </Chip>
  )
}

export function AppShell() {
  const me = useMe()
  const { logout } = useAuth()
  const overview = useOverview()
  const pending = overview.data?.recommendations.pending_review ?? 0

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[264px_minmax(0,1fr)]">
      <a
        href="#main"
        className="sr-only z-50 rounded-md bg-copper-400 px-3 py-2 text-sm font-semibold text-ink-950 focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to main content
      </a>

      <aside className="sticky top-0 hidden h-dvh flex-col border-r border-ink-700 bg-ink-900 lg:flex">
        <div className="px-6 py-5">
          <Wordmark />
        </div>
        <nav aria-label="Primary" className="flex-1 overflow-y-auto">
          <NavList pending={pending} />
        </nav>
        <p className="mx-6 mb-3 text-xs leading-5 text-fg-3">
          Records marked <span className="font-semibold text-fg-2">SYNTHETIC</span> are fictional demonstration data.
        </p>
      </aside>

      <div className="flex min-w-0 flex-col">
        <header className="sticky top-0 z-30 flex items-center gap-2 border-b border-ink-700 bg-ink-900/92 px-4 py-2.5 backdrop-blur sm:gap-3 lg:px-8">
          <div className="min-w-0 lg:hidden">
            <Wordmark />
          </div>
          <div className="ml-auto flex shrink-0 items-center gap-2 sm:gap-3">
            <ConnectionPill />
            <div className="flex items-center gap-2" data-testid="user-chip" title={`Signed in as ${me.user_id} (${me.role})`}>
              <span
                className="flex size-8 items-center justify-center rounded-full bg-ink-750 text-xs font-semibold text-fg uppercase"
                aria-hidden
              >
                {me.user_id.slice(0, 2)}
              </span>
              {/* on a phone the name is visually hidden (space) but stays available to screen readers */}
              <div className="sr-only leading-tight sm:not-sr-only">
                <div className="text-[13px] font-medium text-fg" data-testid="user-id">
                  {me.user_id}
                </div>
                <div className="text-xs text-fg-3" data-testid="user-role">
                  {me.role}
                </div>
              </div>
            </div>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => logout('manual')}
              icon={<LogOut className="size-4" aria-hidden />}
              className="px-2 sm:px-3"
            >
              <span className="sr-only sm:not-sr-only">Sign out</span>
            </Button>
          </div>
        </header>
        <nav aria-label="Primary (compact)" className="overflow-x-auto border-b border-ink-700 bg-ink-900 lg:hidden">
          <NavList pending={pending} horizontal />
        </nav>
        <main id="main" tabIndex={-1} className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-6 outline-none lg:px-8 lg:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
