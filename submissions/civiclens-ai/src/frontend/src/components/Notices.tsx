import { CircleCheck, FlaskConical, Info, RefreshCw, TriangleAlert, CircleX, X } from 'lucide-react'
import type { ReactNode } from 'react'
import { describeError } from '../lib/errorText'
import { cn } from '../lib/cn'
import { Button } from './ui'

/** Renders any API failure: what happened, why, which values, and the status + code for support. */
export function ErrorNotice({
  error,
  onRetry,
  onDismiss,
  className,
}: {
  error: unknown
  onRetry?: () => void
  onDismiss?: () => void
  className?: string
}) {
  const d = describeError(error)
  const warning = d.tone === 'warning'
  const Icon = warning ? TriangleAlert : CircleX
  return (
    <div
      role="alert"
      data-testid="error-notice"
      data-status={d.status}
      data-code={d.code}
      className={cn(
        'rounded-xl border p-4',
        warning ? 'border-warn/45 bg-warn/10' : 'border-critical/55 bg-critical/10',
        className,
      )}
    >
      <div className="flex gap-3">
        <Icon className={cn('mt-0.5 size-5 shrink-0', warning ? 'text-warn' : 'text-critical')} aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-fg">{d.title}</p>
          <p className="mt-0.5 text-sm leading-6 text-fg-2">{d.message}</p>
          {d.items.length > 0 && (
            <ul className="mt-2 list-disc space-y-0.5 pl-5 text-sm text-fg-2">
              {d.items.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          )}
          <p className="mt-2 font-mono text-xs text-fg-3">
            {d.status ? `HTTP ${d.status}` : 'No response'} · {d.code}
          </p>
        </div>
        <div className="flex shrink-0 items-start gap-1">
          {onRetry && (
            <Button size="sm" onClick={onRetry} icon={<RefreshCw className="size-3.5" aria-hidden />}>
              Retry
            </Button>
          )}
          {onDismiss && (
            <button
              type="button"
              onClick={onDismiss}
              aria-label="Dismiss message"
              className="rounded-md p-1.5 text-fg-2 hover:bg-ink-750 hover:text-fg"
            >
              <X className="size-4" aria-hidden />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export function SuccessNotice({
  title,
  children,
  onDismiss,
  className,
}: {
  title: string
  children?: ReactNode
  onDismiss?: () => void
  className?: string
}) {
  return (
    <div
      role="status"
      data-testid="success-notice"
      className={cn('rounded-xl border border-good/45 bg-good/10 p-4', className)}
    >
      <div className="flex gap-3">
        <CircleCheck className="mt-0.5 size-5 shrink-0 text-good" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-fg">{title}</p>
          {children && <div className="mt-0.5 text-sm leading-6 text-fg-2">{children}</div>}
        </div>
        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            aria-label="Dismiss message"
            className="h-fit rounded-md p-1.5 text-fg-2 hover:bg-ink-750 hover:text-fg"
          >
            <X className="size-4" aria-hidden />
          </button>
        )}
      </div>
    </div>
  )
}

export function InfoNotice({ title, children, className }: { title?: string; children: ReactNode; className?: string }) {
  return (
    <div className={cn('rounded-xl border border-series-2/40 bg-series-2/10 p-4', className)}>
      <div className="flex gap-3">
        <Info className="mt-0.5 size-5 shrink-0 text-series-2" aria-hidden />
        <div className="min-w-0 text-sm leading-6 text-fg-2">
          {title && <p className="font-semibold text-fg">{title}</p>}
          {children}
        </div>
      </div>
    </div>
  )
}

/** Shown wherever synthetic data is present, so demonstration data is never mistaken for real reports. */
export function SyntheticBanner({ synthetic, total }: { synthetic: number; total: number }) {
  if (synthetic <= 0) return null
  const all = synthetic === total
  return (
    <div
      data-testid="synthetic-banner"
      className="flex items-start gap-3 rounded-xl border border-dashed border-fg-3/70 bg-ink-850 px-4 py-3"
    >
      <FlaskConical className="mt-0.5 size-5 shrink-0 text-fg-2" aria-hidden />
      <p className="text-sm leading-6 text-fg-2">
        <strong className="font-semibold text-fg">Demonstration data.</strong>{' '}
        {all
          ? total === 1
            ? 'The only complaint in this database is SYNTHETIC: a fictional record generated for the hackathon demo, not a real citizen report.'
            : `All ${total} complaints in this database are SYNTHETIC: fictional records generated for the hackathon demo, not real citizen reports.`
          : `${synthetic} of ${total} ${total === 1 ? 'complaint is' : 'complaints are'} SYNTHETIC: fictional demonstration records, marked wherever they appear.`}
      </p>
    </div>
  )
}
