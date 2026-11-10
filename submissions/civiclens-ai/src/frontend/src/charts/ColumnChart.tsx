import { formatInt, formatPercent } from '../lib/format'
import { share } from './scales'
import { TipContent, TooltipBubble, useChartTooltip } from './Tooltip'
import { useElementWidth } from './useElementWidth'

export interface ColumnDatum {
  key: string
  label: string
  sublabel?: string
  value: number
  color: string
}

const HEIGHT = 196
const M = { top: 24, right: 8, bottom: 46, left: 8 }
const MAX_COLUMN = 24 // columns are never wider than 24px

/** Columns for an ORDINAL scale (severity 1-5) in a one-hue ramp; every value is labelled on its cap. */
export function ColumnChart({
  data,
  ariaLabel,
  valueNoun = 'complaints',
}: {
  data: ColumnDatum[]
  ariaLabel: string
  valueNoun?: string
}) {
  const [boxRef, width] = useElementWidth<HTMLDivElement>()
  const { wrapperRef, tip, showAtElement, showAtPointer, hide } = useChartTooltip()
  const innerW = Math.max(width - M.left - M.right, 10)
  const innerH = HEIGHT - M.top - M.bottom
  const baseline = M.top + innerH
  const band = innerW / Math.max(data.length, 1)
  const colW = Math.min(MAX_COLUMN, band * 0.5)
  const max = Math.max(...data.map((d) => d.value), 1)
  const total = data.reduce((s, d) => s + d.value, 0)

  return (
    <div ref={wrapperRef} className="relative">
      <div ref={boxRef}>
        <svg width={width} height={HEIGHT} role="group" aria-label={ariaLabel} className="block overflow-visible">
          <line x1={M.left} x2={width - M.right} y1={baseline} y2={baseline} stroke="var(--color-ink-600)" strokeWidth={1} />
          {data.map((d, i) => {
            const cx = M.left + band * i + band / 2
            const x = cx - colW / 2
            const h = d.value > 0 ? Math.max((d.value / max) * innerH, 4) : 0
            const y = baseline - h
            const r = Math.min(4, h / 2)
            const content = (
              <TipContent
                title={d.sublabel ? `Severity ${d.label}: ${d.sublabel}` : d.label}
                value={`${formatInt(d.value)} ${valueNoun}`}
                detail={`${formatPercent(share(d.value, total))} of total`}
                color={d.color}
              />
            )
            return (
              <g
                key={d.key}
                tabIndex={0}
                role="img"
                aria-label={`${d.sublabel ? `Severity ${d.label} (${d.sublabel})` : d.label}: ${d.value} ${valueNoun}`}
                data-testid="column"
                data-key={d.key}
                data-value={d.value}
                onPointerMove={(e) => showAtPointer(e, content)}
                onPointerLeave={hide}
                onFocus={(e) => showAtElement(e.currentTarget as unknown as Element, content)}
                onBlur={hide}
                className="group outline-none focus-visible:[&>rect.focus]:stroke-copper-300"
              >
                {/* hit area: the whole band, much larger than the painted column */}
                <rect x={cx - band / 2} y={M.top - 16} width={band} height={innerH + 16 + 30} fill="transparent" className="focus" strokeWidth={2} rx={6} />
                {h > 0 && (
                  <path
                    d={`M${x},${baseline} L${x},${y + r} Q${x},${y} ${x + r},${y} L${x + colW - r},${y} Q${x + colW},${y} ${x + colW},${y + r} L${x + colW},${baseline} Z`}
                    fill={d.color}
                    className="group-hover:brightness-125"
                  />
                )}
                <text x={cx} y={y - 7} textAnchor="middle" fontSize={12} fontWeight={650} fill="var(--color-fg)" className="tabular-nums">
                  {formatInt(d.value)}
                </text>
                <text x={cx} y={baseline + 18} textAnchor="middle" fontSize={12} fontWeight={600} fill="var(--color-fg)">
                  {d.label}
                </text>
                {d.sublabel && (
                  <text x={cx} y={baseline + 33} textAnchor="middle" fontSize={11} fill="var(--color-fg-3)">
                    {d.sublabel}
                  </text>
                )}
              </g>
            )
          })}
        </svg>
      </div>
      <TooltipBubble tip={tip} />
    </div>
  )
}
