import { CircleCheck, TriangleAlert, Wrench } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useOverview, useRecommendationQueue } from '../api/queries'
import { SegmentedBar } from '../charts/SegmentedBar'
import { ChartCard, DataTable } from '../charts/ChartCard'
import { GeneratorBadge, RecommendationStatusBadge } from '../components/Badges'
import { ErrorNotice } from '../components/Notices'
import { Card, CardBody, CardHeader, LoadingBlock, PageHeader } from '../components/ui'
import { actionLabel } from '../lib/audit'
import { GENERATOR_COLOR, GENERATOR_SEGMENT_LABEL, GENERATOR_TYPES, type GeneratorType } from '../lib/domain'
import { describeGenerator } from '../lib/generator'
import { formatInt, formatRelative, pluralise } from '../lib/format'

const EXPLAINED: GeneratorType[] = ['LLM', 'DETERMINISTIC_FALLBACK', 'MANUAL']

const GUARD_RAILS = [
  ['Allow-listed tools only', 'The agent can call a fixed set of read-only tools. Any other tool name is refused and audited.'],
  ['No model-written SQL', 'Each tool runs one fixed, parameterised query. Nothing a model writes is ever executed as SQL.'],
  ['Evidence must be grounded', 'A recommendation may only cite complaints that a tool returned during the same run. Invented IDs are rejected.'],
  ['Proposals only', 'The system can only create recommendations in the PROPOSED state. It cannot approve anything.'],
  ['People decide', 'Reviewers approve or reject, and nobody reviews an investigation they created.'],
  ['Everything is audited', 'Each tool call, refusal, run and decision is appended to the audit log with who did it.'],
] as const

