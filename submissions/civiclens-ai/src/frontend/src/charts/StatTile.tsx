import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Card } from '../components/ui'
import { cn } from '../lib/cn'

/** Stat tile: label (sentence case) - value - optional context line and trend. `hero` is the one 48px+ figure. */
export function StatTile({
  label,
  value,
  context,
  trend,
  hero = false,
  icon,
  testId,
  className,
  to,
}: {
  label: string
  value: string
  context?: ReactNode
  trend?: ReactNode
  hero?: boolean
  icon?: ReactNode
  testId?: string
  className?: string
  to?: string
}) {
  const tile = (
    <Card className={cn('flex h-full flex-col gap-2 p-5', to && 'transition-colors hover:border-copper-500/60', className)} data-testid={testId}>
      <div className="flex items-center gap-2 text-[13px] font-medium text-fg-2">
        {icon && (
          <span className="text-fg-3 [&>svg]:size-4" aria-hidden>
            {icon}
          </span>
        )}
        {label}
      </div>
      {/* proportional figures for big standalone numbers (tabular-nums is for aligned columns only) */}
      <div
        data-testid={testId ? `${testId}-value` : undefined}
        className={cn('font-semibold tracking-tight text-fg', hero ? 'text-[56px] leading-[1.05]' : 'text-[32px] leading-9')}
      >
        {value}
      </div>
      {context && <div className="text-[13px] leading-5 text-fg-2">{context}</div>}
      {trend && <div className="mt-1">{trend}</div>}
    </Card>
  )
  return to ? (
    // no aria-label: the link is named by its visible content (WCAG 2.5.3 Label in Name)
    <Link to={to} className="block h-full rounded-xl">
      {tile}
    </Link>
  ) : (
    tile
  )
}
