import { ClipboardCheck, ThumbsDown, ThumbsUp } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useDecideRecommendation, useEvidence, useRecommendationQueue } from '../api/queries'
import type { Me, RecommendationListItem } from '../api/schemas'
import { useAuth, useMe } from '../auth/AuthContext'
import { GeneratorBadge, GeneratorExplanation, PriorityBadge, RecommendationStatusBadge } from '../components/Badges'
import { EvidenceTable } from '../components/EvidenceTable'
import { Modal } from '../components/Modal'
import { ErrorNotice, InfoNotice, SuccessNotice } from '../components/Notices'
import { RecommendationCard } from '../components/RecommendationCard'
import { Button, Card, CardBody, CardHeader, EmptyState, LoadingBlock, PageHeader, TextArea, ToggleChip } from '../components/ui'
import { cn } from '../lib/cn'
import { formatRelative } from '../lib/format'
import { validateDecision } from '../lib/validation'

type Filter = 'PROPOSED' | 'APPROVED' | 'REJECTED' | 'all'
const FILTERS: Array<{ value: Filter; label: string }> = [
  { value: 'PROPOSED', label: 'Awaiting review' },
  { value: 'APPROVED', label: 'Approved' },
  { value: 'REJECTED', label: 'Rejected' },
  { value: 'all', label: 'All' },
]

type Outcome = { kind: 'success'; text: string } | { kind: 'error'; error: unknown } | null