export function TransparencyView() {
  const overview = useOverview()
  const latest = useRecommendationQueue({ limit: 12 })

  if (overview.isPending) return <LoadingBlock label="Loading agent transparency" className="min-h-96" />
  if (!overview.data) return <ErrorNotice error={overview.error} onRetry={() => void overview.refetch()} />

  const o = overview.data
  const byGen = o.recommendations.by_generator
  const llmCount = byGen.LLM ?? 0
  const total = o.recommendations.total
  const { llm, agent } = o.system

  return (
    <div className="flex flex-col gap-6" data-testid="transparency-view">
      <PageHeader
        title="Agent transparency"
        description="Who or what wrote each recommendation, what the agent is allowed to do, and what has actually happened. Rule-based output is never presented as AI."
      />

      <Card data-testid="llm-status">
        <CardBody className="flex flex-col gap-3 pt-5">
          <div className="flex items-start gap-3">
            {llm.configured ? (
              <CircleCheck className="mt-0.5 size-5 shrink-0 text-good" aria-hidden />
            ) : (
              <TriangleAlert className="mt-0.5 size-5 shrink-0 text-warn" aria-hidden />
            )}
            <div>
              <h2 className="text-[15px] font-semibold text-fg">
                {llm.configured ? `Language model configured: ${llm.provider} · ${llm.model}` : 'No language model is configured'}
              </h2>
              <p className="mt-1 text-sm leading-6 text-fg-2">
                {llm.configured
                  ? 'The settings are complete. This page does not test connectivity to the provider, and a failed model call is reported and audited, never hidden.'
                  : `Investigations run in rule-based mode and say so. ${llm.problem ?? ''}`}
              </p>
              <p className="mt-2 text-sm leading-6 text-fg" data-testid="llm-count-statement">
                {total === 0
                  ? 'There are no recommendations in the database yet.'
                  : llmCount === 0
                    ? total === 1
                      ? 'The one recommendation in the database was not written by a language model.'
                      : `None of the ${formatInt(total)} recommendations in the database were written by a language model.`
                    : `${formatInt(llmCount)} of ${formatInt(total)} ${pluralise(total, 'recommendation')} ${llmCount === 1 ? 'was' : 'were'} written by a language model; each is labelled with its provider and model.`}
              </p>
            </div>
          </div>
        </CardBody>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {EXPLAINED.map((g) => {
          const info = describeGenerator(g, null)
          return (
            <Card key={g} className="flex flex-col gap-3 p-5" data-testid={`generator-card-${g}`}>
              <div className="flex items-center justify-between gap-2">
                <GeneratorBadge type={g} modelName={null} />
                <span className="text-2xl font-semibold text-fg" data-testid={`generator-count-${g}`}>
                  {formatInt(byGen[g] ?? 0)}
                </span>
              </div>
              <p className="text-sm leading-6 text-fg-2">{info.description}</p>
            </Card>
          )
        })}
      </div>

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-5">
        <ChartCard
          className="lg:col-span-3"
          title="Recommendations by author"
          subtitle="Colour follows the author everywhere in the dashboard."
          table={
            <DataTable
              caption="Recommendations by generator"
              columns={[
                { key: 'g', label: 'Author' },
                { key: 'n', label: 'Recommendations', numeric: true },
              ]}
              rows={GENERATOR_TYPES.map((g) => ({ g: GENERATOR_SEGMENT_LABEL[g], n: byGen[g] ?? 0 }))}
            />
          }
        >
          <SegmentedBar
            ariaLabel="Recommendations by generator"
            data={GENERATOR_TYPES.map((g) => ({ key: g, label: GENERATOR_SEGMENT_LABEL[g], value: byGen[g] ?? 0, color: GENERATOR_COLOR[g] }))}
          />
        </ChartCard>

        <Card className="lg:col-span-2" data-testid="guard-rails">
          <CardHeader title="Guard rails in force" subtitle="Enforced in code and covered by automated tests." />
          <CardBody>
            <dl className="grid grid-cols-2 gap-3 border-b border-ink-700 pb-4">
              <div>
                <dt className="text-xs text-fg-3">Maximum steps per run</dt>
                <dd className="text-xl font-semibold text-fg">{agent.max_steps}</dd>
              </div>
              <div>
                <dt className="text-xs text-fg-3">Time limit per run</dt>
                <dd className="text-xl font-semibold text-fg">{agent.timeout_s} s</dd>
              </div>
            </dl>
            <p className="mt-4 flex items-center gap-1.5 text-xs text-fg-2">
              <Wrench className="size-3.5" aria-hidden />
              Allow-listed tools ({agent.tools.length})
            </p>
            <ul className="mt-1.5 flex flex-wrap gap-1.5" data-testid="tool-list">
              {agent.tools.map((t) => (
                <li key={t} className="rounded-md border border-ink-600 bg-ink-850 px-2 py-0.5 font-mono text-xs text-fg">{t}</li>
              ))}
            </ul>
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader title="How the agent is constrained" />
        <CardBody>
          <ul className="grid grid-cols-1 gap-x-8 gap-y-4 md:grid-cols-2">
            {GUARD_RAILS.map(([title, text]) => (
              <li key={title} className="flex gap-3">
                <CircleCheck className="mt-0.5 size-4 shrink-0 text-good" aria-hidden />
                <div>
                  <p className="text-sm font-medium text-fg">{title}</p>
                  <p className="text-[13px] leading-5 text-fg-2">{text}</p>
                </div>
              </li>
            ))}
          </ul>
        </CardBody>
      </Card>

      <Card data-testid="latest-recommendations">
        <CardHeader
          title="Latest recommendations and their authors"
          subtitle="The generator shown here is the one stored in the database with each recommendation."
        />
        <CardBody>
          {latest.isPending ? (
            <LoadingBlock label="Loading recommendations" />
          ) : latest.isError ? (
            <ErrorNotice error={latest.error} onRetry={() => void latest.refetch()} />
          ) : latest.data.length === 0 ? (
            <p className="py-6 text-center text-sm text-fg-2">No recommendations yet.</p>
          ) : (
            <div className="overflow-x-auto">
              {/* Below sm each row is a small stacked block instead of a table row: the table rows are display:block there, so the roles are explicit */}
              <table role="table" className="w-full text-sm max-sm:block">
                <caption className="sr-only">Latest recommendations and their generators</caption>
                <thead role="rowgroup" className="max-sm:sr-only">
                  <tr role="row" className="border-b border-ink-700 text-left text-xs text-fg-2">
                    <th role="columnheader" scope="col" className="hidden px-2 py-2 font-medium sm:table-cell">ID</th>
                    <th role="columnheader" scope="col" className="px-2 py-2 font-medium">Recommendation</th>
                    <th role="columnheader" scope="col" className="px-2 py-2 font-medium">Author</th>
                    <th role="columnheader" scope="col" className="px-2 py-2 font-medium">Status</th>
                    <th role="columnheader" scope="col" className="hidden px-2 py-2 font-medium sm:table-cell">Investigation</th>
                  </tr>
                </thead>
                <tbody role="rowgroup" className="max-sm:block">
                  {latest.data.map((r) => (
                    <tr
                      key={r.recommendation_id}
                      role="row"
                      className="border-b border-ink-700/60 last:border-0 max-sm:block max-sm:py-3"
                      data-testid="author-row"
                      data-generator={r.generator_type}
                    >
                      <td role="cell" className="hidden px-2 py-2 font-mono text-xs text-fg-2 sm:table-cell">#{r.recommendation_id}</td>
                      <td role="cell" className="max-w-sm px-2 py-2 text-fg max-sm:block max-sm:max-w-none max-sm:px-0 max-sm:pt-0">
                        <span className="line-clamp-2">{r.summary}</span>
                      </td>
                      <td role="cell" className="px-2 py-2 max-sm:mr-2 max-sm:inline-block max-sm:p-0">
                        <GeneratorBadge type={r.generator_type} modelName={r.model_name} />
                      </td>
                      <td role="cell" className="px-2 py-2 max-sm:inline-block max-sm:p-0">
                        <RecommendationStatusBadge status={r.status} />
                      </td>
                      <td role="cell" className="hidden px-2 py-2 sm:table-cell">
                        <Link to={`/investigations/${r.investigation_id}`} className="font-mono text-xs text-copper-400 hover:text-copper-300">
                          #{r.investigation_id}
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Recent audited tool activity" subtitle="Tool calls are logged identically whether a language model or the rule-based fallback issued them." />
        <CardBody>
          {o.recent_agent_activity.length === 0 ? (
            <p className="py-6 text-center text-sm text-fg-2">No agent runs recorded yet.</p>
          ) : (
            <ul className="divide-y divide-ink-700/70" data-testid="transparency-activity">
              {o.recent_agent_activity.map((a) => (
                <li key={a.audit_id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2 text-sm">
                  <span className="w-20 shrink-0 text-xs text-fg-3">{formatRelative(a.created_at)}</span>
                  <span className="text-fg">{actionLabel(a.action)}</span>
                  {a.tool_name && <code className="rounded bg-ink-750 px-1.5 py-0.5 font-mono text-xs text-fg-2">{a.tool_name}</code>}
                  {a.investigation_id && (
                    <Link to={`/investigations/${a.investigation_id}`} className="font-mono text-xs text-copper-400 hover:text-copper-300">
                      #{a.investigation_id}
                    </Link>
                  )}
                  {!a.success && <span className="text-xs text-warn">failed</span>}
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
