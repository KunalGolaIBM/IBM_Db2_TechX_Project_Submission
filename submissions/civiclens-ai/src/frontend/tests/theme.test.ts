import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { contrastRatio } from '../src/charts/scales'
import { GENERATOR_COLOR, GENERATOR_TYPES, SERIES_COLORS, SEVERITY_COLORS } from '../src/lib/domain'

const css = readFileSync(join(__dirname, '../src/index.css'), 'utf8')
const token = (name: string): string => {
  const m = new RegExp(`--color-${name}:\\s*(#[0-9a-fA-F]{6})`).exec(css)
  if (!m) throw new Error(`token --color-${name} not found in index.css`)
  return m[1].toLowerCase()
}

describe('theme tokens stay in sync with the validated chart palette', () => {
  // These exact values were run through the dataviz palette validator (docs/evidence/palette_validation.txt).
  // Changing one is allowed, but only together with a fresh validator run: that is what this test enforces.
  it('categorical series are the validated set, in the validated order', () => {
    expect([1, 2, 3, 4].map((i) => token(`series-${i}`))).toEqual(['#cc7233', '#3987e5', '#199e70', '#9085e9'])
    expect(Object.values(SERIES_COLORS)).toEqual([1, 2, 3, 4].map((i) => token(`series-${i}`)))
  })

  it('the severity ramp in TypeScript equals the CSS tokens (SVG/Leaflet cannot read CSS variables)', () => {
    expect([1, 2, 3, 4, 5].map((i) => token(`sev-${i}`))).toEqual([...SEVERITY_COLORS])
  })

  it('severity ramp is monotone in lightness (more severe = lighter)', () => {
    const lum = (hex: string) => contrastRatio(hex, '#000000')
    const values = SEVERITY_COLORS.map(lum)
    expect(values).toEqual([...values].sort((a, b) => a - b))
  })

  it('each generator keeps its own series hue everywhere (colour follows the entity)', () => {
    expect(GENERATOR_COLOR.LLM).toBe(token('series-1'))
    expect(GENERATOR_COLOR.DETERMINISTIC_FALLBACK).toBe(token('series-2'))
    expect(GENERATOR_COLOR.MANUAL).toBe(token('series-3'))
    expect(new Set(GENERATOR_TYPES.map((g) => GENERATOR_COLOR[g])).size).toBe(GENERATOR_TYPES.length)
  })
})

describe('text and mark contrast (WCAG)', () => {
  const surfaces = ['ink-950', 'ink-900', 'ink-850', 'ink-800', 'ink-750'].map(token)

  it.each(['fg', 'fg-2', 'fg-3'])('body text token %s reaches 4.5:1 on every surface', (name) => {
    for (const surface of surfaces) expect(contrastRatio(token(name), surface)).toBeGreaterThanOrEqual(4.5)
  })

  it('copper-400 (link/accent text) reaches 4.5:1 on every surface', () => {
    for (const surface of surfaces) expect(contrastRatio(token('copper-400'), surface)).toBeGreaterThanOrEqual(4.5)
  })

  it('primary buttons use dark ink on copper, which is legible (light ink would not be)', () => {
    expect(contrastRatio(token('ink-950'), token('copper-400'))).toBeGreaterThanOrEqual(4.5)
    expect(contrastRatio(token('fg'), token('copper-400'))).toBeLessThan(4.5)
  })

  it('categorical series and status colours reach 3:1 on the panel surface', () => {
    const panel = token('ink-800')
    for (const name of ['series-1', 'series-2', 'series-3', 'series-4', 'good', 'warn', 'critical']) {
      expect(contrastRatio(token(name), panel), name).toBeGreaterThanOrEqual(3)
    }
  })

  it('every severity step reaches the ordinal-ramp floor of 2:1 (severity is also shown by dot count, size and labels)', () => {
    const panel = token('ink-800')
    for (let i = 1; i <= 5; i++) expect(contrastRatio(token(`sev-${i}`), panel), `sev-${i}`).toBeGreaterThanOrEqual(2)
  })
})
