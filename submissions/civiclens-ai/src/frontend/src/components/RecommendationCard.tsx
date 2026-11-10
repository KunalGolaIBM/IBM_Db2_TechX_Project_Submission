import { ChevronDown, ChevronUp, Link2 } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import type { Recommendation, RecommendationListItem } from '../api/schemas'
import { describeGenerator } from '../lib/generator'
import { cn } from '../lib/cn'
import { formatDateTime } from '../lib/format'
import { ConfidenceMeter, GeneratorBadge, PriorityBadge, RecommendationStatusBadge } from './Badges'

const confidenceCaption = (kind: ReturnType<typeof describeGenerator>['kind']): string => {
  switch (kind) {
    case 'llm':
      return 'Model-reported confidence'
    case 'rules':
      return 'Rule-based score (not a model probability)'
    case 'manual':
      return 'Analyst-estimated confidence'
    default:
      return 'Confidence (origin unverified)'
  }
}

/**
 * One recommendation with its provenance, explanation, priority, confidence and cited evidence.
 * The generator badge is always visible: reviewers must always know who or what wrote what they approve.
 */
export function RecommendationCard({
  rec,
  actions,
  className,
  defaultExpanded = false,
}: {
  rec: Recommendation | RecommendationListItem
  actions?: ReactNode
  className?: string
  defaultExpanded?: boolean
}) {
  const [expanded, setExpanded] = useState(defaultExpanded)
  const info = describeGenerator(rec.generator_type, rec.model_name)
  const long = rec.rationale.length > 280
  return (
    <article
      data-testid="recommendation"
      data-recommendation-id={rec.recommendation_id}
      data-status={rec.status}
      data-generator={rec.generator_type}
      className={cn('rounded-xl border border-ink-700 bg-ink-850 p-4', className)}
    >
      <div className="flex flex-wrap items-center gap-2">
        <PriorityBadge priority={rec.priority} />
        <RecommendationStatusBadge status={rec.status} />
        <GeneratorBadge type={rec.generator_type} modelName={rec.model_name} />
        <span className="ml-auto font-mono text-xs text-fg-3">#{rec.recommendation_id}</span>
      </div>

      <h3 className="mt-3 text-[15px] leading-6 font-semibold text-fg" data-testid="recommendation-summary">
        {rec.summary}
      </h3>
      {'investigation_title' in rec && (
        <p className="text-xs text-fg-3">
          From investigation “{rec.investigation_title}” · created by {rec.investigation_created_by}
        </p>
      )}

      <p
        className={cn('mt-2 text-sm leading-6 whitespace-pre-wrap text-fg-2', !expanded && long && 'line-clamp-4')}
        data-testid="recommendation-rationale"
      >
        {rec.rationale}
      </p>
      {long && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          className="mt-1 inline-flex items-center gap-1 text-[13px] font-medium text-copper-400 hover:text-copper-300"
        >
          {expanded ? <ChevronUp className="size-3.5" aria-hidden /> : <ChevronDown className="size-3.5" aria-hidden />}
          {expanded ? 'Show less' : 'Show full explanation'}
        </button>
      )}

      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-[minmax(10rem,14rem)_1fr]">
        <ConfidenceMeter value={rec.confidence} caption={confidenceCaption(info.kind)} />
        <div>
          <p className="flex items-center gap-1.5 text-xs text-fg-2">
            <Link2 className="size-3.5" aria-hidden />
            Evidence ({rec.evidence_ids.length} {rec.evidence_ids.length === 1 ? 'complaint' : 'complaints'})
          </p>
          <ul className="mt-1.5 flex flex-wrap gap-1" aria-label="Cited complaint IDs" data-testid="evidence-ids">
            {rec.evidence_ids.slice(0, 24).map((id) => (
              <li key={id} className="rounded-md border border-ink-600 bg-ink-800 px-1.5 py-0.5 font-mono text-xs text-fg-2">
                #{id}
              </li>
            ))}
            {rec.evidence_ids.length > 24 && <li className="text-xs text-fg-3">+{rec.evidence_ids.length - 24} more</li>}
          </ul>
        </div>
      </div>

      {rec.review && (
        <div className="mt-3 rounded-lg border border-ink-700 bg-ink-800 px-3 py-2 text-[13px] text-fg-2" data-testid="review-outcome">
          <strong className="font-semibold text-fg">{rec.review.decision === 'APPROVED' ? 'Approved' : 'Rejected'}</strong> by{' '}
          <span className="font-medium text-fg">{rec.review.reviewer}</span> · {formatDateTime(rec.review.decided_at)}
          {rec.review.comment && <p className="mt-1 whitespace-pre-wrap text-fg-2">“{rec.review.comment}”</p>}
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs text-fg-3">Proposed {formatDateTime(rec.created_at)}</span>
        {actions}
      </div>
    </article>
  )
}
