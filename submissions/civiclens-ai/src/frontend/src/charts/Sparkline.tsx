import { useElementWidth } from './useElementWidth'

const H = 40

/** 12+ point trend in the de-emphasis ink, with the most recent days in the accent and a ringed end marker. */
export function Sparkline({ values, recent = 7, ariaLabel }: { values: number[]; recent?: number; ariaLabel: string }) {
  const [ref, width] = useElementWidth<HTMLDivElement>(240)
  if (values.length < 2) return null
  const max = Math.max(...values, 1)
  const pad = 6
  const x = (i: number) => pad + (i * (width - pad * 2)) / (values.length - 1)
  const y = (v: number) => H - pad - (v / max) * (H - pad * 2)
  const path = (from: number, to: number) =>
    values
      .slice(from, to + 1)
      .map((v, k) => `${k === 0 ? 'M' : 'L'}${x(from + k).toFixed(1)},${y(v).toFixed(1)}`)
      .join(' ')
  const split = Math.max(values.length - recent, 0)
  const last = values.length - 1
  return (
    <div ref={ref} className="w-full">
      <svg width={width} height={H} role="img" aria-label={ariaLabel} className="block">
        <path d={path(0, split)} fill="none" stroke="var(--color-fg-3)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        <path d={path(split, last)} fill="none" stroke="var(--color-series-1)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        <circle cx={x(last)} cy={y(values[last])} r={4} fill="var(--color-series-1)" stroke="var(--color-ink-800)" strokeWidth={2} />
      </svg>
    </div>
  )
}
