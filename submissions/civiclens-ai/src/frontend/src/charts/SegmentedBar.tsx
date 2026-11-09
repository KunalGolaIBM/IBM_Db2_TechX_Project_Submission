import { EmptyState } from '../components/ui'
import { formatInt, formatPercent } from '../lib/format'
import { readableInk, share } from './scales'
import { TipContent, TooltipBubble, useChartTooltip } from './Tooltip'
import { useElementWidth } from './useElementWidth'

export interface SegmentDatum {
  key: string
  label: string
  value: number
  color: string
}

const GAP = 2 // a 2px surface gap separates blocks
const MIN_LABEL_WIDTH = 52

/**
 * Tall segmented bar: one whole split into <= 6 parts. Each part is its own block (4px corners, 2px gaps),
 * its share is printed inside only when it fits, and the legend names the parts without repeating numbers.
 */
export function SegmentedBar({
  data,
  ariaLabel,
  valueNoun = 'recommendations',
}: {
  data: SegmentDatum[]
  ariaLabel: string
  valueNoun?: string
}) {
  const [boxRef, width] = useElementWidth<HTMLDivElement>()
  const { wrapperRef, tip, showAtElement, showAtPointer, hide } = useChartTooltip()
  const parts = data.filter((d) => d.value > 0) // a part at zero draws nothing
  const total = parts.reduce((s, d) => s + d.value, 0)
  if (total === 0) return <EmptyState title="Nothing to show yet">{`No ${valueNoun} have been recorded.`}</EmptyState>

  const usable = Math.max(width - GAP * (parts.length - 1), 1)
  return (
    <div ref={wrapperRef} className="relative">
      <div
        ref={boxRef}
        role="group"
        aria-label={`${ariaLabel}: ${parts.map((p) => `${p.label} ${p.value} (${formatPercent(share(p.value, total))})`).join(', ')}`}
        className="flex h-7"
        style={{ gap: GAP }}
      >
        {parts.map((p) => {
          const w = (p.value / total) * usable
          const pct = formatPercent(share(p.value, total))
          const content = (
            <TipContent title={p.label} value={`${formatInt(p.value)} ${valueNoun}`} detail={pct} color={p.color} />
          )
          return (
            <div
              key={p.key}
              tabIndex={0}
              role="img"
              aria-label={`${p.label}: ${p.value} ${valueNoun}, ${pct}`}
              data-testid="segment"
              data-key={p.key}
              data-value={p.value}
              onPointerMove={(e) => showAtPointer(e, content)}
              onPointerLeave={hide}
              onFocus={(e) => showAtElement(e.currentTarget, content)}
              onBlur={hide}
              className="flex items-center justify-start overflow-visible rounded-[4px] px-2 text-xs font-semibold tabular-nums hover:brightness-110"
              style={{ width: w, background: p.color, color: readableInk(p.color) }}
            >
              {w >= MIN_LABEL_WIDTH ? pct : null}
            </div>
          )
        })}
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5" aria-label="Legend">
        {parts.map((p) => (
          <li key={p.key} className="flex items-center gap-1.5 text-[13px] text-fg-2">
            <span className="size-2.5 rounded-[3px]" style={{ background: p.color }} aria-hidden />
            {p.label}
          </li>
        ))}
      </ul>
      <TooltipBubble tip={tip} />
    </div>
  )
}
