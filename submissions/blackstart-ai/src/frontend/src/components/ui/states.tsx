import type { ReactNode } from 'react';
import { AlertTriangle, Inbox, RefreshCw } from 'lucide-react';

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden="true" />;
}

export function LoadingBlock({
  label = 'Fetching connected demonstration grid data from IBM Db2…',
  rows = 4,
}: {
  label?: string;
  rows?: number;
}) {
  return (
    <div className="space-y-4 p-5" role="status" aria-live="polite">
      <div className="flex items-center gap-3">
        <span className="relative flex h-2.5 w-2.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent/70" />
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-accent" />
        </span>
        <span className="text-xs font-medium uppercase tracking-[0.16em] text-slate-400">
          {label}
        </span>
      </div>
      <div className="space-y-3">
        {Array.from({ length: rows }).map((_, index) => (
          <Skeleton key={index} className="h-9 w-full" />
        ))}
      </div>
    </div>
  );
}

export function ErrorBlock({
  message,
  onRetry,
  title = 'Backend unreachable',
}: {
  message: string;
  onRetry?: () => void;
  title?: string;
}) {
  return (
    <div
      className="flex flex-col items-start gap-4 p-6"
      role="alert"
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-red-500/35 bg-red-500/10">
          <AlertTriangle className="text-red-300" size={18} />
        </span>
        <div>
          <p className="text-sm font-semibold text-red-200">{title}</p>
          <p className="mt-1 max-w-xl text-sm leading-relaxed text-slate-400">{message}</p>
        </div>
      </div>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-ink-700 px-4 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-200 transition hover:border-accent/40 hover:text-accent"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Retry request
        </button>
      ) : null}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl border border-dashed border-white/15 bg-ink-800 text-slate-500">
        {icon ?? <Inbox className="h-5 w-5" />}
      </div>
      <p className="font-display text-sm font-semibold tracking-wide text-slate-300">
        {title}
      </p>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-slate-500">{description}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}
