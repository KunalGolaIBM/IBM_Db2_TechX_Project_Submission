import { ArrowLeft, Link2, ListPlus, Play, Plus } from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  useAttachEvidence,
  useAudit,
  useComplaints,
  useEvidence,
  useInvestigation,
  useInvestigationRecommendations,
  useOverview,
  useProposeRecommendation,
  useRunInvestigation,
} from '../api/queries'
import type { EvidenceItem, Investigation, RunResult } from '../api/schemas'
import { useAuth } from '../auth/AuthContext'
import { GeneratorExplanation, InvestigationStatusBadge, SeverityDots, SyntheticBadge } from '../components/Badges'
import { AuditTimeline } from '../components/AuditTimeline'
import { EvidenceTable } from '../components/EvidenceTable'
import { Modal } from '../components/Modal'
import { ErrorNotice, InfoNotice, SuccessNotice } from '../components/Notices'
import { RecommendationCard } from '../components/RecommendationCard'
import { StepTracker } from '../components/StepTracker'
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  Chip,
  EmptyState,
  LoadingBlock,
  SelectInput,
  TextArea,
  TextInput,
} from '../components/ui'
import { cn } from '../lib/cn'
import { CATEGORIES, CATEGORY_LABEL, PRIORITY_LABEL, type Category } from '../lib/domain'
import { formatDateTime, pluralise } from '../lib/format'
import { isValid, parseIdList, validateRecommendation } from '../lib/validation'
import { NotFoundView } from './NotFoundView'

export function InvestigationDetailView() {
  const { id: raw } = useParams()
  const id = Number(raw)
  if (!Number.isInteger(id) || id < 1) return <NotFoundView />
  return <Workspace id={id} />
}

