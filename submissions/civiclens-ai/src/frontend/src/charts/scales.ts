/** Pure helpers for the charts (unit tested). */

/** Round up to 1, 2, 5 x 10^n. */
export function niceCeil(value: number): number {
  if (!(value > 0)) return 1
  const base = 10 ** Math.floor(Math.log10(value))
  const f = value / base
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * base
}

/** Clean axis ticks from 0 up to a "nice" top that contains `max`. Integer steps for count data. */
export function niceScale(max: number, count = 4, integer = true): { top: number; ticks: number[] } {
  const safeMax = max > 0 ? max : 1
  let step = niceCeil(safeMax / count)
  if (integer) step = Math.max(1, step)
  const top = Math.ceil(safeMax / step) * step
  const ticks: number[] = []
  for (let v = 0; v <= top + 1e-9; v += step) ticks.push(Math.round(v * 1e6) / 1e6)
  return { top, ticks }
}

export const clamp = (v: number, lo: number, hi: number): number => Math.min(Math.max(v, lo), hi)

export function linearScale(domain: [number, number], range: [number, number]): (v: number) => number {
  const [d0, d1] = domain
  const [r0, r1] = range
  const span = d1 - d0 || 1
  return (v) => r0 + ((v - d0) / span) * (r1 - r0)
}

/** Index of the entry in `xs` closest to `x`. */
export function nearestIndex(x: number, xs: number[]): number {
  let best = 0
  let bestDist = Infinity
  xs.forEach((value, i) => {
    const d = Math.abs(value - x)
    if (d < bestDist) {
      best = i
      bestDist = d
    }
  })
  return best
}

const lin = (c: number) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)
export function relativeLuminance(hex: string): number {
  const n = hex.replace('#', '')
  const [r, g, b] = [0, 2, 4].map((i) => lin(parseInt(n.slice(i, i + 2), 16) / 255))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}
export function contrastRatio(a: string, b: string): number {
  const [hi, lo] = [relativeLuminance(a), relativeLuminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

/** Label colour inside a coloured fill: whichever of near-black / white reads better. */
export function readableInk(fill: string): '#0b0b0b' | '#ffffff' {
  return contrastRatio('#0b0b0b', fill) >= contrastRatio('#ffffff', fill) ? '#0b0b0b' : '#ffffff'
}

export const share = (part: number, total: number): number => (total > 0 ? part / total : 0)
