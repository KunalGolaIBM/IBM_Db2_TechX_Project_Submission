import { LoaderCircle } from 'lucide-react'
import {
  useId,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from 'react'
import { cn } from '../lib/cn'

// ---- Button ------------------------------------------------------------------------------------------
type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
const buttonVariants: Record<ButtonVariant, string> = {
  // dark ink on copper: 8.3:1 (light ink would be 2:1)
  primary: 'bg-copper-400 text-ink-950 hover:bg-copper-300 font-semibold',
  secondary: 'bg-ink-750 text-fg border border-ink-600 hover:bg-ink-700',
  ghost: 'text-fg-2 hover:bg-ink-750 hover:text-fg',
  danger: 'border border-critical/70 bg-critical/10 text-fg hover:bg-critical/25',
}
const buttonSizes = { sm: 'h-8 px-3 text-[13px]', md: 'h-9 px-4 text-sm', lg: 'h-11 px-5 text-sm' } as const

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: keyof typeof buttonSizes
  loading?: boolean
  icon?: ReactNode
}

export function Button({
  variant = 'secondary',
  size = 'md',
  loading = false,
  icon,
  children,
  className,
  disabled,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        'inline-flex shrink-0 items-center justify-center gap-2 rounded-lg whitespace-nowrap transition-colors',
        'disabled:cursor-not-allowed disabled:opacity-50',
        buttonVariants[variant],
        buttonSizes[size],
        className,
      )}
      {...rest}
    >
      {loading ? <LoaderCircle className="size-4 animate-spin" aria-hidden /> : icon}
      {children}
    </button>
  )
}

// ---- Layout pieces ------------------------------------------------------------------------------------
export function Card({
  children,
  className,
  ...rest
}: { children: ReactNode; className?: string } & React.HTMLAttributes<HTMLElement>) {
  return (
    // min-w-0: a Card is often a grid/flex item, and without it a wide table inside forces the whole page wider
    <section className={cn('min-w-0 rounded-xl border border-ink-700 bg-ink-800', className)} {...rest}>
      {children}
    </section>
  )
}

export function CardHeader({
  title,
  subtitle,
  actions,
  id,
}: {
  title: ReactNode
  subtitle?: ReactNode
  actions?: ReactNode
  id?: string
}) {
  return (
    <header className="flex items-start justify-between gap-3 px-5 pt-4 pb-3">
      <div className="min-w-0 flex-1">
        <h2 id={id} className="text-[15px] leading-6 font-semibold text-fg">
          {title}
        </h2>
        {subtitle && <p className="mt-0.5 text-[13px] leading-5 text-fg-2">{subtitle}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </header>
  )
}

export const CardBody = ({ children, className }: { children: ReactNode; className?: string }) => (
  <div className={cn('px-5 pb-5', className)}>{children}</div>
)

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string
  description?: ReactNode
  actions?: ReactNode
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-2xl leading-8 font-semibold tracking-tight text-fg">{title}</h1>
        {description && <p className="mt-1 max-w-3xl text-sm leading-6 text-fg-2">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

// ---- Chips --------------------------------------------------------------------------------------------
export type Tone = 'neutral' | 'copper' | 'good' | 'warn' | 'critical' | 'info' | 'violet' | 'aqua'
const chipTones: Record<Tone, { box: string; icon: string }> = {
  neutral: { box: 'border-ink-600 bg-ink-750', icon: 'text-fg-3' },
  copper: { box: 'border-copper-500/50 bg-copper-500/12', icon: 'text-copper-400' },
  good: { box: 'border-good/45 bg-good/12', icon: 'text-good' },
  warn: { box: 'border-warn/45 bg-warn/12', icon: 'text-warn' },
  critical: { box: 'border-critical/55 bg-critical/12', icon: 'text-critical' },
  info: { box: 'border-series-2/50 bg-series-2/12', icon: 'text-series-2' },
  violet: { box: 'border-series-4/55 bg-series-4/12', icon: 'text-series-4' },
  aqua: { box: 'border-series-3/50 bg-series-3/12', icon: 'text-series-3' },
}

export function Chip({
  tone = 'neutral',
  icon,
  children,
  className,
  title,
  ...rest
}: {
  tone?: Tone
  icon?: ReactNode
  children: ReactNode
  className?: string
  title?: string
} & React.HTMLAttributes<HTMLSpanElement>) {
  const t = chipTones[tone]
  return (
    <span
      title={title}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs leading-5 font-medium whitespace-nowrap text-fg',
        t.box,
        className,
      )}
      {...rest}
    >
      {icon && (
        <span className={cn('inline-flex [&>svg]:size-3.5', t.icon)} aria-hidden>
          {icon}
        </span>
      )}
      {children}
    </span>
  )
}

export const toneIconClass = (tone: Tone): string => chipTones[tone].icon

// ---- Feedback -----------------------------------------------------------------------------------------
export function Spinner({ label = 'Loading' }: { label?: string }) {
  return (
    <span role="status" className="inline-flex items-center gap-2 text-sm text-fg-2">
      <LoaderCircle className="size-4 animate-spin text-copper-400" aria-hidden />
      <span>{label}…</span>
    </span>
  )
}