function Workspace({ id }: { id: number }) {
  const { can } = useAuth()
  const invQ = useInvestigation(id)
  const evidenceQ = useEvidence(id)
  const recsQ = useInvestigationRecommendations(id)
  const auditQ = useAudit(id)
  const [flash, setFlash] = useState<string | null>(null)
  const [picking, setPicking] = useState(false)
  const [proposing, setProposing] = useState(false)

  if (invQ.isPending) return <LoadingBlock label="Loading the investigation" className="min-h-96" />
  if (!invQ.data) {
    return (
      <div className="flex flex-col gap-4">
        <BackLink />
        <ErrorNotice error={invQ.error} onRetry={() => void invQ.refetch()} />
      </div>
    )
  }
  const inv = invQ.data
  const evidence = evidenceQ.data ?? []
  const closed = inv.status === 'CLOSED'

  return (
    <div className="flex flex-col gap-5" data-testid="workspace" data-investigation-id={id}>
      <BackLink />
      <Header inv={inv} />
      {flash && <SuccessNotice title={flash} onDismiss={() => setFlash(null)} />}

      <div className="grid grid-cols-1 items-start gap-5 xl:grid-cols-[minmax(0,1.65fr)_minmax(0,1fr)]">
        <div className="flex min-w-0 flex-col gap-5">
          <Card data-testid="evidence-card">
            <CardHeader
              title="Evidence"
              subtitle="Complaints attached to this investigation. Recommendations may only cite attached evidence."
              actions={
                can('evidence:attach') && !closed ? (
                  <Button size="sm" onClick={() => setPicking(true)} icon={<ListPlus className="size-4" aria-hidden />}>
                    Attach evidence
                  </Button>
                ) : undefined
              }
            />
            <CardBody className="flex flex-col gap-4">
              {evidenceQ.isPending ? (
                <LoadingBlock label="Loading evidence" />
              ) : evidenceQ.isError ? (
                <ErrorNotice error={evidenceQ.error} onRetry={() => void evidenceQ.refetch()} />
              ) : (
                <EvidenceTable items={evidence} collapseAfter={8} emptyHint="Attach complaints yourself, or let the investigator choose and cite its own." />
              )}
              {can('evidence:attach') && !closed && <AttachById id={id} onAttached={(n) => setFlash(`Attached ${n} ${pluralise(n, 'complaint')} as evidence.`)} />}
            </CardBody>
          </Card>

          <RunCard inv={inv} onRan={(r) => setFlash(`Run finished: ${r.recommendation_ids.length} ${pluralise(r.recommendation_ids.length, 'recommendation')} proposed.`)} />

          <Card data-testid="recommendations-card">
            <CardHeader
              title="Recommendations"
              subtitle="Each one shows who or what produced it. All start as proposals that a reviewer must decide."
              actions={
                can('recommendation:propose') && !closed ? (
                  <Button size="sm" onClick={() => setProposing(true)} icon={<Plus className="size-4" aria-hidden />}>
                    Propose manually
                  </Button>
                ) : undefined
              }
            />
            <CardBody className="flex flex-col gap-3">
              {recsQ.isPending ? (
                <LoadingBlock label="Loading recommendations" />
              ) : recsQ.isError ? (
                <ErrorNotice error={recsQ.error} onRetry={() => void recsQ.refetch()} />
              ) : recsQ.data.length === 0 ? (
                <EmptyState title="No recommendations yet">
                  Run the investigation, or propose one manually from the evidence above.
                </EmptyState>
              ) : (
                recsQ.data.map((rec) => <RecommendationCard key={rec.recommendation_id} rec={rec} />)
              )}
              {recsQ.data?.some((r) => r.status === 'PROPOSED') && (
                <p className="text-[13px] text-fg-2">
                  Decisions are made by reviewers in{' '}
                  <Link to="/review" className="font-medium text-copper-400 hover:text-copper-300">
                    Human review
                  </Link>
                  .
                </p>
              )}
            </CardBody>
          </Card>
        </div>

        <Card className="min-w-0 xl:sticky xl:top-20" data-testid="audit-card">
          <CardHeader title="Tool activity and audit history" subtitle="Every action on this investigation, in order, from the audit log." />
          <CardBody>
            {auditQ.isPending ? (
              <LoadingBlock label="Loading audit history" />
            ) : auditQ.isError ? (
              <ErrorNotice error={auditQ.error} onRetry={() => void auditQ.refetch()} />
            ) : (
              <AuditTimeline entries={auditQ.data} />
            )}
          </CardBody>
        </Card>
      </div>

      {picking && (
        <EvidencePicker
          id={id}
          attached={evidence}
          onClose={() => setPicking(false)}
          onAttached={(n) => {
            setPicking(false)
            setFlash(`Attached ${n} ${pluralise(n, 'complaint')} as evidence.`)
          }}
        />
      )}
      {proposing && (
        <ProposalModal
          id={id}
          evidence={evidence}
          onClose={() => setProposing(false)}
          onCreated={() => {
            setProposing(false)
            setFlash('Manual recommendation proposed. It is awaiting review.')
          }}
        />
      )}
    </div>
  )
}

const BackLink = () => (
  <Link to="/investigations" className="inline-flex w-fit items-center gap-1.5 text-[13px] font-medium text-fg-2 hover:text-fg">
    <ArrowLeft className="size-4" aria-hidden />
    All investigations
  </Link>
)

function Header({ inv }: { inv: Investigation }) {
  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-mono text-xs text-fg-3">Investigation #{inv.investigation_id}</p>
          <h1 className="mt-1 text-2xl leading-8 font-semibold tracking-tight text-fg" data-testid="investigation-title">
            {inv.title}
          </h1>
        </div>
        <InvestigationStatusBadge status={inv.status} />
      </div>
      <blockquote className="mt-3 max-w-3xl border-l-2 border-copper-500/70 pl-4 text-sm leading-6 text-fg-2">{inv.question}</blockquote>
      <p className="mt-3 text-[13px] text-fg-3">
        Created by <span className="font-medium text-fg-2">{inv.created_by}</span> · {formatDateTime(inv.created_at)}
        {inv.closed_at && <> · closed {formatDateTime(inv.closed_at)}</>}
      </p>
      <div className="mt-4 border-t border-ink-700 pt-4">
        <StepTracker status={inv.status} />
      </div>
    </Card>
  )
}

