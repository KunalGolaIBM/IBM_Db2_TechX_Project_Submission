import { useCallback, useRef, useState, type ReactNode } from 'react'
import { clamp } from './scales'

export interface TipState {
  x: number
  y: number
  content: ReactNode
}

/** Pointer + keyboard tooltip state for a chart wrapper (`position: relative`). Tooltips enhance, never gate. */
export function useChartTooltip() {
  const wrapperRef = useRef<HTMLDivElement>(null)
  const [tip, setTip] = useState<TipState | null>(null)

  const place = useCallback((clientX: number, clientY: number, content: ReactNode) => {
    const box = wrapperRef.current?.getBoundingClientRect()
    if (!box) return
    setTip({ x: clamp(clientX - box.left, 72, Math.max(72, box.width - 72)), y: clientY - box.top, content })
  }, [])

  const showAtPointer = useCallback(
    (event: { clientX: number; clientY: number }, content: ReactNode) => place(event.clientX, event.clientY, content),
    [place],
  )
  const showAtElement = useCallback(
    (element: Element, content: ReactNode) => {
      const b = element.getBoundingClientRect()
      place(b.left + b.width / 2, b.top, content)
    },
    [place],
  )
  const hide = useCallback(() => setTip(null), [])
  return { wrapperRef, tip, showAtPointer, showAtElement, hide }
}

export function TooltipBubble({ tip }: { tip: TipState | null }) {
  if (!tip) return null
  return (
    <div
      role="tooltip"
      data-testid="chart-tooltip"
      className="pointer-events-none absolute z-20 w-max max-w-64 rounded-lg border border-ink-600 bg-ink-750 px-3 py-2 text-xs shadow-xl"
      style={{ left: tip.x, top: tip.y, transform: 'translate(-50%, calc(-100% - 10px))' }}
    >
      {tip.content}
    </div>
  )
}

/** Value leads (strong), label follows (secondary); a short line key identifies the series. */
export function TipContent({
  title,
  value,
  detail,
  color,
}: {
  title: string
  value: string
  detail?: string
  color?: string
}) {
  return (
    <div className="flex items-start gap-2">
      {color && <span className="mt-1.5 h-0.5 w-3 shrink-0 rounded-full" style={{ background: color }} aria-hidden />}
      <div>
        <div className="text-sm font-semibold text-fg tabular-nums">{value}</div>
        <div className="text-fg-2">{title}</div>
        {detail && <div className="text-fg-3">{detail}</div>}
      </div>
    </div>
  )
}
