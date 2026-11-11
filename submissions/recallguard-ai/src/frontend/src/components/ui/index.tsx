/* shadcn/ui-style primitives (CVA + tailwind-merge + Radix Slot), tuned for the dark command-centre theme. */
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { AlertTriangle, Inbox, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-cyan-500 text-ink-950 hover:bg-cyan-400 shadow-[0_0_20px_-6px_rgba(34,211,238,.7)]",
        secondary: "border border-line bg-ink-800 text-slate-100 hover:bg-ink-700",
        ghost: "text-slate-300 hover:bg-ink-800 hover:text-white",
        success: "bg-emerald-500 text-ink-950 hover:bg-emerald-400",
        danger: "border border-red-500/40 bg-red-500/10 text-red-300 hover:bg-red-500/20",
        outline: "border border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/10",
      },
      size: { sm: "h-8 px-3 text-xs", md: "h-9 px-4", lg: "h-11 px-5 text-[15px]", icon: "h-9 w-9" },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  loading?: boolean;
}
export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, asChild, loading, children, disabled, ...props }, ref) => {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp ref={ref} className={cn(buttonVariants({ variant, size }), className)} disabled={disabled || loading} {...props}>
      {asChild ? children : <>{loading && <Loader2 className="animate-spin" />}{children}</>}
    </Comp>
  );
});
Button.displayName = "Button";

export function Card({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("glass", className)} {...p} />;
}
export function CardHeader({ title, subtitle, icon, action, className }: { title: React.ReactNode; subtitle?: React.ReactNode; icon?: React.ReactNode; action?: React.ReactNode; className?: string }) {
  return (
    <div className={cn("flex items-start justify-between gap-3 border-b border-line px-4 py-3", className)}>
      <div className="flex min-w-0 items-start gap-2.5">
        {icon && <div className="mt-0.5 text-cyan-400 [&_svg]:size-4">{icon}</div>}
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-slate-100">{title}</h3>
          {subtitle && <p className="mt-0.5 text-xs text-slate-400">{subtitle}</p>}
        </div>
      </div>
      {action}
    </div>
  );
}

const toneMap = {
  red: "border-red-500/30 bg-red-500/10 text-red-300",
  amber: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  emerald: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  cyan: "border-cyan-500/30 bg-cyan-500/10 text-cyan-300",
  violet: "border-violet-500/30 bg-violet-500/10 text-violet-300",
  slate: "border-slate-500/30 bg-slate-500/10 text-slate-300",
};
export type Tone = keyof typeof toneMap;
export function Badge({ tone = "slate", children, className, dot }: { tone?: Tone; children: React.ReactNode; className?: string; dot?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-md border px-1.5 py-0.5 text-[11px] font-medium leading-4", toneMap[tone], className)}>
      {dot && <span className="size-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}

export function Progress({ value, tone = "cyan", className }: { value: number; tone?: "cyan" | "emerald" | "amber" | "red"; className?: string }) {
  const color = { cyan: "bg-cyan-400", emerald: "bg-emerald-400", amber: "bg-amber-400", red: "bg-red-400" }[tone];
  return (
    <div className={cn("h-1.5 w-full overflow-hidden rounded-full bg-ink-700", className)} role="progressbar" aria-valuenow={Math.round(value)} aria-valuemin={0} aria-valuemax={100}>
      <div className={cn("h-full rounded-full transition-all duration-500", color)} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-ink-800", className)} />;
}

export function LoadingState({ label = "Loading…", rows = 3 }: { label?: string; rows?: number }) {
  return (
    <div className="space-y-2 p-4" aria-busy="true" aria-label={label}>
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const msg = error instanceof Error ? error.message : String(error);
  return (
    <div role="alert" className="m-4 flex items-start gap-3 rounded-lg border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-200">
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-red-400" />
      <div className="flex-1">
        <p className="font-medium">Something went wrong</p>
        <p className="mt-1 text-red-300/80">{msg}</p>
      </div>
      {onRetry && <Button size="sm" variant="danger" onClick={onRetry}>Retry</Button>}
    </div>
  );
}

export function EmptyState({ title, hint, action }: { title: string; hint?: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      <Inbox className="size-8 text-slate-600" />
      <p className="text-sm font-medium text-slate-300">{title}</p>
      {hint && <p className="max-w-sm text-xs text-slate-500">{hint}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function StatCard({ label, value, icon, tone = "cyan", hint }: { label: string; value: React.ReactNode; icon: React.ReactNode; tone?: Tone; hint?: string }) {
  const iconTone = { red: "text-red-400 bg-red-500/10", amber: "text-amber-300 bg-amber-500/10", emerald: "text-emerald-300 bg-emerald-500/10", cyan: "text-cyan-300 bg-cyan-500/10", violet: "text-violet-300 bg-violet-500/10", slate: "text-slate-300 bg-slate-500/10" }[tone];
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between">
        <p className="label">{label}</p>
        <div className={cn("grid size-8 place-items-center rounded-lg [&_svg]:size-4", iconTone)}>{icon}</div>
      </div>
      <p className="mt-2 text-2xl font-semibold tabular-nums text-white">{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </Card>
  );
}

export function PageHeader({ title, subtitle, actions, eyebrow }: { title: string; subtitle?: React.ReactNode; actions?: React.ReactNode; eyebrow?: string }) {
  return (
    <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
      <div>
        {eyebrow && <p className="label mb-1 text-cyan-400/80">{eyebrow}</p>}
        <h1 className="text-xl font-semibold tracking-tight text-white md:text-2xl">{title}</h1>
        {subtitle && <p className="mt-1 max-w-3xl text-sm text-slate-400">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Tabs<T extends string>({ value, onChange, items }: { value: T; onChange: (v: T) => void; items: { value: T; label: React.ReactNode }[] }) {
  return (
    <div role="tablist" className="inline-flex flex-wrap gap-1 rounded-lg border border-line bg-ink-900/80 p-1">
      {items.map((it) => (
        <button key={it.value} role="tab" aria-selected={value === it.value} onClick={() => onChange(it.value)}
          className={cn("rounded-md px-3 py-1.5 text-xs font-medium transition-colors", value === it.value ? "bg-ink-700 text-white" : "text-slate-400 hover:text-slate-200")}>
          {it.label}
        </button>
      ))}
    </div>
  );
}

export function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <label className="block space-y-1.5">
      <span className="label">{label}</span>
      {children}
      {hint && <span className="block text-[11px] text-slate-500">{hint}</span>}
    </label>
  );
}
