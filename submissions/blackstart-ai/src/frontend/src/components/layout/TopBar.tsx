import { useLocation } from 'react-router-dom';
import { Clock, Database, Menu, Server } from 'lucide-react';
import { routeMeta } from '../../lib/routes';
import { useDashboard } from '../../state/DashboardContext';
import { formatTime } from '../../lib/format';
import { RefreshButton, RunAnalysisButton, StatusDot } from '../ui/bits';

export function TopBar({ onMenu }: { onMenu: () => void }) {
  const { pathname } = useLocation();
  const meta = routeMeta(pathname);
  const { health, db2, statusState, lastAnalysisAt } = useDashboard();

  const apiOnline = statusState === 'success' && health?.status === 'healthy';
  const apiError = statusState === 'error';
  const db2Connected = db2?.connected === true;

  return (
    <header className="sticky top-0 z-30 border-b border-white/[0.07] bg-ink-900/85 backdrop-blur-xl">
      <div className="flex h-16 items-center gap-3 px-4 sm:px-6">
        <button
          type="button"
          onClick={onMenu}
          aria-label="Open navigation"
          className="rounded-lg border border-white/10 bg-ink-800/80 p-2 text-slate-400 transition hover:border-accent/40 hover:text-accent lg:hidden"
        >
          <Menu className="h-4 w-4" />
        </button>

        <div className="min-w-0 flex-1">
          <p className="truncate font-display text-sm font-semibold tracking-wide text-slate-200 sm:text-[15px]">
            {meta.label}
          </p>
          <p className="hidden truncate text-[11px] text-slate-500 sm:block">
            {meta.description}
          </p>
        </div>

        <div className="hidden items-center gap-2 md:flex">
          <span
            className={`inline-flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] ${
              apiError
                ? 'border-red-500/40 bg-red-500/10 text-red-300'
                : apiOnline
                  ? 'border-emerald-400/35 bg-emerald-400/10 text-emerald-300'
                  : 'border-slate-500/40 bg-slate-500/10 text-slate-400'
            }`}
          >
            <StatusDot
              tone={apiError ? 'error' : apiOnline ? 'ok' : 'idle'}
              pulse={statusState === 'loading'}
            />
            <Server className="h-3 w-3" />
            {apiError ? 'API offline' : apiOnline ? 'System online' : 'System …'}
          </span>

          <span
            className={`inline-flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] ${
              statusState === 'success' && !db2Connected
                ? 'border-red-500/40 bg-red-500/10 text-red-300'
                : db2Connected
                  ? 'border-accent/30 bg-accent/[0.08] text-accent'
                  : 'border-slate-500/40 bg-slate-500/10 text-slate-400'
            }`}
          >
            <Database className="h-3 w-3" />
            {statusState === 'success'
              ? db2Connected
                ? 'Db2 connected'
                : 'Db2 offline'
              : 'Db2 …'}
          </span>
        </div>

        <span
          className="hidden items-center gap-2 rounded-lg border border-white/[0.08] bg-ink-800/70 px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400 xl:inline-flex"
          title="Timestamp of the last successful POST /api/v1/analyze"
        >
          <Clock className="h-3 w-3 text-slate-500" />
          Analysis
          <span className="font-mono normal-case tracking-normal text-slate-300">
            {lastAnalysisAt ? formatTime(lastAnalysisAt) : 'not run'}
          </span>
        </span>

        <RefreshButton />
        <RunAnalysisButton size="sm" className="whitespace-nowrap" />
      </div>
    </header>
  );
}
