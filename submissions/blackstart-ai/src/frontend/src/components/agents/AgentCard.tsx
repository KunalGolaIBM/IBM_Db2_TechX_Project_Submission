import type { LucideIcon } from 'lucide-react';
import { Loader2 } from 'lucide-react';
import type { ReactNode } from 'react';

export type AgentCardStatus = 'idle' | 'running' | 'complete' | 'error';

const accents = {
  cyan: 'border-accent/30 bg-accent/[0.04]',
  sky: 'border-sky-400/30 bg-sky-400/[0.04]',
  amber: 'border-amber-400/30 bg-amber-400/[0.04]',
  red: 'border-red-500/30 bg-red-500/[0.04]',
  emerald: 'border-emerald-400/30 bg-emerald-400/[0.04]',
};

const iconAccents = {
  cyan: 'border-accent/30 bg-accent/10 text-accent',
  sky: 'border-sky-400/30 bg-sky-400/10 text-sky-300',
  amber: 'border-amber-400/30 bg-amber-400/10 text-amber-200',
  red: 'border-red-500/30 bg-red-500/10 text-red-300',
  emerald: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300',
};

const statusMeta: Record<
  AgentCardStatus,
  { label: string; className: string }
> = {
  idle: {
    label: 'awaiting analysis',
    className: 'border-slate-500/40 bg-slate-500/10 text-slate-400',
  },
  running: {
    label: 'executing',
    className: 'border-accent/40 bg-accent/10 text-accent',
  },
  complete: {
    label: 'findings returned',
    className: 'border-emerald-400/40 bg-emerald-400/10 text-emerald-300',
  },
  error: {
    label: 'run failed',
    className: 'border-red-500/40 bg-red-500/10 text-red-300',
  },
};

export function AgentCard({
  name,
  role,
  description,
  icon: Icon,
  accent,
  status,
  children,
  className = '',
}: {
  name: string;
  role: string;
  description: string;
  icon: LucideIcon;
  accent: keyof typeof accents;
  status: AgentCardStatus;
  children?: ReactNode;
  className?: string;
}) {
  const meta = statusMeta[status];

  return (
    <article
      className={`panel relative flex flex-col overflow-hidden transition-all duration-200 hover:shadow-panel-hover ${accents[accent]} ${className}`}
    >
      <div className="flex items-start justify-between gap-3 border-b border-white/[0.06] px-5 py-4">
        <div className="flex items-start gap-3">
          <span
            className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border ${iconAccents[accent]}`}
          >
            <Icon className="h-5 w-5" />
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="font-display text-base font-bold tracking-[0.1em] text-slate-100">
                {name}
              </h2>
              <span
                className={`text-[10px] font-semibold uppercase tracking-[0.16em] ${
                  accent === 'cyan'
                    ? 'text-accent'
                    : accent === 'sky'
                      ? 'text-sky-300'
                      : accent === 'amber'
                        ? 'text-amber-200'
                        : accent === 'red'
                          ? 'text-red-300'
                          : 'text-emerald-300'
                }`}
              >
                {role}
              </span>
            </div>
            <p className="mt-1 text-xs leading-relaxed text-slate-500">
              {description}
            </p>
          </div>
        </div>
        <span
          className={`inline-flex shrink-0 items-center gap-1.5 rounded-md border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${meta.className}`}
        >
          {status === 'running' ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : null}
          {meta.label}
        </span>
      </div>

      <div className="flex-1 px-5 py-5">{children}</div>
    </article>
  );
}

export function FindingRow({
  label,
  value,
  tone = 'text-slate-200',
}: {
  label: string;
  value: string;
  tone?: string;
}) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-white/[0.05] py-2.5 last:border-0">
      <span className="text-xs text-slate-500">{label}</span>
      <span className={`mono-num text-xs font-semibold ${tone}`}>{value}</span>
    </div>
  );
}

export function AgentEmpty({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-dashed border-white/10 bg-ink-900/50 px-4 py-5">
      <p className="text-xs leading-relaxed text-slate-500">{message}</p>
    </div>
  );
}
