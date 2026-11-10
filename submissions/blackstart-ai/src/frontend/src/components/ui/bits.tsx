import { useState, type ReactNode } from 'react';
import { Loader2, Play, RefreshCw } from 'lucide-react';
import { useDashboard } from '../../state/DashboardContext';

export function Chip({
  children,
  className = '',
  dot,
}: {
  children: ReactNode;
  className?: string;
  dot?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em] ${className}`}
    >
      {dot ? <span className={`h-1.5 w-1.5 rounded-full ${dot}`} /> : null}
      {children}
    </span>
  );
}

export function SectionHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <p className="label-cap text-accent/80">{eyebrow}</p>
        <h1 className="mt-1.5 font-display text-2xl font-semibold tracking-tight text-slate-100 sm:text-[28px]">
          {title}
        </h1>
        {description ? (
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-500">
            {description}
          </p>
        ) : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function RunAnalysisButton({
  size = 'md',
  className = '',
}: {
  size?: 'sm' | 'md';
  className?: string;
}) {
  const { analysisState, runAnalysis } = useDashboard();
  const running = analysisState === 'running';
  const sizing =
    size === 'sm'
      ? 'px-3 py-1.5 text-[10px]'
      : 'px-4 py-2.5 text-[11px]';

  return (
    <button
      type="button"
      onClick={() => void runAnalysis()}
      disabled={running}
      className={`group relative inline-flex items-center justify-center gap-2 overflow-hidden rounded-lg font-semibold uppercase tracking-[0.14em] transition-all duration-200 disabled:cursor-not-allowed ${sizing} ${
        running
          ? 'cursor-wait border border-accent/30 bg-accent/10 text-accent'
          : 'bg-accent text-ink-950 shadow-glow hover:bg-accent-bright active:scale-[0.98]'
      } ${className}`}
    >
      {running ? (
        <>
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Analyzing grid…
        </>
      ) : (
        <>
          <Play className="h-3.5 w-3.5 fill-current" />
          Run Intelligence Analysis
        </>
      )}
    </button>
  );
}

export function RefreshButton({
  onDone,
  className = '',
}: {
  onDone?: () => void;
  className?: string;
}) {
  const { refreshAll } = useDashboard();
  const [refreshing, setRefreshing] = useState(false);

  return (
    <button
      type="button"
      onClick={async () => {
        setRefreshing(true);
        try {
          await refreshAll();
          onDone?.();
        } finally {
          setRefreshing(false);
        }
      }}
      aria-label="Refresh dashboard data"
      title="Refresh dashboard data"
      className={`inline-flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 bg-ink-800/80 text-slate-400 transition hover:border-accent/40 hover:text-accent active:scale-95 ${className}`}
    >
      <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
    </button>
  );
}

export function StatusDot({
  tone,
  pulse = false,
}: {
  tone: 'ok' | 'warn' | 'error' | 'idle';
  pulse?: boolean;
}) {
  const toneClass =
    tone === 'ok'
      ? 'bg-emerald-400'
      : tone === 'warn'
        ? 'bg-amber-300'
        : tone === 'error'
          ? 'bg-red-400'
          : 'bg-slate-500';

  return (
    <span className="relative flex h-2 w-2">
      {pulse ? (
        <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-60 ${toneClass}`} />
      ) : null}
      <span className={`relative inline-flex h-2 w-2 rounded-full ${toneClass}`} />
    </span>
  );
}
