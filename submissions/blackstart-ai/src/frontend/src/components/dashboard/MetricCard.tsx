import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';
import { Skeleton } from '../ui/states';

export type MetricTone = 'cyan' | 'emerald' | 'amber' | 'red' | 'slate' | 'sky';

const toneStyles: Record<MetricTone, { icon: string; value: string; ring: string }> = {
  cyan: {
    icon: 'border-accent/30 bg-accent/10 text-accent',
    value: 'text-accent',
    ring: 'hover:border-accent/30',
  },
  sky: {
    icon: 'border-sky-400/30 bg-sky-400/10 text-sky-300',
    value: 'text-sky-200',
    ring: 'hover:border-sky-400/30',
  },
  emerald: {
    icon: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300',
    value: 'text-emerald-300',
    ring: 'hover:border-emerald-400/30',
  },
  amber: {
    icon: 'border-amber-400/30 bg-amber-400/10 text-amber-200',
    value: 'text-amber-200',
    ring: 'hover:border-amber-400/30',
  },
  red: {
    icon: 'border-red-500/30 bg-red-500/10 text-red-300',
    value: 'text-red-300',
    ring: 'hover:border-red-500/30',
  },
  slate: {
    icon: 'border-slate-500/30 bg-slate-500/10 text-slate-400',
    value: 'text-slate-200',
    ring: 'hover:border-slate-500/30',
  },
};

export function MetricCard({
  label,
  value,
  sub,
  icon: Icon,
  tone = 'slate',
  loading = false,
  footer,
}: {
  label: string;
  value: string;
  sub: string;
  icon: LucideIcon;
  tone?: MetricTone;
  loading?: boolean;
  footer?: ReactNode;
}) {
  const styles = toneStyles[tone];

  return (
    <div
      className={`panel panel-hover relative overflow-hidden p-5 ${styles.ring}`}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="label-cap">{label}</p>
        <span
          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border ${styles.icon}`}
        >
          <Icon className="h-4 w-4" />
        </span>
      </div>

      {loading ? (
        <div className="mt-4 space-y-2">
          <Skeleton className="h-8 w-24" />
          <Skeleton className="h-3 w-32" />
        </div>
      ) : (
        <>
          <p
            className={`mt-3 font-display text-[32px] font-semibold leading-none tracking-tight ${styles.value}`}
          >
            {value}
          </p>
          <p className="mt-2 text-xs leading-relaxed text-slate-500">{sub}</p>
          {footer ? <div className="mt-3 border-t border-white/[0.06] pt-3">{footer}</div> : null}
        </>
      )}
    </div>
  );
}
