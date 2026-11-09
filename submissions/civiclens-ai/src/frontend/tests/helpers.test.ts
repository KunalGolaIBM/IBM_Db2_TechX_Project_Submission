import { describe, expect, it } from 'vitest'
import { clamp, contrastRatio, linearScale, nearestIndex, niceCeil, niceScale, readableInk, share } from '../src/charts/scales'
import { formatCompact, formatDayMonth, formatRelative, parseServerTime, pluralise } from '../src/lib/format'
import { cellBounds, cellCenter, hotspotKey } from '../src/map/geo'
import { complaintTooltip, hotspotTooltip } from '../src/map/popup'
import { LIMITS, isValid, parseIdList, validateComplaint, validateDecision, validateInvestigation, validateRecommendation } from '../src/lib/validation'
import { complaint, hotspot } from './fixtures'

describe('chart scales', () => {
  it('niceCeil rounds up to 1, 2, 5 x 10^n', () => {
    expect([0.3, 1, 1.5, 3, 7, 12, 99, 101].map(niceCeil)).toEqual([0.5, 1, 2, 5, 10, 20, 100, 200])
    expect(niceCeil(0)).toBe(1)
  })

  it('niceScale gives clean integer ticks containing the max', () => {
    expect(niceScale(7)).toEqual({ top: 8, ticks: [0, 2, 4, 6, 8] })
    expect(niceScale(0)).toEqual({ top: 1, ticks: [0, 1] }) // no data: a small, honest axis
    const { top, ticks } = niceScale(1234)
    expect(top).toBeGreaterThanOrEqual(1234)
    expect(ticks[0]).toBe(0)
    expect(ticks.every((t) => Number.isInteger(t))).toBe(true)
  })

  it('linearScale maps a domain onto a range (including an inverted y range)', () => {
    const y = linearScale([0, 10], [100, 0])
    expect([y(0), y(5), y(10)]).toEqual([100, 50, 0])
    expect(linearScale([3, 3], [0, 10])(3)).toBe(0) // a degenerate domain does not divide by zero
  })

  it('nearestIndex snaps a pointer to the closest data position', () => {
    expect(nearestIndex(41, [0, 20, 40, 60])).toBe(2)
    expect(nearestIndex(-100, [0, 20])).toBe(0)
    expect(nearestIndex(500, [0, 20])).toBe(1)
  })

  it('clamp and share behave at the edges', () => {
    expect([clamp(5, 0, 3), clamp(-1, 0, 3), clamp(2, 0, 3)]).toEqual([3, 0, 2])
    expect([share(1, 4), share(1, 0)]).toEqual([0.25, 0])
  })

  it('readableInk picks whichever of near-black/white contrasts more', () => {
    expect(readableInk('#cc7233')).toBe('#0b0b0b')
    expect(readableInk('#104281')).toBe('#ffffff')
    for (const fill of ['#cc7233', '#3987e5', '#199e70', '#9085e9', '#8e95a2']) {
      expect(contrastRatio(readableInk(fill), fill)).toBeGreaterThanOrEqual(3)
    }
  })
})

describe('formatting', () => {
  it('server timestamps are naive UTC and are parsed as UTC', () => {
    expect(parseServerTime('2026-11-09T08:50:58').toISOString()).toBe('2026-11-09T08:50:58.000Z')
    expect(parseServerTime('2026-11-09T08:50:58.245789').toISOString()).toBe('2026-11-09T08:50:58.245Z')
    expect(parseServerTime('2026-11-09T08:50:58+05:30').toISOString()).toBe('2026-11-09T03:20:58.000Z')
    expect(parseServerTime('2026-11-09').toISOString()).toBe('2026-11-09T00:00:00.000Z')
  })

  it('formats relative time and dates', () => {
    const now = Date.parse('2026-11-09T10:00:00Z')
    expect(formatRelative('2026-11-09T09:59:50', now)).toBe('just now')
    expect(formatRelative('2026-11-09T09:30:00', now)).toBe('30 min ago')
    expect(formatRelative('2026-11-09T05:00:00', now)).toBe('5 h ago')
    expect(formatRelative('2026-11-04T10:00:00', now)).toBe('5 d ago')
    expect(formatDayMonth('2026-10-25')).toBe('25 Oct')
  })

  it('pluralises and compacts', () => {
    expect([pluralise(1, 'complaint'), pluralise(2, 'complaint')]).toEqual(['complaint', 'complaints'])
    expect([formatCompact(950), formatCompact(12_900)]).toEqual(['950', '12.9K'])
  })
})

