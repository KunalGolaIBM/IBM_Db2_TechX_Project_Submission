import {
  CircleCheck,
  CircleDashed,
  CircleHelp,
  CircleX,
  Cog,
  FlaskConical,
  Hourglass,
  LoaderCircle,
  PenLine,
  Sparkles,
} from 'lucide-react'
import type { ReactNode } from 'react'
import {
  COMPLAINT_STATUS_LABEL,
  INVESTIGATION_STATUS_LABEL,
  PRIORITY_LABEL,
  RECOMMENDATION_STATUS_LABEL,
  SEVERITY_LABEL,
  severityColor,
  type ComplaintStatus,
  type GeneratorType,
  type InvestigationStatus,
  type RecommendationStatus,
} from '../lib/domain'
import { describeGenerator, type GeneratorKind } from '../lib/generator'
import { cn } from '../lib/cn'
import { Chip, type Tone } from './ui'

const generatorStyle: Record<GeneratorKind, { tone: Tone; icon: ReactNode }> = {
  llm: { tone: 'copper', icon: <Sparkles /> },
  rules: { tone: 'info', icon: <Cog /> },
  manual: { tone: 'aqua', icon: <PenLine /> },
  'test-double': { tone: 'violet', icon: <FlaskConical /> },
  unknown: { tone: 'neutral', icon: <CircleHelp /> },
}

/**
 * Who produced a recommendation. Colour is only a secondary cue: every variant also has its own icon and
 * its own words, and the rule-based label says "no LLM" explicitly.
 */
export function GeneratorBadge({
  type,
  modelName,
  className,
}: {
  type: GeneratorType
  modelName: string | null
  className?: string
}) {
  const info = describeGenerator(type, modelName)
  const style = generatorStyle[info.kind]
  return (
    <Chip
      tone={style.tone}
      icon={style.icon}
      title={info.description}
      className={className}
      data-testid="generator-badge"
      data-generator-kind={info.kind}
    >
      {info.label}
    </Chip>
  )
}

/** The full-sentence version, for panels where the reader must understand the provenance. */
export function GeneratorExplanation({ type, modelName }: { type: GeneratorType; modelName: string | null }) {
  const info = describeGenerator(type, modelName)
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-ink-700 bg-ink-850 p-3" data-testid="generator-explanation">
      <div className="flex flex-wrap items-center gap-2">
        <GeneratorBadge type={type} modelName={modelName} />
        {info.detail && <code className="font-mono text-xs text-fg-2">{info.detail}</code>}
      </div>
      <p className="text-[13px] leading-5 text-fg-2">{info.description}</p>
    </div>
  )
}

const investigationStyle: Record<InvestigationStatus, { tone: Tone; icon: ReactNode }> = {
  OPEN: { tone: 'neutral', icon: <CircleDashed /> },
  RUNNING: { tone: 'info', icon: <LoaderCircle className="animate-spin" /> },
  PENDING_REVIEW: { tone: 'warn', icon: <Hourglass /> },
  CLOSED: { tone: 'good', icon: <CircleCheck /> },
  FAILED: { tone: 'critical', icon: <CircleX /> },
}
export function InvestigationStatusBadge({
  status,
  testId = 'investigation-status',
}: {
  status: InvestigationStatus
  testId?: string
}) {
  const s = investigationStyle[status]
  return (
    <Chip tone={s.tone} icon={s.icon} data-testid={testId} data-status={status}>
      {INVESTIGATION_STATUS_LABEL[status]}
    </Chip>
  )
}

const recommendationStyle: Record<RecommendationStatus, { tone: Tone; icon: ReactNode }> = {
  PROPOSED: { tone: 'warn', icon: <Hourglass /> },
  APPROVED: { tone: 'good', icon: <CircleCheck /> },
  REJECTED: { tone: 'critical', icon: <CircleX /> },
  NEEDS_INFO: { tone: 'info', icon: <CircleHelp /> },
}
export function RecommendationStatusBadge({ status }: { status: RecommendationStatus }) {
  const s = recommendationStyle[status]
  return (
    <Chip tone={s.tone} icon={s.icon} data-testid="recommendation-status" data-status={status}>
      {RECOMMENDATION_STATUS_LABEL[status]}
    </Chip>
  )
}

const complaintTone: Record<ComplaintStatus, Tone> = {
  NEW: 'neutral',
  TRIAGED: 'info',
  DUPLICATE: 'neutral',
  UNDER_INVESTIGATION: 'copper',
  RESOLVED: 'good',
  REJECTED: 'critical',
}
export const ComplaintStatusBadge = ({ status }: { status: ComplaintStatus }) => (
  <Chip tone={complaintTone[status]}>{COMPLAINT_STATUS_LABEL[status]}</Chip>
)

/** Dashed outline matches the dashed ring used for synthetic points on the map. */
export function SyntheticBadge({ className }: { className?: string }) {
  return (
    <span
      data-testid="synthetic-badge"
      title="Fictional demonstration record, not a real citizen report"
      className={cn(
        'inline-flex items-center gap-1 rounded-md border border-dashed border-fg-3 px-1.5 py-px text-[11px] leading-4 font-semibold tracking-wider text-fg-2 uppercase',
        className,
      )}
    >
      <FlaskConical className="size-3" aria-hidden />
      Synthetic
    </span>
  )
}

export function SeverityDots({ severity }: { severity: number }) {
  return (
    <span
      role="img"
      aria-label={`Severity ${severity} of 5 (${SEVERITY_LABEL[severity] ?? 'unknown'})`}
      title={`Severity ${severity} of 5 · ${SEVERITY_LABEL[severity] ?? ''}`}
      className="inline-flex items-center gap-0.5"
    >
      {[1, 2, 3, 4, 5].map((i) => (
        <span
          key={i}
          className="size-2 rounded-[2px]"
          style={{ background: i <= severity ? severityColor(severity) : 'var(--color-ink-600)' }}
        />
      ))}
    </span>
  )
}

export function PriorityBadge({ priority }: { priority: number }) {
  const strong = priority <= 2
  return (
    <span
      data-testid="priority-badge"
      title={`Priority ${priority} of 5: ${PRIORITY_LABEL[priority] ?? ''} (1 is most urgent)`}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-semibold',
        strong ? 'border-copper-400/70 bg-copper-500/15 text-fg' : 'border-ink-600 bg-ink-750 text-fg-2',
      )}
    >
      P{priority}
      <span className="font-medium text-fg-2">{PRIORITY_LABEL[priority]}</span>
    </span>
  )
}

/** Same-ramp track meter (the unfilled track is a darker step of the fill's own hue). */
export function ConfidenceMeter({ value, caption }: { value: number; caption: string }) {
  const pct = Math.round(Math.min(Math.max(value, 0), 1) * 100)
  return (
    <div className="min-w-32">
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className="text-fg-2">{caption}</span>
        <span className="font-semibold text-fg tabular-nums">{pct}%</span>
      </div>
      <div
        role="meter"
        aria-label={caption}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        className="mt-1 h-1.5 overflow-hidden rounded-full bg-copper-700/45"
      >
        <div className="h-full rounded-full bg-copper-500" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}
