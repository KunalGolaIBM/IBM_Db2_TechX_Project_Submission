import { NavLink } from 'react-router-dom';
import { Database, Radio, X, Zap } from 'lucide-react';
import { ROUTES } from '../../lib/routes';
import { useDashboard } from '../../state/DashboardContext';
import { API_BASE_URL } from '../../services/api';
import { Chip, StatusDot } from '../ui/bits';

function BrandMark() {
  return (
    <span className="relative flex h-10 w-10 items-center justify-center rounded-xl border border-accent/30 bg-gradient-to-br from-accent/20 to-accent/5 shadow-glow">
      <svg viewBox="0 0 32 32" className="h-6 w-6" aria-hidden="true">
        <path
          d="M18.5 3.5 L7.5 18.2 h5.6 L11 28.5 L24.5 13.2 h-6.2 z"
          fill="#22D3EE"
        />
      </svg>
    </span>
  );
}

function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
      <p className="label-cap px-3 pb-2">Command</p>
      {ROUTES.map((route) => {
        const Icon = route.icon;
        return (
          <NavLink
            key={route.path}
            to={route.path}
            end={route.path === '/'}
            onClick={onNavigate}
            className={({ isActive }) =>
              `group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-all duration-200 ${
                isActive
                  ? 'bg-accent/[0.08] text-accent'
                  : 'text-slate-400 hover:bg-white/[0.04] hover:text-slate-200'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <span
                  className={`absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r-full transition-all duration-200 ${
                    isActive ? 'bg-accent shadow-glow' : 'bg-transparent'
                  }`}
                />
                <Icon
                  className={`h-4 w-4 shrink-0 transition-colors ${
                    isActive ? 'text-accent' : 'text-slate-500 group-hover:text-slate-300'
                  }`}
                />
                <span className="truncate font-medium">{route.label}</span>
              </>
            )}
          </NavLink>
        );
      })}
    </nav>
  );
}

function SidebarFooter() {
  const { db2, statusState } = useDashboard();
  const connected = db2?.connected === true;
  const unknown = statusState !== 'success';

  return (
    <div className="space-y-3 border-t border-white/[0.06] px-4 py-4">
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-2 text-[11px] font-medium text-slate-500">
          <Database className="h-3.5 w-3.5" />
          IBM Db2
        </span>
        <Chip
          className={
            unknown
              ? 'border-slate-500/40 bg-slate-500/10 text-slate-400'
              : connected
                ? 'border-emerald-400/35 bg-emerald-400/10 text-emerald-300'
                : 'border-red-500/40 bg-red-500/10 text-red-300'
          }
          dot={
            unknown
              ? 'bg-slate-500'
              : connected
                ? 'bg-emerald-400'
                : 'bg-red-400'
          }
        >
          {unknown ? 'Checking' : connected ? 'Connected' : 'Offline'}
        </Chip>
      </div>
      <div className="rounded-lg border border-white/[0.06] bg-ink-900/70 px-3 py-2.5">
        <p className="label-cap mb-1">API endpoint</p>
        <p className="break-all font-mono text-[10px] leading-relaxed text-slate-500">
          {API_BASE_URL}
        </p>
      </div>
      <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-amber-200/80">
        <Radio className="h-3.5 w-3.5 text-amber-300" />
        Advisory only · no auto switching
      </div>
    </div>
  );
}

export function Sidebar({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { health, statusState } = useDashboard();
  const healthy = health?.status === 'healthy';

  return (
    <>
      {open ? (
        <div
          className="fixed inset-0 z-40 bg-ink-950/80 backdrop-blur-sm lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      ) : null}

      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-[264px] flex-col border-r border-white/[0.07] bg-ink-900/95 backdrop-blur-xl transition-transform duration-300 lg:translate-x-0 ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex items-center gap-3 border-b border-white/[0.06] px-4 py-4">
          <BrandMark />
          <div className="min-w-0 flex-1">
            <p className="font-display text-[15px] font-bold leading-none tracking-[0.06em] text-slate-100">
              BLACKSTART <span className="text-accent">AI</span>
            </p>
            <p className="mt-1.5 text-[9px] font-semibold uppercase tracking-[0.22em] text-slate-500">
              Grid Intelligence
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close navigation"
            className="rounded-md p-1.5 text-slate-500 transition hover:bg-white/5 hover:text-slate-200 lg:hidden"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex items-center gap-2 border-b border-white/[0.06] px-4 py-3">
          <StatusDot
            tone={statusState === 'error' ? 'error' : healthy ? 'ok' : 'warn'}
            pulse={statusState === 'loading'}
          />
          <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
            {statusState === 'error'
              ? 'Backend offline'
              : healthy
                ? 'FastAPI online'
                : 'Status unknown'}
          </span>
          <Zap className="ml-auto h-3 w-3 text-accent/70" />
        </div>

        <SidebarNav onNavigate={onClose} />
        <SidebarFooter />
      </aside>
    </>
  );
}
