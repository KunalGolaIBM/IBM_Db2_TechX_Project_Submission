import { useState, type KeyboardEvent, type PointerEvent } from 'react'
import { formatDayMonth, formatInt } from '../lib/format'
import { linearScale, nearestIndex, niceScale } from './scales'
import { TipContent, TooltipBubble, useChartTooltip } from './Tooltip'
import { useElementWidth } from './useElementWidth'

export interface TrendPoint {
  date: string
  count: number
}

const HEIGHT = 208
const M = { top: 14, right: 18, bottom: 30, left: 34 }
const COLOR = 'var(--color-series-1)'

/**
 * Single-series daily trend: 2px line with a 10% wash, a >=8px end marker with a 2px surface ring,
 * hairline solid grid, a crosshair that snaps to the nearest day, and keyboard stepping with the arrow keys.
 */
export function TrendChart({
  points,
  ariaLabel,
  valueNoun = 'new complaints',
}: {
  points: TrendPoint[]
  ariaLabel: string
  valueNoun?: string
}) {
  const [boxRef, width] = useElementWidth<HTMLDivElement>()
  const { wrapperRef, tip, showAtPointer, hide } = useChartTooltip()
  const [active, setActive] = useState<number | null>(null)

  const n = points.length
  const innerW = Math.max(width - M.left - M.right, 10)
  const innerH = HEIGHT - M.top - M.bottom
  const { top: yTop, ticks } = niceScale(Math.max(...points.map((p) => p.count), 1), 4)
  const x = linearScale([0, Math.max(n - 1, 1)], [M.left, M.left + innerW])
  const y = linearScale([0, yTop], [M.top + innerH, M.top])
  const xs = points.map((_, i) => x(i))
  const baseY = M.top + innerH

  if (n === 0) return null
  const line = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(p.count).toFixed(1)}`).join(' ')
  const area = `${line} L${x(n - 1).toFixed(1)},${baseY} L${x(0).toFixed(1)},${baseY} Z`
  const peak = points.reduce((best, p, i) => (p.count > points[best].count ? i : best), 0)

  const tipFor = (i: number) => (
    <TipContent
      title={formatDayMonth(points[i].date)}
      value={`${formatInt(points[i].count)} ${valueNoun}`}
      color={COLOR}
    />
  )
  const move = (event: PointerEvent<SVGRectElement>) => {
    const box = event.currentTarget.getBoundingClientRect()
    const i = nearestIndex(event.clientX - box.left + M.left, xs)
    setActive(i)
    showAtPointer({ clientX: box.left + xs[i] - M.left, clientY: box.top + y(points[i].count) - M.top }, tipFor(i))
  }
  const key = (event: KeyboardEvent<SVGSVGElement>) => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight' && event.key !== 'Home' && event.key !== 'End') return
    event.preventDefault()
    const next =
      event.key === 'Home' ? 0 : event.key === 'End' ? n - 1 : Math.min(Math.max((active ?? n - 1) + (event.key === 'ArrowRight' ? 1 : -1), 0), n - 1)
    setActive(next)
    const svg = event.currentTarget.getBoundingClientRect()
    showAtPointer({ clientX: svg.left + xs[next], clientY: svg.top + y(points[next].count) }, tipFor(next))
  }

  return (
    <div ref={wrapperRef} className="relative" data-testid="trend-chart">
      <div ref={boxRef}>
        <svg
          width={width}
          height={HEIGHT}
          tabIndex={0}
          role="img"
          aria-label={`${ariaLabel} Peak: ${points[peak].count} on ${formatDayMonth(points[peak].date)}. Use the arrow keys to step through days.`}
          onKeyDown={key}
          onBlur={() => {
            setActive(null)
            hide()
          }}
          className="block overflow-visible rounded-md outline-none focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-copper-300"
        >
          {ticks.map((t) => (
            <g key={t}>
              <line x1={M.left} x2={M.left + innerW} y1={y(t)} y2={y(t)} stroke="var(--color-ink-700)" strokeWidth={1} />
              <text x={M.left - 8} y={y(t) + 4} textAnchor="end" fontSize={11} fill="var(--color-fg-3)" className="tabular-nums">
                {t}
              </text>
            </g>
          ))}
          {[0, Math.floor((n - 1) / 2), n - 1].map((i) => (
            <text
              key={i}
              x={x(i)}
              y={HEIGHT - 8}
              textAnchor={i === 0 ? 'start' : i === n - 1 ? 'end' : 'middle'}
              fontSize={11}
              fill="var(--color-fg-3)"
            >
              {formatDayMonth(points[i].date)}
            </text>
          ))}
          <path d={area} fill={COLOR} fillOpacity={0.1} />
          <path d={line} fill="none" stroke={COLOR} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
          {active !== null && (
            <line x1={xs[active]} x2={xs[active]} y1={M.top} y2={baseY} stroke="var(--color-fg-3)" strokeWidth={1} />
          )}
          {/* end marker (and the hovered point) carry a 2px ring in the surface colour */}
          {[n - 1, ...(active !== null && active !== n - 1 ? [active] : [])].map((i) => (
            <circle
              key={i}
              cx={x(i)}
              cy={y(points[i].count)}
              r={4.5}
              fill={COLOR}
              stroke="var(--color-ink-800)"
              strokeWidth={2}
            />
          ))}
          <rect
            x={M.left}
            y={M.top}
            width={innerW}
            height={innerH}
            fill="transparent"
            onPointerMove={move}
            onPointerLeave={() => {
              setActive(null)
              hide()
            }}
          />
        </svg>
      </div>
      <TooltipBubble tip={tip} />
    </div>
  )
}