export function LoadingBlock({ label, className }: { label?: string; className?: string }) {
  return (
    <div className={cn('flex min-h-32 items-center justify-center', className)}>
      <Spinner label={label} />
    </div>
  )
}

export function EmptyState({
  icon,
  title,
  children,
  action,
}: {
  icon?: ReactNode
  title: string
  children?: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-10 text-center">
      {icon && (
        <div className="mb-1 rounded-full border border-ink-600 bg-ink-750 p-3 text-fg-3 [&>svg]:size-5" aria-hidden>
          {icon}
        </div>
      )}
      <p className="text-sm font-medium text-fg">{title}</p>
      {children && <p className="max-w-md text-[13px] leading-5 text-fg-2">{children}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}

// ---- Form controls ------------------------------------------------------------------------------------
export const controlClass =
  'w-full rounded-lg border border-ink-600 bg-ink-900 px-3 py-2 text-sm text-fg placeholder:text-fg-3 ' +
  'hover:border-fg-3 focus:border-copper-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-copper-300/50 ' +
  'disabled:cursor-not-allowed disabled:opacity-60 aria-[invalid=true]:border-critical'

interface FieldShellProps {
  label: string
  hint?: string
  error?: string | null
  className?: string
  /** Label beside the control instead of above it (compact toolbars). */
  inline?: boolean
}

function FieldShell({
  label,
  hint,
  error,
  className,
  inline,
  htmlFor,
  describedBy,
  children,
}: FieldShellProps & { htmlFor: string; describedBy: string; children: ReactNode }) {
  return (
    <div className={cn(inline ? 'flex items-center gap-2' : 'flex flex-col gap-1.5', className)}>
      <label htmlFor={htmlFor} className={cn('text-[13px] font-medium text-fg', inline && 'whitespace-nowrap')}>
        {label}
      </label>
      {children}
      {(hint || error) && (
        <p id={describedBy} className={cn('text-xs leading-5', error ? 'text-fg' : 'text-fg-3')}>
          {error ? <span className="text-critical">●</span> : null} {error ?? hint}
        </p>
      )}
    </div>
  )
}

export function TextInput({
  label,
  hint,
  error,
  className,
  inline,
  ...rest
}: FieldShellProps & InputHTMLAttributes<HTMLInputElement>) {
  const id = useId()
  return (
    <FieldShell label={label} hint={hint} error={error} className={className} inline={inline} htmlFor={id} describedBy={`${id}-d`}>
      <input
        id={id}
        className={controlClass}
        aria-invalid={error ? true : undefined}
        aria-describedby={hint || error ? `${id}-d` : undefined}
        {...rest}
      />
    </FieldShell>
  )
}

export function TextArea({
  label,
  hint,
  error,
  className,
  inline,
  ...rest
}: FieldShellProps & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const id = useId()
  return (
    <FieldShell label={label} hint={hint} error={error} className={className} inline={inline} htmlFor={id} describedBy={`${id}-d`}>
      <textarea
        id={id}
        className={cn(controlClass, 'min-h-24 resize-y leading-6')}
        aria-invalid={error ? true : undefined}
        aria-describedby={hint || error ? `${id}-d` : undefined}
        {...rest}
      />
    </FieldShell>
  )
}

export function SelectInput({
  label,
  hint,
  error,
  className,
  inline,
  children,
  ...rest
}: FieldShellProps & SelectHTMLAttributes<HTMLSelectElement>) {
  const id = useId()
  return (
    <FieldShell label={label} hint={hint} error={error} className={className} inline={inline} htmlFor={id} describedBy={`${id}-d`}>
      <select
        id={id}
        className={controlClass}
        aria-invalid={error ? true : undefined}
        aria-describedby={hint || error ? `${id}-d` : undefined}
        {...rest}
      >
        {children}
      </select>
    </FieldShell>
  )
}

export function Checkbox({
  label,
  className,
  ...rest
}: { label: ReactNode } & Omit<InputHTMLAttributes<HTMLInputElement>, 'type'>) {
  const id = useId()
  return (
    <label htmlFor={id} className={cn('inline-flex cursor-pointer items-center gap-2 text-sm text-fg', className)}>
      <input id={id} type="checkbox" className="size-4 accent-copper-400" {...rest} />
      <span>{label}</span>
    </label>
  )
}

/** A toggleable filter chip (aria-pressed), used for category filters. */
export function ToggleChip({
  pressed,
  onToggle,
  children,
  swatch,
  count,
}: {
  pressed: boolean
  onToggle: () => void
  children: ReactNode
  swatch?: ReactNode
  count?: number
}) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onToggle}
      className={cn(
        'inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-[13px] transition-colors',
        pressed
          ? 'border-copper-400 bg-copper-500/18 text-fg'
          : 'border-ink-600 bg-ink-800 text-fg-2 hover:border-fg-3 hover:text-fg',
      )}
    >
      {swatch}
      {children}
      {count !== undefined && <span className="text-xs text-fg-3 tabular-nums">{count}</span>}
    </button>
  )
}
