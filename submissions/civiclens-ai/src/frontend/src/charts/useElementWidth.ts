import { useLayoutEffect, useRef, useState, type RefObject } from 'react'

/** Measures an element's width (ResizeObserver reports once on observe). Falls back where unavailable (jsdom). */
export function useElementWidth<T extends HTMLElement>(fallback = 320): [RefObject<T | null>, number] {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(fallback)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(() => {
      const w = Math.round(el.getBoundingClientRect().width)
      if (w > 0) setWidth(w)
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])
  return [ref, width]
}