describe('geo-cells', () => {
  it('converts a cell id back to the grid rectangle the backend aggregated', () => {
    expect(cellBounds('C5499_15535')).toEqual([
      [27.495, 77.675],
      [27.5, 77.68],
    ])
    expect(cellCenter('C5499_15535')).toEqual([27.4975, 77.6775])
  })

  it('handles negative cells and rejects malformed ids', () => {
    expect(cellBounds('C-10_-20')).toEqual([
      [-0.05, -0.1],
      [-0.045, -0.095],
    ])
    for (const bad of ['', 'C1', 'X1_2', 'C1_2_3', 'C1.5_2']) expect(cellBounds(bad)).toBeNull()
  })

  it('a hotspot is keyed by cell AND category', () => {
    expect(hotspotKey({ geo_cell: 'C1_2', category: 'POTHOLE' })).toBe('C1_2|POTHOLE')
    expect(hotspotKey({ geo_cell: 'C1_2', category: 'GARBAGE' })).not.toBe(hotspotKey({ geo_cell: 'C1_2', category: 'POTHOLE' }))
  })
})

describe('map tooltips treat complaint text as untrusted (XSS)', () => {
  const evil = '<img src=x onerror="window.__pwned=true"><script>window.__pwned=true</script>'

  it('shows markup in a title literally and creates no elements from it', () => {
    const node = complaintTooltip(complaint({ title: evil }))
    document.body.append(node)
    expect(node.querySelector('img, script')).toBeNull()
    expect(node.textContent).toContain(evil)
    expect((window as unknown as { __pwned?: boolean }).__pwned).toBeUndefined()
    node.remove()
  })

  it('marks synthetic records and omits the marker for real ones', () => {
    expect(complaintTooltip(complaint({ is_synthetic: true })).textContent).toContain('SYNTHETIC demonstration record')
    expect(complaintTooltip(complaint({ is_synthetic: false })).textContent).not.toContain('SYNTHETIC')
  })

  it('hotspot tooltip is plain text as well', () => {
    const node = hotspotTooltip(hotspot())
    expect(node.textContent).toMatch(/Pothole cluster.*9 complaints/)
    expect(node.querySelector('script, img')).toBeNull()
  })
})

describe('form validation mirrors the server limits', () => {
  const base = { title: 'Valid title', description: 'Valid description', latitude: '27.49', longitude: '77.67', ward: '' }

  it('accepts a good complaint and flags each bad field', () => {
    expect(isValid(validateComplaint(base))).toBe(true)
    const errors = validateComplaint({ ...base, title: 'ab', description: '', latitude: '91', longitude: 'east', ward: 'x'.repeat(65) })
    expect(Object.keys(errors).filter((k) => errors[k as keyof typeof errors])).toEqual(['title', 'description', 'latitude', 'longitude', 'ward'])
    expect(validateComplaint({ ...base, latitude: '' }).latitude).toMatch(/required/)
    expect(validateComplaint({ ...base, longitude: '181' }).longitude).toMatch(/between -180 and 180/)
  })

  it('investigation title and question have length limits', () => {
    expect(isValid(validateInvestigation({ title: 'Okay', question: 'A question?' }))).toBe(true)
    expect(validateInvestigation({ title: 'x'.repeat(201), question: 'ok?' }).title).toMatch(/at most 200/)
    expect(validateInvestigation({ title: 'ok', question: 'ab' }).question).toMatch(/at least 3/)
  })

  it('a recommendation needs summary, explanation and evidence', () => {
    expect(isValid(validateRecommendation({ summary: 'Fix it now', rationale: 'Because the evidence shows it.', evidenceIds: [1] }))).toBe(true)
    const e = validateRecommendation({ summary: 'no', rationale: 'short', evidenceIds: [] })
    expect(e.summary && e.rationale && e.evidence).toBeTruthy()
    expect(validateRecommendation({ summary: 'Fix it now', rationale: 'Because the evidence shows it.', evidenceIds: Array.from({ length: LIMITS.maxEvidence + 1 }, (_, i) => i + 1) }).evidence).toMatch(/at most 50/)
  })

  it('rejecting needs a comment; approving does not', () => {
    expect(validateDecision('APPROVED', '')).toBeUndefined()
    expect(validateDecision('REJECTED', '')).toMatch(/required to reject/)
    expect(validateDecision('REJECTED', 'no')).toMatch(/required to reject/)
    expect(validateDecision('REJECTED', 'Not enough evidence')).toBeUndefined()
    expect(validateDecision('APPROVED', 'x'.repeat(2001))).toMatch(/at most 2000/)
  })

  it('parseIdList accepts mixed separators and reports (not drops) invalid tokens', () => {
    expect(parseIdList('12, #15  99;12')).toEqual({ ids: [12, 15, 99], invalid: [] })
    expect(parseIdList('4, abc, -3, 0, 1.5, 99999999999999999999')).toEqual({
      ids: [4],
      invalid: ['abc', '-3', '0', '1.5', '99999999999999999999'],
    })
    expect(parseIdList('  ')).toEqual({ ids: [], invalid: [] })
  })
})
