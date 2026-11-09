import type { Complaint, Hotspot } from '../api/schemas'
import { CATEGORY_LABEL, SEVERITY_LABEL } from '../lib/domain'
import { formatDateTime } from '../lib/format'

/**
 * Tooltip content for map markers. Complaint text is untrusted user input, so it is only ever inserted with
 * `textContent` (never innerHTML): markup in a title is displayed literally and cannot run.
 */
function row(text: string, style: Partial<CSSStyleDeclaration> = {}): HTMLDivElement {
  const el = document.createElement('div')
  el.textContent = text
  Object.assign(el.style, style)
  return el
}

export function complaintTooltip(c: Complaint): HTMLElement {
  const muted = { color: 'var(--color-fg-2)' }
  const root = document.createElement('div')
  root.append(
    row(c.title, { fontWeight: '650' }),
    row(`${CATEGORY_LABEL[c.category]} · severity ${c.severity} (${SEVERITY_LABEL[c.severity] ?? '?'})`, muted),
    row(`#${c.complaint_id} · ${formatDateTime(c.reported_at)}`, muted),
  )
  if (c.is_synthetic) {
    root.append(row('SYNTHETIC demonstration record', { ...muted, letterSpacing: '0.04em', fontSize: '11px' }))
  }
  return root
}

export function hotspotLabel(h: Hotspot): string {
  return `${CATEGORY_LABEL[h.category]} hotspot: ${h.complaint_count} complaints in cell ${h.geo_cell}`
}

export function hotspotTooltip(h: Hotspot): HTMLElement {
  const root = document.createElement('div')
  const title = document.createElement('div')
  title.style.fontWeight = '650'
  title.textContent = `${CATEGORY_LABEL[h.category]} cluster`
  const meta = document.createElement('div')
  meta.style.color = 'var(--color-fg-2)'
  meta.textContent = `${h.complaint_count} complaints · avg severity ${h.avg_severity.toFixed(1)} · cell ${h.geo_cell}`
  root.append(title, meta)
  return root
}
