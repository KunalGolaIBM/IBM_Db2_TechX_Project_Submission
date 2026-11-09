import { EmptyState } from '../components/ui'
import { formatInt, formatPercent } from '../lib/format'
import { share } from './scales'
import { TipContent, TooltipBubble, useChartTooltip } from './Tooltip'

export interface BarDatum {
  key: string
  label: string
  value: number
  note?: string
}

/**
 * Ranked horizontal bars for one nominal series: every bar shares slot-1 (identity is the label, not the
 * colour). Thin (14px) bars, square at the baseline and 4px rounded at the data end, value printed at the tip.
 */
export function RankedBars({
  data,
  ariaLabel,
  valueNoun = 'complaints',
  color = 'var(--color-series-1)',
}: {
  data: BarDatum[]
  ariaLabel: string
  valueNoun?: string
  color?: string
}) {
  const { wrapperRef, tip, showAtPointer, showAtElement, hide } = useChartTooltip()
  if (data.length === 0) return <EmptyState title="No data yet">Nothing to chart for this period.</EmptyState>
  const total = data.reduce((sum, d) => sum + d.value, 0)
  const max = Math.max(...data.map((d) => d.value), 1)

  return (
    <div ref={wrapperRef} className="relative">
      <ul aria-label={ariaLabel} className="flex flex-col gap-0.5">
        {data.map((d) => {
          const ratio = d.value / max
          const tipContent = (
            <TipContent
              title={d.label}
              value={`${formatInt(d.value)} ${valueNoun}`}
              detail={`${formatPercent(share(d.value, total))} of total${d.note ? ` · ${d.note}` : ''}`}
              color={color}
            />
          )
          return (
            <li
              key={d.key}
              tabIndex={0}
              aria-label={`${d.label}: ${d.value} ${valueNoun}`}
              data-testid="bar-row"
              data-key={d.key}
              data-value={d.value}
              onPointerMove={(e) => showAtPointer(e, tipContent)}
              onPointerLeave={hide}
              onFocus={(e) => showAtElement(e.currentTarget, tipContent)}
              onBlur={hide}
              className="group grid grid-cols-[minmax(6.5rem,9.5rem)_1fr] items-center gap-3 rounded-md px-1 py-0.5 hover:bg-ink-750/70"
            >
              <span className="truncate text-[13px] text-fg-2 group-hover:text-fg" title={d.label}>
                {d.label}
              </span>
              <span className="relative block h-5">
                <span
                  className="absolute inset-y-[3px] left-0 rounded-r-[4px] group-hover:brightness-125"
                  style={{ width: `calc((100% - 3rem) * ${ratio})`, minWidth: 3, background: color }}
                />
                <span
                  className="absolute top-1/2 -translate-y-1/2 text-[13px] font-semibold text-fg tabular-nums"
                  style={{ left: `calc((100% - 3rem) * ${ratio} + 8px)` }}
                >
                  {formatInt(d.value)}
                </span>
              </span>
            </li>
          )
        })}
      </ul>
      <TooltipBubble tip={tip} />
    </div>
  )
}
