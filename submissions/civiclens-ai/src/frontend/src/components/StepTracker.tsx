import { Check, X } from 'lucide-react'
import type { InvestigationStatus } from '../lib/domain'
import { cn } from '../lib/cn'

const STEPS: Array<{ status: InvestigationStatus; label: string }> = [
  { status: 'OPEN', label: 'Open' },
  { status: 'RUNNING', label: 'Running' },
  { status: 'PENDING_REVIEW', label: 'Pending review' },
  { status: 'CLOSED', label: 'Closed' },
]

/** Where an investigation is in its lifecycle. FAILED is shown as a stopped Running step. */
export function StepTracker({ status }: { status: InvestigationStatus }) {
  const failed = status === 'FAILED'
  const current = failed ? 1 : STEPS.findIndex((s) => s.status === status)
  return (
    <ol className="flex flex-wrap items-center gap-x-2 gap-y-2" aria-label="Investigation progress" data-testid="step-tracker">
      {STEPS.map((step, i) => {
        const done = i < current || (status === 'CLOSED' && i === current)
        const isCurrent = i === current && !done
        const isFailedStep = failed && i === 1
        return (
          <li key={step.status} className="flex items-center gap-2" aria-current={isCurrent || isFailedStep ? 'step' : undefined}>
            <span
              className={cn(
                'flex size-6 items-center justify-center rounded-full border text-xs font-semibold',
                done && 'border-good bg-good/20 text-fg',
                isCurrent && !isFailedStep && 'border-copper-400 bg-copper-500/20 text-fg',
                isFailedStep && 'border-critical bg-critical/20 text-fg',
                !done && !isCurrent && !isFailedStep && 'border-ink-600 text-fg-3',
              )}
            >
              {isFailedStep ? <X className="size-3.5" aria-hidden /> : done ? <Check className="size-3.5" aria-hidden /> : i + 1}
            </span>
            <span className={cn('text-[13px]', done || isCurrent || isFailedStep ? 'font-medium text-fg' : 'text-fg-3')}>
              {isFailedStep ? 'Failed' : step.label}
            </span>
            {i < STEPS.length - 1 && <span className="mx-1 hidden h-px w-6 bg-ink-600 sm:block" aria-hidden />}
          </li>
        )
      })}
    </ol>
  )
}
