import clsx from 'clsx';
import { forwardRef, type ButtonHTMLAttributes, type HTMLAttributes, type ReactNode } from 'react';
import { motion } from 'motion/react';
import { Loader2 } from 'lucide-react';
import type { Gate, Severity } from '@/lib/api';
import { GATE_META, SEV_COLOR } from '@/lib/format';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';

export const Button = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  icon?: ReactNode;
}>(function Button({ variant = 'secondary', size = 'md', loading, icon, className, children, disabled, ...rest }, ref) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={clsx(
        'focus-ring inline-flex items-center justify-center gap-2 rounded-xl font-medium transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-50 select-none',
        size === 'sm' && 'h-8 px-3 text-[13px]',
        size === 'md' && 'h-10 px-4 text-sm',
        size === 'lg' && 'h-12 px-6 text-[15px]',
        variant === 'primary' &&
          'bg-gradient-to-b from-brand-500 to-brand-600 text-white shadow-[0_8px_30px_-8px_rgba(15,98,254,0.7)] hover:brightness-110 active:brightness-95',
        variant === 'secondary' && 'bg-white/[0.06] text-fg ring-1 ring-line hover:bg-white/[0.1] hover:ring-line-strong',
        variant === 'ghost' && 'text-muted hover:bg-white/[0.06] hover:text-fg',
        variant === 'danger' && 'bg-sev-critical/12 text-sev-critical ring-1 ring-sev-critical/30 hover:bg-sev-critical/20',
        className,
      )}
      {...rest}
    >
      {loading ? <Loader2 className="size-4 animate-spin" /> : icon}
      {children}
    </button>
  );
});

export function Card({ className, children, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={clsx('glass rounded-2xl', className)} {...rest}>
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle, action, icon }: { title: ReactNode; subtitle?: ReactNode; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 px-5 pt-5">
      <div className="flex items-start gap-3">
        {icon && <div className="mt-0.5 grid size-8 place-items-center rounded-lg bg-white/[0.06] text-brand-400 ring-1 ring-line">{icon}</div>}
        <div>
          <h3 className="text-[15px] font-semibold tracking-tight text-fg">{title}</h3>
          {subtitle && <p className="mt-0.5 text-[13px] text-muted">{subtitle}</p>}
        </div>
      </div>
      {action}
    </div>
  );
}

export function SeverityBadge({ severity, className }: { severity: Severity; className?: string }) {
  return (
    <span
      className={clsx('inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider ring-1', className)}
      style={{ color: SEV_COLOR[severity], background: `${SEV_COLOR[severity]}1a`, boxShadow: `inset 0 0 0 1px ${SEV_COLOR[severity]}40` }}
    >
      <span className="size-1.5 rounded-full" style={{ background: SEV_COLOR[severity] }} />
      {severity}
    </span>
  );
}

export function GateBadge({ gate, size = 'md' }: { gate: Gate; size?: 'md' | 'lg' }) {
  const meta = GATE_META[gate];
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-2 rounded-full font-semibold ring-1',
        meta.tone,
        size === 'md' ? 'px-2.5 py-0.5 text-xs' : 'px-4 py-1.5 text-sm',
      )}
    >
      <span className="size-2 rounded-full" style={{ background: meta.color, boxShadow: `0 0 12px ${meta.color}` }} />
      {meta.label}
    </span>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('skeleton', className)} />;
}

export function EmptyState({ icon, title, body, action }: { icon: ReactNode; title: string; body: ReactNode; action?: ReactNode }) {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col items-center px-6 py-14 text-center">
      <div className="mb-4 grid size-12 place-items-center rounded-2xl bg-white/[0.05] text-brand-400 ring-1 ring-line">{icon}</div>
      <h4 className="text-base font-semibold">{title}</h4>
      <p className="mt-1 max-w-md text-sm text-muted">{body}</p>
      {action && <div className="mt-5">{action}</div>}
    </motion.div>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="mono rounded-md border border-line bg-white/[0.04] px-1.5 py-0.5 text-[11px] text-muted">{children}</kbd>;
}

export function ErrorNote({ error }: { error: Error | null }) {
  if (!error) return null;
  return (
    <div className="rounded-xl bg-sev-critical/10 px-4 py-3 text-sm text-sev-critical ring-1 ring-sev-critical/25">
      {error.message}
    </div>
  );
}

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow?: string; title: ReactNode; description?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div>
        {eyebrow && <p className="mono mb-2 text-xs font-medium uppercase tracking-[0.18em] text-brand-400">{eyebrow}</p>}
        <h1 className="text-3xl font-semibold tracking-tight text-fg sm:text-[34px]">{title}</h1>
        {description && <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-muted">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