// ---------------------------------------------------------------------------------------------------
function AttachById({ id, onAttached }: { id: number; onAttached: (count: number) => void }) {
  const attach = useAttachEvidence(id)
  const [text, setText] = useState('')
  const [local, setLocal] = useState<string | null>(null)

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    const { ids, invalid } = parseIdList(text)
    if (invalid.length > 0) return setLocal(`Not a valid complaint ID: ${invalid.join(', ')}`)
    if (ids.length === 0) return setLocal('Enter at least one complaint ID.')
    if (ids.length > 50) return setLocal('Attach at most 50 complaints at a time.')
    setLocal(null)
    attach.mutate({ complaint_ids: ids }, { onSuccess: () => (setText(''), onAttached(ids.length)) })
  }

  return (
    <form onSubmit={onSubmit} noValidate className="border-t border-ink-700 pt-4" data-testid="attach-by-id">
      <div className="flex flex-wrap items-end gap-3">
        <TextInput
          label="Attach by complaint ID"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="e.g. 12, 15, 21"
          error={local}
          hint="Comma or space separated. The server checks that each complaint exists."
          className="min-w-64 flex-1"
        />
        <Button type="submit" loading={attach.isPending} icon={<Link2 className="size-4" aria-hidden />}>
          Attach
        </Button>
      </div>
      {attach.isError && <ErrorNotice className="mt-3" error={attach.error} onDismiss={() => attach.reset()} />}
    </form>
  )
}