export function ReviewView() {
  const { can } = useAuth()
  const me = useMe()
  const [filter, setFilter] = useState<Filter>('PROPOSED')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [outcome, setOutcome] = useState<Outcome>(null)
  const outcomeRef = useRef<HTMLDivElement>(null)
  const q = useRecommendationQueue({ status: filter === 'all' ? undefined : filter, limit: 100 })
  const decide = useDecideRecommendation()

  // The decision buttons sit at the bottom of a long panel, but the result appears at the top of the page. Without this the
  // reviewer would click "Confirm" and see nothing happen (found in the real-browser screenshots).
  useEffect(() => {
    if (!outcome) return
    outcomeRef.current?.scrollIntoView({ block: 'start' })
    outcomeRef.current?.focus({ preventScroll: true })
  }, [outcome])

  const items = q.data ?? []
  const selected = items.find((i) => i.recommendation_id === selectedId) ?? items[0] ?? null

  function onDecide(rec: RecommendationListItem, decision: 'APPROVED' | 'REJECTED', comment: string) {
    setOutcome(null)
    decide.mutate(
      { id: rec.recommendation_id, decision, comment: comment.trim() || null },
      {
        onSuccess: () =>
          setOutcome({
            kind: 'success',
            text: `Recommendation #${rec.recommendation_id} ${decision === 'APPROVED' ? 'approved' : 'rejected'}. The decision, your identity and the time are recorded in the audit log.`,
          }),
        onError: (error) => setOutcome({ kind: 'error', error }),
      },
    )
  }

  return (
    <div className="flex flex-col gap-5" data-testid="review-view">
      <PageHeader
        title="Human review"
        description="Every recommendation is only a proposal. A reviewer reads the explanation and the evidence, then approves or rejects it. Nobody reviews their own investigation."
      />

      {!can('recommendation:decide') && (
        <InfoNotice title={`You are signed in as ${me.user_id} (${me.role})`}>
          Only reviewers can approve or reject. You can read the queue and the evidence behind each recommendation.
        </InfoNotice>
      )}
      {outcome && (
        <div ref={outcomeRef} tabIndex={-1} className="scroll-mt-20 outline-none" data-testid="decision-outcome">
          {outcome.kind === 'success' ? (
            <SuccessNotice title="Decision recorded" onDismiss={() => setOutcome(null)}>{outcome.text}</SuccessNotice>
          ) : (
            <ErrorNotice error={outcome.error} onDismiss={() => setOutcome(null)} />
          )}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filter by decision status">
        {FILTERS.map((f) => (
          <ToggleChip key={f.value} pressed={filter === f.value} onToggle={() => (setFilter(f.value), setSelectedId(null))}>
            {f.label}
          </ToggleChip>
        ))}
      </div>

      {q.isPending ? (
        <LoadingBlock label="Loading the review queue" className="min-h-72" />
      ) : !q.data ? (
        <ErrorNotice error={q.error} onRetry={() => void q.refetch()} />
      ) : items.length === 0 ? (
        <Card>
          <EmptyState icon={<ClipboardCheck />} title={filter === 'PROPOSED' ? 'Nothing is waiting for review' : 'No recommendations match this filter'}>
            {filter === 'PROPOSED' ? (
              <>
                New proposals appear here after an analyst runs an investigation.{' '}
                <Link to="/investigations" className="font-medium text-copper-400 hover:text-copper-300">
                  Go to investigations
                </Link>
                .
              </>
            ) : (
              'Choose another filter.'
            )}
          </EmptyState>
        </Card>
      ) : (
        <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[minmax(300px,380px)_minmax(0,1fr)]">
          <ul className="flex flex-col gap-2" aria-label="Recommendations" data-testid="review-queue">
            {items.map((rec) => (
              <li key={rec.recommendation_id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(rec.recommendation_id)}
                  aria-pressed={selected?.recommendation_id === rec.recommendation_id}
                  data-testid="queue-item"
                  data-recommendation-id={rec.recommendation_id}
                  data-status={rec.status}
                  className={cn(
                    'flex w-full flex-col gap-2 rounded-xl border p-3.5 text-left transition-colors',
                    selected?.recommendation_id === rec.recommendation_id
                      ? 'border-copper-400 bg-copper-500/10'
                      : 'border-ink-700 bg-ink-800 hover:border-ink-600',
                  )}
                >
                  <span className="flex flex-wrap items-center gap-2">
                    <PriorityBadge priority={rec.priority} />
                    {(filter === 'all' || rec.status !== 'PROPOSED') && <RecommendationStatusBadge status={rec.status} />}
                    <GeneratorBadge type={rec.generator_type} modelName={rec.model_name} />
                  </span>
                  <span className="line-clamp-2 text-sm font-medium text-fg">{rec.summary}</span>
                  <span className="flex flex-wrap items-center justify-between gap-x-3 text-xs text-fg-3">
                    <span className="line-clamp-1">{rec.investigation_title}</span>
                    <span className="whitespace-nowrap">
                      {rec.evidence_ids.length} evidence · {formatRelative(rec.created_at)}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>

          {selected && (
            <DetailPanel
              key={selected.recommendation_id}
              rec={selected}
              me={me}
              canDecide={can('recommendation:decide')}
              pending={decide.isPending}
              onDecide={onDecide}
            />
          )}
        </div>
      )}
    </div>
  )
}

function DetailPanel({
  rec,
  me,
  canDecide,
  pending,
  onDecide,
}: {
  rec: RecommendationListItem
  me: Me
  canDecide: boolean
  pending: boolean
  onDecide: (rec: RecommendationListItem, decision: 'APPROVED' | 'REJECTED', comment: string) => void
}) {
  const evidenceQ = useEvidence(rec.investigation_id)
  const [comment, setComment] = useState('')
  const [fieldError, setFieldError] = useState<string | null>(null)
  const [confirm, setConfirm] = useState<'APPROVED' | 'REJECTED' | null>(null)
  const cited = evidenceQ.data?.filter((e) => rec.evidence_ids.includes(e.complaint_id)) ?? []
  const selfReview = rec.investigation_created_by === me.user_id
  const decidable = canDecide && rec.status === 'PROPOSED'

  function begin(decision: 'APPROVED' | 'REJECTED') {
    const error = validateDecision(decision, comment) ?? null
    setFieldError(error)
    if (!error) setConfirm(decision)
  }

  return (
    <div className="flex min-w-0 flex-col gap-4" data-testid="review-detail" data-recommendation-id={rec.recommendation_id}>
      <RecommendationCard rec={rec} defaultExpanded />
      <GeneratorExplanation type={rec.generator_type} modelName={rec.model_name} />

      <Card>
        <CardHeader title="Evidence behind this recommendation" subtitle={`${cited.length} of ${rec.evidence_ids.length} cited complaints shown`} />
        <CardBody>
          {evidenceQ.isPending ? (
            <LoadingBlock label="Loading evidence" />
          ) : evidenceQ.isError ? (
            <ErrorNotice error={evidenceQ.error} onRetry={() => void evidenceQ.refetch()} />
          ) : (
            <EvidenceTable items={cited} />
          )}
        </CardBody>
      </Card>

      {decidable ? (
        <Card data-testid="decision-panel">
          <CardHeader title="Your decision" subtitle={`You are acting as ${me.user_id}. The decision is permanent and appears in the audit log.`} />
          <CardBody className="flex flex-col gap-4">
            {selfReview && (
              <InfoNotice title="You created this investigation">
                The four-eyes rule will refuse your decision. Ask another reviewer.
              </InfoNotice>
            )}
            <TextArea
              label="Comment"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              error={fieldError}
              hint="Optional when approving. Required when rejecting."
              data-testid="decision-comment"
            />
            <div className="flex flex-wrap gap-3">
              <Button variant="primary" size="lg" disabled={pending || selfReview} onClick={() => begin('APPROVED')} icon={<ThumbsUp className="size-4" aria-hidden />}>
                Approve
              </Button>
              <Button variant="danger" size="lg" disabled={pending || selfReview} onClick={() => begin('REJECTED')} icon={<ThumbsDown className="size-4" aria-hidden />}>
                Reject
              </Button>
            </div>
          </CardBody>
        </Card>
      ) : (
        rec.status === 'PROPOSED' && (
          <InfoNotice>Decision controls are only shown to reviewers.</InfoNotice>
        )
      )}

      <Modal
        open={confirm !== null}
        onClose={() => setConfirm(null)}
        title={`${confirm === 'APPROVED' ? 'Approve' : 'Reject'} recommendation #${rec.recommendation_id}?`}
        footer={
          <>
            <Button onClick={() => setConfirm(null)}>Cancel</Button>
            <Button
              variant={confirm === 'APPROVED' ? 'primary' : 'danger'}
              data-autofocus
              onClick={() => {
                const decision = confirm
                setConfirm(null)
                if (decision) onDecide(rec, decision, comment)
              }}
            >
              Confirm {confirm === 'APPROVED' ? 'approval' : 'rejection'}
            </Button>
          </>
        }
      >
        <p className="text-sm leading-6 text-fg-2">
          “{rec.summary}”
        </p>
        <p className="mt-3 text-[13px] leading-5 text-fg-2">
          You are acting as <strong className="text-fg">{me.user_id}</strong> (reviewer). This is recorded permanently with your
          identity and cannot be changed afterwards.
        </p>
      </Modal>
    </div>
  )
}
