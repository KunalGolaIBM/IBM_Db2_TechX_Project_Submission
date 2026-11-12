import clsx from 'clsx';
import { Command } from 'cmdk';
import { AnimatePresence, motion } from 'motion/react';
import {
  Activity, BookOpenText, Database, GitCompareArrows, LayoutDashboard, LogOut, Radar, Search, ShieldCheck, UserCog,
} from 'lucide-react';
import { useCallback, useState, type ReactNode } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import type { Ready } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { useApi, useHotkey } from '@/lib/hooks';
import { Kbd } from './ui';

const NAV = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, role: 'viewer' as const },
  { to: '/scan', label: 'New scan', icon: Radar, role: 'operator' as const, hotkey: 'N' },
  { to: '/assessments', label: 'Assessments', icon: Activity, role: 'viewer' as const },
  { to: '/compare', label: 'Compare', icon: GitCompareArrows, role: 'viewer' as const },
  { to: '/policies', label: 'Policies', icon: BookOpenText, role: 'viewer' as const },
  { to: '/admin', label: 'Admin', icon: UserCog, role: 'admin' as const },
];

export function Logo({ className }: { className?: string }) {
  return (
    <div className={clsx('flex items-center gap-2.5', className)}>
      <div className="relative grid size-8 place-items-center rounded-lg bg-gradient-to-br from-brand-500 to-violet-500 shadow-[0_6px_24px_-6px_rgba(69,137,255,0.8)]">
        <ShieldCheck className="size-[18px] text-white" strokeWidth={2.4} />
      </div>
      <div className="leading-none">
        <div className="text-[15px] font-semibold tracking-tight">ShipSafe AI</div>
        <div className="mono mt-1 text-[10px] uppercase tracking-[0.16em] text-faint">on IBM Db2</div>
      </div>
    </div>
  );
}

function Db2Status() {
  const { data, error } = useApi<Ready>('/api/ready', 15000);
  const ok = data?.status === 'ready';
  const down = !!error || data?.status === 'degraded';
  return (
    <div
      title={down ? 'IBM Db2 is unreachable. Scans still run but results are not saved.' : `Schema ${data?.db2.schema ?? ''}`}
      className={clsx(
        'hidden items-center gap-2 rounded-full px-3 py-1.5 text-xs ring-1 md:flex',
        ok && 'bg-ok/[0.07] text-fg ring-ok/25',
        down && 'bg-sev-critical/10 text-sev-critical ring-sev-critical/30',
        !ok && !down && 'text-muted ring-line',
      )}
    >
      <span className={clsx('size-2 rounded-full pulse-dot', ok ? 'bg-ok' : down ? 'bg-sev-critical' : 'bg-faint')} />
      <Database className="size-3.5 opacity-70" />
      {ok ? (
        <span>
          Db2 <span className="mono text-muted">{data?.db2.version?.replace(/^DB2 /, '')}</span>
          <span className="mx-1.5 text-faint">·</span>
          <span className="mono text-muted">{data?.db2.latency_ms} ms</span>
        </span>
      ) : down ? (
        'Db2 unavailable'
      ) : (
        'Connecting…'
      )}
    </div>
  );
}

