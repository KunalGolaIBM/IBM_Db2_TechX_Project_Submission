import { Bot, CircleCheck, CircleX, Cog, UserRound, Wrench } from 'lucide-react'
import { useState } from 'react'
import type { AuditEntry } from '../api/schemas'
import { actionLabel, formatAuditValue, generatorOfRun, isToolActivity, parseAuditInput } from '../lib/audit'
import { cn } from '../lib/cn'
import { describeGenerator } from '../lib/generator'
import { formatDateTime } from '../lib/format'
import { GeneratorBadge } from './Badges'
import { Checkbox, EmptyState } from './ui'

const actorIcon = (type: string) =>
  type === 'AGENT' ? <Bot className="size-4" /> : type === 'SYSTEM' ? <Cog className="size-4" /> : <UserRound className="size-4" />

/** Append-only history of one investigation straight from AUDIT_LOG, with tool calls called out. */
export function AuditTimeline({ entries }: { entries: AuditEntry[] }) {
  const [toolsOnly, setToolsOnly] = useState(false)
  const toolCalls = entries.filter(isToolActivity)
  const shown = toolsOnly ? toolCalls : entries
  const generator = generatorOfRun(entries)
  const gen = generator ? describeGenerator(generator, null) : null

  if (entries.length === 0) return <EmptyState title="No activity recorded yet" />

  return (
    <div data-testid="audit-timeline">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <p className="text-[13px] text-fg-2" data-testid="audit-summary">
          {entries.length} audit {entries.length === 1 ? 'entry' : 'entries'} · {toolCalls.length} tool{' '}
          {toolCalls.length === 1 ? 'call' : 'calls'}
        </p>
        <Checkbox label="Tool activity only" checked={toolsOnly} onChange={(e) => setToolsOnly(e.target.checked)} />
      </div>

      {generator && gen && (
        <div
          className="mb-4 flex flex-wrap items-center gap-2 rounded-lg border border-ink-700 bg-ink-850 px-3 py-2 text-[13px] text-fg-2"
          data-testid="tool-activity-origin"
        >
          <Wrench className="size-4 text-fg-3" aria-hidden />
          Tool calls in this run were issued by
          <GeneratorBadge type={generator} modelName={null} />
          {!gen.isRealModel && <span>These calls were not made by a language model.</span>}
        </div>
      )}

      <ol className="relative flex flex-col gap-0">
        {shown.map((e, i) => {
          const input = parseAuditInput(e.input_json)
          const tool = isToolActivity(e)
          return (
            <li
              key={e.audit_id}
              data-testid="audit-entry"
              data-action={e.action}
              data-tool={e.tool_name ?? ''}
              data-success={e.success}
              className="relative flex gap-3 pb-4 last:pb-0"
            >
              {i < shown.length - 1 && <span className="absolute top-8 bottom-0 left-[15px] w-px bg-ink-700" aria-hidden />}
              <span
                className={cn(
                  'z-[1] flex size-8 shrink-0 items-center justify-center rounded-full border bg-ink-800',
                  tool ? 'border-copper-500/60 text-copper-400' : 'border-ink-600 text-fg-2',
                )}
                aria-hidden
              >
                {actorIcon(e.actor_type)}
              </span>
              <div className="min-w-0 flex-1 pt-0.5">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <span className="text-sm font-medium text-fg">{actionLabel(e.action)}</span>
                  {e.tool_name && <code className="rounded bg-ink-750 px-1.5 py-0.5 font-mono text-xs text-fg">{e.tool_name}</code>}
                  <span className="inline-flex items-center gap-1 text-xs text-fg-2">
                    {e.success ? (
                      <CircleCheck className="size-3.5 text-good" aria-hidden />
                    ) : (
                      <CircleX className="size-3.5 text-critical" aria-hidden />
                    )}
                    {e.success ? 'ok' : 'failed'}
                  </span>
                </div>
                <p className="text-xs text-fg-3">
                  {e.actor_id} · {formatDateTime(e.created_at)}
                </p>
                {input && Object.keys(input).length > 0 && (
                  <dl className="mt-1.5 flex flex-wrap gap-1.5">
                    {Object.entries(input)
                      .slice(0, 8)
                      .map(([k, v]) => (
                        <div key={k} className="flex gap-1 rounded-md border border-ink-700 bg-ink-850 px-1.5 py-0.5 text-xs">
                          <dt className="text-fg-3">{k}</dt>
                          <dd className="text-fg-2">{formatAuditValue(v)}</dd>
                        </div>
                      ))}
                  </dl>
                )}
                {e.output_summary && <p className="mt-1 text-[13px] leading-5 text-fg-2">{e.output_summary}</p>}
              </div>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
