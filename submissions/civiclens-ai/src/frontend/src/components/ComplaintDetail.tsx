import type { ReactNode } from 'react'
import type { Complaint } from '../api/schemas'
import { CATEGORY_LABEL } from '../lib/domain'
import { formatDateTime } from '../lib/format'
import { ComplaintStatusBadge, SeverityDots, SyntheticBadge } from './Badges'
import { Chip } from './ui'

/** Full detail of one complaint. All text is rendered through React (escaped); nothing is injected as HTML. */
export function ComplaintDetail({ complaint: c, actions }: { complaint: Complaint; actions?: ReactNode }) {
  return (
    <div data-testid="complaint-detail" data-complaint-id={c.complaint_id}>
      <div className="flex flex-wrap items-center gap-2">
        <Chip>{CATEGORY_LABEL[c.category]}</Chip>
        <ComplaintStatusBadge status={c.status} />
        <SeverityDots severity={c.severity} />
        {c.is_synthetic && <SyntheticBadge />}
      </div>
      <h3 className="mt-3 text-base leading-6 font-semibold text-fg">{c.title}</h3>
      <p className="mt-2 text-sm leading-6 whitespace-pre-wrap text-fg-2">{c.description}</p>
      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
        {[
          ['Complaint ID', `#${c.complaint_id}`],
          ['External ref', c.external_ref ?? '–'],
          ['Ward', c.ward ?? '–'],
          ['Source', c.source],
          ['Reported', formatDateTime(c.reported_at)],
          ['Stored', formatDateTime(c.created_at)],
          ['Coordinates', `${c.latitude.toFixed(5)}, ${c.longitude.toFixed(5)}`],
          ['Geo-cell', c.geo_cell],
          ...(c.duplicate_of ? [['Duplicate of', `#${c.duplicate_of}`]] : []),
        ].map(([k, v]) => (
          <div key={k}>
            <dt className="text-xs text-fg-3">{k}</dt>
            <dd className="mt-0.5 break-words text-fg">{v}</dd>
          </div>
        ))}
      </dl>
      {actions && <div className="mt-5 flex flex-wrap gap-2">{actions}</div>}
    </div>
  )
}