function EvidencePicker({
  id,
  attached,
  onClose,
  onAttached,
}: {
  id: number
  attached: EvidenceItem[]
  onClose: () => void
  onAttached: (count: number) => void
}) {
  const complaintsQ = useComplaints({ limit: 200 })
  const attach = useAttachEvidence(id)
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState<'all' | Category>('all')
  const [picked, setPicked] = useState<Set<number>>(new Set())
  const attachedIds = useMemo(() => new Set(attached.map((e) => e.complaint_id)), [attached])

  const rows = (complaintsQ.data ?? []).filter(
    (c) =>
      (category === 'all' || c.category === category) &&
      (!search.trim() ||
        c.title.toLowerCase().includes(search.trim().toLowerCase()) ||
        String(c.complaint_id) === search.trim().replace(/^#/, '')),
  )
  const toggle = (cid: number) =>
    setPicked((prev) => {
      const next = new Set(prev)
      if (next.has(cid)) next.delete(cid)
      else next.add(cid)
      return next
    })

  return (
    <Modal
      open
      onClose={onClose}
      title="Attach evidence"
      size="xl"
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            variant="primary"
            disabled={picked.size === 0}
            loading={attach.isPending}
            onClick={() => attach.mutate({ complaint_ids: [...picked] }, { onSuccess: () => onAttached(picked.size) })}
          >
            Attach {picked.size > 0 ? picked.size : ''} selected
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {attach.isError && <ErrorNotice error={attach.error} />}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_14rem]">
          <TextInput label="Search" type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Title or #ID" data-autofocus />
          <SelectInput label="Category" value={category} onChange={(e) => setCategory(e.target.value as 'all' | Category)}>
            <option value="all">All categories</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>{CATEGORY_LABEL[c]}</option>
            ))}
          </SelectInput>
        </div>
        {complaintsQ.isPending ? (
          <LoadingBlock label="Loading complaints" />
        ) : complaintsQ.isError ? (
          <ErrorNotice error={complaintsQ.error} onRetry={() => void complaintsQ.refetch()} />
        ) : (
          <ul className="max-h-[46dvh] divide-y divide-ink-700/70 overflow-y-auto rounded-lg border border-ink-700" data-testid="picker-list">
            {rows.length === 0 && <li className="p-4 text-sm text-fg-2">No complaints match.</li>}
            {rows.map((c) => {
              const already = attachedIds.has(c.complaint_id)
              return (
                <li key={c.complaint_id}>
                  <label
                    className={cn(
                      'flex cursor-pointer items-start gap-3 px-3 py-2.5 hover:bg-ink-750/60',
                      already && 'cursor-not-allowed opacity-60',
                    )}
                  >
                    <input
                      type="checkbox"
                      className="mt-1 size-4 accent-copper-400"
                      disabled={already}
                      checked={already || picked.has(c.complaint_id)}
                      onChange={() => toggle(c.complaint_id)}
                      aria-label={`Select complaint ${c.complaint_id}: ${c.title}`}
                      data-testid="picker-checkbox"
                      data-complaint-id={c.complaint_id}
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-medium text-fg">{c.title}</span>
                      <span className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-fg-2">
                        <span className="font-mono text-fg-3">#{c.complaint_id}</span>
                        {CATEGORY_LABEL[c.category]}
                        <SeverityDots severity={c.severity} />
                        {c.is_synthetic && <SyntheticBadge />}
                        {already && <Chip tone="good">Already attached</Chip>}
                      </span>
                    </span>
                  </label>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </Modal>
  )
}

// ---------------------------------------------------------------------------------------------------
type Mode = 'auto' | 'llm' | 'fallback'
const MODES: Array<{ value: Mode; title: string; text: string }> = [
  { value: 'auto', title: 'Auto', text: 'Use a language model if one is configured; otherwise use the rule-based fallback and say so.' },
  { value: 'llm', title: 'LLM only', text: 'Require a language model. Fails with a clear error if none is configured; it never silently falls back.' },
  { value: 'fallback', title: 'Rule-based only', text: 'Deterministic rules over database aggregates. No AI model is involved, and the output is labelled that way.' },
]

function RunCard({ inv, onRan }: { inv: Investigation; onRan: (result: RunResult) => void }) {
  const { can } = useAuth()
  const run = useRunInvestigation(inv.investigation_id)
  const overview = useOverview()
  const llm = overview.data?.system.llm
  const [mode, setMode] = useState<Mode>('auto')
  const [days, setDays] = useState('30')
  const [category, setCategory] = useState<'all' | Category>('all')
  const [maxHotspots, setMaxHotspots] = useState('3')

  const runnable = inv.status === 'OPEN' || inv.status === 'FAILED'
  const daysNumber = Number(days)
  const daysInvalid = !Number.isInteger(daysNumber) || daysNumber < 1 || daysNumber > 365
  const result = run.data

  return (
    <Card data-testid="run-card">
      <CardHeader
        title="Run the investigation"
        subtitle="The investigator reads the database through audited, read-only tools and proposes recommendations."
      />
      <CardBody className="flex flex-col gap-4">
        {!can('investigation:run') ? (
          <InfoNotice>Only analysts can run investigations. You can follow the results and audit history here.</InfoNotice>
        ) : !runnable ? (
          <InfoNotice title={`This investigation is ${inv.status === 'PENDING_REVIEW' ? 'awaiting review' : inv.status.toLowerCase()}`}>
            Only open or failed investigations can be run. Its results are shown below.
          </InfoNotice>
        ) : (
          <form
            className="flex flex-col gap-4"
            noValidate
            onSubmit={(event) => {
              event.preventDefault()
              if (daysInvalid) return
              run.mutate(
                {
                  mode,
                  days: daysNumber,
                  category: category === 'all' ? null : category,
                  max_hotspots: Number(maxHotspots),
                },
                { onSuccess: onRan },
              )
            }}
          >
            <fieldset className="flex flex-col gap-2" data-testid="mode-options">
              <legend className="mb-1 text-[13px] font-medium text-fg">Investigator</legend>
              {MODES.map((m) => (
                <label
                  key={m.value}
                  className={cn(
                    'flex cursor-pointer items-start gap-3 rounded-lg border px-3 py-2.5 transition-colors',
                    mode === m.value ? 'border-copper-400 bg-copper-500/10' : 'border-ink-700 bg-ink-850 hover:border-ink-600',
                  )}
                >
                  <input
                    type="radio"
                    name="mode"
                    value={m.value}
                    checked={mode === m.value}
                    onChange={() => setMode(m.value)}
                    className="mt-1 size-4 accent-copper-400"
                  />
                  <span>
                    <span className="block text-sm font-medium text-fg">{m.title}</span>
                    <span className="block text-[13px] leading-5 text-fg-2">{m.text}</span>
                  </span>
                </label>
              ))}
            </fieldset>

            {llm && !llm.configured && mode !== 'fallback' && (
              <InfoNotice title="No language model is configured on this server">
                {mode === 'llm'
                  ? 'LLM-only mode will be refused with LLM_NOT_CONFIGURED.'
                  : 'Auto mode will use the rule-based fallback, and the result will say so.'}
                {llm.problem ? ` (${llm.problem})` : ''}
              </InfoNotice>
            )}
            {llm?.configured && mode !== 'fallback' && (
              <InfoNotice>
                A language model is configured ({llm.provider}: {llm.model}). Its connectivity has not been verified by this page; a
                failed call is reported, never hidden.
              </InfoNotice>
            )}

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <TextInput
                label="Look-back window (days)"
                inputMode="numeric"
                value={days}
                onChange={(e) => setDays(e.target.value)}
                error={daysInvalid ? 'Enter a whole number from 1 to 365.' : null}
              />
              <SelectInput label="Category" value={category} onChange={(e) => setCategory(e.target.value as 'all' | Category)}>
                <option value="all">All categories</option>
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>{CATEGORY_LABEL[c]}</option>
                ))}
              </SelectInput>
              <SelectInput label="Max hotspots" value={maxHotspots} onChange={(e) => setMaxHotspots(e.target.value)}>
                {[1, 2, 3, 4, 5].map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </SelectInput>
            </div>
            <p className="-mt-2 text-xs leading-5 text-fg-3">
              The rule-based investigator uses these parameters; it does not read the free-text question.
            </p>

            <div>
              <Button type="submit" variant="primary" size="lg" loading={run.isPending} disabled={daysInvalid} icon={<Play className="size-4" aria-hidden />}>
                {run.isPending ? 'Running…' : 'Run investigation'}
              </Button>
            </div>
          </form>
        )}

        {run.isError && <ErrorNotice error={run.error} onDismiss={() => run.reset()} />}

        {result && (
          <div className="flex flex-col gap-3 rounded-xl border border-ink-600 bg-ink-850 p-4" data-testid="run-result">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold text-fg">Run result</span>
              <InvestigationStatusBadge status={result.status} testId="run-result-status" />
            </div>
            <GeneratorExplanation type={result.generator} modelName={result.model_name} />
            <p className="text-sm leading-6 text-fg-2" data-testid="run-notice">{result.notice}</p>
            {result.fallback_reason && (
              <p className="text-[13px] leading-5 text-fg-2" data-testid="fallback-reason">
                <strong className="font-semibold text-fg">Why the fallback was used:</strong> {result.fallback_reason}
              </p>
            )}
            <dl className="grid grid-cols-3 gap-3 text-sm">
              {[
                ['Steps', result.steps],
                ['Tool calls', result.tool_calls],
                ['Recommendations', result.recommendation_ids.length],
              ].map(([k, v]) => (
                <div key={k}>
                  <dt className="text-xs text-fg-3">{k}</dt>
                  <dd className="text-lg font-semibold text-fg">{v}</dd>
                </div>
              ))}
            </dl>
          </div>
        )}
      </CardBody>
    </Card>
  )
}

// ---------------------------------------------------------------------------------------------------
function ProposalModal({
  id,
  evidence,
  onClose,
  onCreated,
}: {
  id: number
  evidence: EvidenceItem[]
  onClose: () => void
  onCreated: () => void
}) {
  const propose = useProposeRecommendation(id)
  const [summary, setSummary] = useState('')
  const [rationale, setRationale] = useState('')
  const [priority, setPriority] = useState('3')
  const [confidence, setConfidence] = useState('50')
  const [cited, setCited] = useState<Set<number>>(new Set())
  const [submitted, setSubmitted] = useState(false)
  const errors = validateRecommendation({ summary, rationale, evidenceIds: [...cited] })
  const confidenceNumber = Number(confidence)
  const confidenceInvalid = !Number.isFinite(confidenceNumber) || confidenceNumber < 0 || confidenceNumber > 100

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitted(true)
    if (!isValid(errors) || confidenceInvalid) return
    propose.mutate(
      {
        summary: summary.trim(),
        rationale: rationale.trim(),
        priority: Number(priority),
        confidence: confidenceNumber / 100,
        evidence_ids: [...cited].sort((a, b) => a - b),
      },
      { onSuccess: onCreated },
    )
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Propose a recommendation"
      size="lg"
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" type="submit" form="proposal-form" loading={propose.isPending}>
            Propose
          </Button>
        </>
      }
    >
      <form id="proposal-form" onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        <InfoNotice>
          This will be recorded as a <strong className="text-fg">manual</strong> recommendation written by you. No AI model or
          rule set is involved, and it still needs a reviewer’s decision.
        </InfoNotice>
        {propose.isError && <ErrorNotice error={propose.error} />}
        <TextInput label="Summary" value={summary} onChange={(e) => setSummary(e.target.value)} error={submitted ? (errors.summary ?? null) : null} data-autofocus />
        <TextArea label="Explanation" value={rationale} onChange={(e) => setRationale(e.target.value)} error={submitted ? (errors.rationale ?? null) : null} hint="Say why the cited evidence supports this action." />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <SelectInput label="Priority" value={priority} onChange={(e) => setPriority(e.target.value)} hint="1 is the most urgent.">
            {[1, 2, 3, 4, 5].map((p) => (
              <option key={p} value={p}>{p} · {PRIORITY_LABEL[p]}</option>
            ))}
          </SelectInput>
          <TextInput
            label="Confidence (%)"
            inputMode="numeric"
            value={confidence}
            onChange={(e) => setConfidence(e.target.value)}
            error={submitted && confidenceInvalid ? 'Enter a number from 0 to 100.' : null}
          />
        </div>
        <fieldset>
          <legend className="mb-1.5 text-[13px] font-medium text-fg">Cite attached evidence</legend>
          {evidence.length === 0 ? (
            <p className="text-sm text-fg-2">Attach evidence to this investigation first, then cite it here.</p>
          ) : (
            <ul className="max-h-48 divide-y divide-ink-700/70 overflow-y-auto rounded-lg border border-ink-700">
              {evidence.map((e) => (
                <li key={e.complaint_id}>
                  <label className="flex cursor-pointer items-start gap-3 px-3 py-2 hover:bg-ink-750/60">
                    <input
                      type="checkbox"
                      className="mt-1 size-4 accent-copper-400"
                      checked={cited.has(e.complaint_id)}
                      onChange={() =>
                        setCited((prev) => {
                          const next = new Set(prev)
                          if (next.has(e.complaint_id)) next.delete(e.complaint_id)
                          else next.add(e.complaint_id)
                          return next
                        })
                      }
                    />
                    <span className="text-sm text-fg">
                      <span className="font-mono text-xs text-fg-3">#{e.complaint_id}</span> {e.title}
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          )}
          {submitted && errors.evidence && <p className="mt-1.5 text-xs text-fg"><span className="text-critical">●</span> {errors.evidence}</p>}
        </fieldset>
      </form>
    </Modal>
  )
}