function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const { can } = useAuth();
  const go = (to: string) => {
    onClose();
    navigate(to);
  };
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 flex items-start justify-center bg-black/55 px-4 pt-[14vh] backdrop-blur-sm"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}>
          <motion.div initial={{ opacity: 0, y: -8, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.16 }} className="w-full max-w-xl" onClick={(e) => e.stopPropagation()}>
            <Command label="Command menu" className="glass overflow-hidden rounded-2xl bg-ink-850/90 shadow-2xl">
              <div className="flex items-center gap-3 border-b border-line px-4">
                <Search className="size-4 text-muted" />
                <Command.Input autoFocus placeholder="Jump to a page or action…" className="h-14 w-full bg-transparent text-[15px] outline-none placeholder:text-faint" />
                <Kbd>Esc</Kbd>
              </div>
              <Command.List className="scroll-thin max-h-80 overflow-y-auto p-2">
                <Command.Empty className="px-3 py-6 text-center text-sm text-muted">Nothing matches.</Command.Empty>
                <Command.Group heading="Navigate" className="px-1 text-[11px] uppercase tracking-wider text-faint [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-2">
                  {NAV.filter((n) => can(n.role)).map((n) => (
                    <Command.Item key={n.to} onSelect={() => go(n.to)} className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 text-sm normal-case tracking-normal text-muted">
                      <n.icon className="size-4" /> {n.label}
                    </Command.Item>
                  ))}
                </Command.Group>
                <Command.Group heading="Actions" className="px-1 text-[11px] uppercase tracking-wider text-faint [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-2">
                  {can('operator') && (
                    <Command.Item onSelect={() => go('/scan')} className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 text-sm normal-case tracking-normal text-muted">
                      <Radar className="size-4" /> Run a new pre-PR scan
                    </Command.Item>
                  )}
                  <Command.Item onSelect={() => go('/policies')} className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 text-sm normal-case tracking-normal text-muted">
                    <BookOpenText className="size-4" /> Ask the policy library
                  </Command.Item>
                </Command.Group>
              </Command.List>
            </Command>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const { me, can, signOut } = useAuth();
  const [palette, setPalette] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  useHotkey('k', useCallback((e: KeyboardEvent) => { e.preventDefault(); setPalette((p) => !p); }, []), { meta: true });
  useHotkey('escape', useCallback(() => setPalette(false), []));
  useHotkey('n', useCallback(() => { if (can('operator')) navigate('/scan'); }, [can, navigate]));

  return (
    <div className="relative flex min-h-full">
      <div className="pointer-events-none fixed inset-0 grid-bg opacity-60" />
      <aside className="sticky top-0 z-20 hidden h-screen w-64 shrink-0 flex-col border-r border-line bg-ink-950/95 px-4 py-5 lg:flex">
        <Logo className="px-2" />
        <nav className="mt-8 flex flex-col gap-1">
          {NAV.filter((n) => can(n.role)).map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === '/'}
              className={({ isActive }) => clsx(
                'focus-ring group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors',
                isActive ? 'text-fg' : 'text-muted hover:bg-white/[0.04] hover:text-fg',
              )}>
              {({ isActive }) => (
                <>
                  {isActive && (
                    <motion.span layoutId="nav-active" className="absolute inset-0 rounded-xl bg-white/[0.07] ring-1 ring-line-strong"
                      transition={{ type: 'spring', stiffness: 420, damping: 34 }} />
                  )}
                  <n.icon className={clsx('relative size-[18px]', isActive && 'text-brand-400')} />
                  <span className="relative flex-1">{n.label}</span>
                  {n.hotkey && <span className="relative"><Kbd>{n.hotkey}</Kbd></span>}
                </>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto">
          <div className="glass rounded-xl p-3">
            <div className="flex items-center gap-3">
              <div className="grid size-8 place-items-center rounded-full bg-gradient-to-br from-brand-600 to-violet-500 text-xs font-semibold uppercase">
                {me?.name.slice(0, 2)}
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium">{me?.name}</div>
                <div className="mono text-[11px] uppercase tracking-wider text-faint">{me?.role}</div>
              </div>
              {me?.auth_enabled && (
                <button onClick={signOut} title="Sign out" className="focus-ring rounded-lg p-1.5 text-muted hover:bg-white/[0.06] hover:text-fg">
                  <LogOut className="size-4" />
                </button>
              )}
            </div>
          </div>
        </div>
      </aside>

      <div className="relative z-10 flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-4 border-b border-line bg-ink-900/95 px-5 sm:px-8">
          <Logo className="lg:hidden" />
          <button onClick={() => setPalette(true)}
            className="focus-ring ml-auto flex h-9 w-full max-w-sm items-center gap-2 rounded-xl bg-white/[0.04] px-3 text-sm text-faint ring-1 ring-line transition hover:text-muted lg:ml-0">
            <Search className="size-4" /> <span className="flex-1 text-left">Search or jump to…</span> <Kbd>Ctrl K</Kbd>
          </button>
          <div className="ml-auto flex items-center gap-3"><Db2Status /></div>
        </header>
        <nav className="flex gap-1 overflow-x-auto border-b border-line px-4 py-2 lg:hidden">
          {NAV.filter((n) => can(n.role)).map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === '/'}
              className={({ isActive }) => clsx('flex shrink-0 items-center gap-2 rounded-lg px-3 py-1.5 text-sm', isActive ? 'bg-white/[0.08] text-fg' : 'text-muted')}>
              <n.icon className="size-4" />{n.label}
            </NavLink>
          ))}
        </nav>
        <main className="mx-auto w-full max-w-[1400px] flex-1 px-5 py-8 sm:px-8 lg:py-10">
          <AnimatePresence mode="wait">
            <motion.div key={location.pathname} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}>
              {children}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
      <CommandPalette open={palette} onClose={() => setPalette(false)} />
    </div>
  );
}
