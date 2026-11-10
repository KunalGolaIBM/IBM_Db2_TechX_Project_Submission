import { ChevronDown, ChevronUp } from 'lucide-react'
import { useState } from 'react'
import type { EvidenceItem } from '../api/schemas'
import { CATEGORY_LABEL } from '../lib/domain'
import { formatDateTime } from '../lib/format'
import { describeEvidenceNote } from '../lib/generator'
import { SeverityDots, SyntheticBadge } from './Badges'
import { EmptyState } from './ui'

export function EvidenceTable({
  items,
  highlightIds,
  emptyHint,
  collapseAfter,
}: {
  items: EvidenceItem[]
  highlightIds?: number[]
  emptyHint?: string
  /**
   * Long lists push everything after them off screen. With this set, only the first N rows are shown until the
   * reader asks for all of them. Hiding a single row would save nothing, so a list is only collapsed when it has
   * at least two rows more than the limit.
   */
  collapseAfter?: number
}) {
  const [expanded, setExpanded] = useState(false)

  if (items.length === 0) {
    return <EmptyState title="No evidence attached yet">{emptyHint}</EmptyState>
  }

  const collapsible = collapseAfter !== undefined && items.length >= collapseAfter + 2
  const visible = collapsible && !expanded ? items.slice(0, collapseAfter) : items

  return (
    <div className="flex flex-col gap-3">
      <div className="@container overflow-x-auto">
        <table className="w-full text-sm" data-testid="evidence-table">
          <caption className="sr-only">Complaints attached to this investigation as evidence</caption>
          <thead>
            <tr className="border-b border-ink-700 text-left text-xs text-fg-2">
              <th scope="col" className="px-2 py-2 font-medium sm:px-3">ID</th>
              <th scope="col" className="px-2 py-2 font-medium sm:px-3">Complaint</th>
              <th scope="col" className="hidden px-3 py-2 font-medium @md:table-cell">Category</th>
              <th scope="col" className="px-2 py-2 font-medium sm:px-3">Severity</th>
              <th scope="col" className="hidden px-3 py-2 font-medium @2xl:table-cell">Cell</th>
              <th scope="col" className="px-2 py-2 font-medium sm:px-3">Reported</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((e) => (
              <tr
                key={e.complaint_id}
                data-testid="evidence-row"
                data-complaint-id={e.complaint_id}
                className={
                  highlightIds?.includes(e.complaint_id)
                    ? 'border-b border-ink-700/60 bg-copper-500/8'
                    : 'border-b border-ink-700/60 last:border-0'
                }
              >
                <td className="px-2 py-2 font-mono text-xs text-fg-2 sm:px-3">#{e.complaint_id}</td>
                <td className="max-w-xs px-2 py-2 sm:px-3">
                  <span className="line-clamp-2 text-fg">{e.title}</span>
                  {e.is_synthetic && <SyntheticBadge className="mt-1" />}
                  {e.note && <span className="mt-0.5 block text-xs text-fg-3">{describeEvidenceNote(e.note)}</span>}
                </td>
                <td className="hidden px-3 py-2 text-fg-2 @md:table-cell">{CATEGORY_LABEL[e.category]}</td>
                <td className="px-2 py-2 sm:px-3">
                  <SeverityDots severity={e.severity} />
                </td>
                <td className="hidden px-3 py-2 font-mono text-xs text-fg-2 @2xl:table-cell">{e.geo_cell}</td>
                <td className="px-2 py-2 text-fg-2 sm:px-3 sm:whitespace-nowrap">{formatDateTime(e.reported_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {collapsible && (
        <div className="flex flex-wrap items-center justify-between gap-2 px-3 text-[13px] text-fg-2" data-testid="evidence-collapse">
          <span aria-live="polite">
            Showing {visible.length} of {items.length} complaints
          </span>
          <button
            type="button"
            aria-expanded={expanded}
            onClick={() => setExpanded((v) => !v)}
            className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 font-medium text-copper-400 hover:text-copper-300"
          >
            {expanded ? (
              <>
                Show fewer <ChevronUp className="size-4" aria-hidden />
              </>
            ) : (
              <>
                Show all {items.length} <ChevronDown className="size-4" aria-hidden />
              </>
            )}
          </button>
        </div>
      )}
    </div>
  )
}
