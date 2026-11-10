/** Server timestamps are naive UTC strings ("2026-11-09T08:50:58.245789"); treat them as UTC. */
export function parseServerTime(value: string): Date {
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return new Date(`${value}T00:00:00Z`)
  const trimmed = value.replace(/(\.\d{3})\d+/, '$1') // JS dates are millisecond precision
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(trimmed)
  return new Date(hasZone ? trimmed : `${trimmed}Z`)
}

const dateTime = new Intl.DateTimeFormat('en-GB', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})
const dateOnly = new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
const dayMonth = new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', timeZone: 'UTC' })
const timeOnly = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
const integer = new Intl.NumberFormat('en-US')

export const formatDateTime = (value: string): string => dateTime.format(parseServerTime(value))
export const formatDate = (value: string): string => dateOnly.format(parseServerTime(value))
export const formatDayMonth = (value: string): string => dayMonth.format(parseServerTime(value))
export const formatClock = (value: string | Date): string =>
  timeOnly.format(typeof value === 'string' ? parseServerTime(value) : value)
export const formatInt = (value: number): string => integer.format(value)
export const formatPercent = (fraction: number, digits = 0): string => `${(fraction * 100).toFixed(digits)}%`

/** "3 min ago" / "2 h ago" / "5 d ago" */
export function formatRelative(value: string, now: number = Date.now()): string {
  const seconds = Math.max(0, Math.round((now - parseServerTime(value).getTime()) / 1000))
  if (seconds < 45) return 'just now'
  if (seconds < 3600) return `${Math.round(seconds / 60)} min ago`
  if (seconds < 86_400) return `${Math.round(seconds / 3600)} h ago`
  return `${Math.round(seconds / 86_400)} d ago`
}

export const pluralise = (n: number, one: string, many = `${one}s`): string => (n === 1 ? one : many)

/** Compact axis/tile numbers: 1,284 / 12.9K */
export function formatCompact(value: number): string {
  if (Math.abs(value) < 10_000) return integer.format(value)
  return new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(value)
}
