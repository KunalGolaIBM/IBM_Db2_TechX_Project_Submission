import {
  Activity,
  Bot,
  CircleCheck,
  ClipboardCheck,
  Database,
  FolderSearch,
  Info,
  MapPin,
  RefreshCw,
  ShieldCheck,
  TriangleAlert,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useOverview } from '../api/queries'
import type { Overview } from '../api/schemas'
import { useMe } from '../auth/AuthContext'
import { ChartCard, DataTable } from '../charts/ChartCard'
import { ColumnChart } from '../charts/ColumnChart'
import { RankedBars } from '../charts/RankedBars'
import { SegmentedBar } from '../charts/SegmentedBar'
import { Sparkline } from '../charts/Sparkline'
import { StatTile } from '../charts/StatTile'
import { TrendChart } from '../charts/TrendChart'
import { SeverityDots } from '../components/Badges'
import { ErrorNotice, SyntheticBanner } from '../components/Notices'
import { Button, Card, CardBody, CardHeader, Chip, LoadingBlock, PageHeader } from '../components/ui'
import { actionLabel } from '../lib/audit'
import {
  CATEGORY_LABEL,
  GENERATOR_COLOR,
  GENERATOR_SEGMENT_LABEL,
  GENERATOR_TYPES,
  RECOMMENDATION_STATUS_LABEL,
  RECOMMENDATION_STATUSES,
  SEVERITY_COLORS,
  SEVERITY_LABEL,
} from '../lib/domain'
import { formatClock, formatDayMonth, formatInt, formatRelative, pluralise } from '../lib/format'
import { CELL_METERS, hotspotKey } from '../map/geo'

type StatusTone = 'good' | 'warn' | 'info'
const statusIcon: Record<StatusTone, ReactNode> = {
  good: <CircleCheck className="size-5 text-good" aria-hidden />,
  warn: <TriangleAlert className="size-5 text-warn" aria-hidden />,
  info: <Info className="size-5 text-series-2" aria-hidden />,
}

function StatusRow({ tone, title, children, testId }: { tone: StatusTone; title: string; children: ReactNode; testId: string }) {
  return (
    <li className="flex gap-3 py-3" data-testid={testId} data-tone={tone}>
      <span className="mt-0.5 shrink-0">{statusIcon[tone]}</span>
      <div className="min-w-0">
        <p className="text-sm font-medium text-fg">{title}</p>
        <p className="mt-0.5 text-[13px] leading-5 text-fg-2">{children}</p>
      </div>
    </li>
  )
}

function OperationalStatus({ o, userLine }: { o: Overview; userLine: string }) {
  const { database, llm, agent, environment } = o.system
  return (
    <Card data-testid="operational-status">
      <CardHeader title="Operational status" subtitle="Read from the live system, not hardcoded." />
      <CardBody>
        <ul className="divide-y divide-ink-700">
          <StatusRow tone="good" title="API reachable" testId="status-api">
            Answered this page’s request at {formatClock(o.generated_at)} UTC.
          </StatusRow>
          <StatusRow tone="good" title={`${database.product} ${database.version}`} testId="status-db">
            Database {database.database}, schema {database.schema_name}. Verified by the live queries behind this page.
          </StatusRow>
          {llm.configured ? (
            <StatusRow tone="info" title={`Language model configured: ${llm.provider}`} testId="status-llm">
              Model <code className="font-mono text-fg">{llm.model}</code>. The settings are complete, but this page does not
              test connectivity to the provider.
            </StatusRow>
          ) : (
            <StatusRow tone="warn" title="No language model configured" testId="status-llm">
              Investigations use the deterministic rule-based fallback, which is labelled “no LLM” everywhere it appears.
              {llm.problem ? ` ${llm.problem}` : ''}
            </StatusRow>
          )}
          <StatusRow tone="info" title="Agent guard rails" testId="status-agent">
            At most {agent.max_steps} {pluralise(agent.max_steps, 'step')} and {agent.timeout_s} s per run, {agent.tools.length} read-only
            allow-listed {pluralise(agent.tools.length, 'tool')}.
            The agent can only propose; people decide.
          </StatusRow>
          <StatusRow tone="info" title="Access" testId="status-access">
            {userLine}. Environment: {environment}.
          </StatusRow>
        </ul>
      </CardBody>
    </Card>
  )
}

export function OverviewView() {
  const me = useMe()
  const q = useOverview()

  if (q.isPending) return <LoadingBlock label="Loading the intelligence overview" className="min-h-96" />
  if (!q.data) return <ErrorNotice error={q.error} onRetry={() => void q.refetch()} />

  const o = q.data
  const c = o.complaints
  const dimmed = q.isFetching
  const trend = c.trend.map((p) => p.count)
  const bySeverity = c.by_severity.map((s) => ({
    key: String(s.severity),
    label: String(s.severity),
    sublabel: SEVERITY_LABEL[s.severity],
    value: s.count,
    color: SEVERITY_COLORS[s.severity - 1],
  }))
  const provenance = GENERATOR_TYPES.map((g) => ({
    key: g,
    label: GENERATOR_SEGMENT_LABEL[g],
    value: o.recommendations.by_generator[g] ?? 0,
    color: GENERATOR_COLOR[g],
  }))
  const llmCount = o.recommendations.by_generator.LLM ?? 0

  return (
    <div className="flex flex-col gap-6" data-testid="overview">
      <PageHeader
        title="Intelligence overview"
        description="Every figure on this page is computed by IBM Db2 when you load it. Nothing is cached in the browser or hardcoded."
        actions={
          <>
            <span className="text-[13px] text-fg-2" data-testid="updated-at">
              Updated {formatClock(o.generated_at)} UTC
            </span>
            <Button
              size="sm"
              onClick={() => void q.refetch()}
              loading={q.isFetching}
              icon={<RefreshCw className="size-3.5" aria-hidden />}
            >
              Refresh
            </Button>
          </>
        }
      />

      {q.isError && <ErrorNotice error={q.error} onRetry={() => void q.refetch()} />}
      <SyntheticBanner synthetic={c.synthetic} total={c.total} />

      <div className={`grid gap-4 md:grid-cols-2 xl:grid-cols-[1.7fr_1fr_1fr_1fr] ${dimmed ? 'opacity-70' : ''} transition-opacity`}>
        <StatTile
          hero
          testId="kpi-complaints"
          to="/complaints"
          icon={<Database />}
          label="Complaints tracked"
          value={formatInt(c.total)}
          context={
            <>
              {formatInt(c.last_7d)} in the last 7 days · {formatInt(c.last_30d)} in 30 days ·{' '}
              <span data-testid="provenance-split">
                {formatInt(c.synthetic)} synthetic, {formatInt(c.real)} real
              </span>
            </>
          }
          trend={<Sparkline values={trend} ariaLabel={`Daily new complaints, last ${c.trend_days} days`} />}
        />
        <StatTile
          testId="kpi-investigations"
          to="/investigations"
          icon={<FolderSearch />}
          label="Active investigations"
          value={formatInt(o.investigations.active)}
          context={`of ${formatInt(o.investigations.total)} total · ${formatInt(o.investigations.by_status.PENDING_REVIEW ?? 0)} awaiting review`}
        />
        <StatTile
          testId="kpi-pending"
          to="/review"
          icon={<ClipboardCheck />}
          label="Awaiting human review"
          value={formatInt(o.recommendations.pending_review)}
          context={`${pluralise(o.recommendations.pending_review, 'recommendation')} with no decision yet`}
        />
        <StatTile
          testId="kpi-hotspots"
          to="/map"
          icon={<MapPin />}
          label="Active hotspots"
          value={formatInt(o.hotspots.total)}
          context={`${o.hotspots.min_count}+ complaints in one grid cell within ${o.hotspots.window_days} days`}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChartCard
          testId="chart-category"
          title="Complaints by category"
          subtitle="All time, ranked. Bar length is the count; the label names the category."
          dimmed={dimmed}
          table={
            <DataTable
              caption="Complaints by category"
              columns={[
                { key: 'cat', label: 'Category' },
                { key: 'n', label: 'Complaints', numeric: true },
                { key: 'sev', label: 'Avg severity', numeric: true },
                { key: 'syn', label: 'Synthetic', numeric: true },
              ]}
              rows={c.by_category.map((x) => ({
                cat: CATEGORY_LABEL[x.category],
                n: formatInt(x.count),
                sev: x.avg_severity.toFixed(2),
                syn: formatInt(x.synthetic),
              }))}
            />
          }
        >
          <RankedBars
            ariaLabel="Complaints by category"
            data={c.by_category.map((x) => ({
              key: x.category,
              label: CATEGORY_LABEL[x.category],
              value: x.count,
              note: `avg severity ${x.avg_severity.toFixed(1)}`,
            }))}
          />
        </ChartCard>

        <ChartCard
          testId="chart-trend"
          title={`New complaints per day, last ${c.trend_days} days`}
          subtitle="By reported date (UTC). Hover or use the arrow keys to read a day."
          dimmed={dimmed}
          table={
            <DataTable
              caption="New complaints per day"
              columns={[
                { key: 'd', label: 'Date (UTC)' },
                { key: 'n', label: 'Complaints', numeric: true },
              ]}
              rows={c.trend.map((p) => ({ d: formatDayMonth(p.date), n: p.count }))}
            />
          }
        >
          <TrendChart points={c.trend} ariaLabel={`New complaints per day for the last ${c.trend_days} days.`} />
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        <ChartCard
          testId="chart-severity"
          className="lg:col-span-2"
          title="Severity distribution"
          subtitle="One-hue ramp: lighter means more severe."
          dimmed={dimmed}
          table={
            <DataTable
              caption="Complaints by severity"
              columns={[
                { key: 's', label: 'Severity' },
                { key: 'n', label: 'Complaints', numeric: true },
              ]}
              rows={c.by_severity.map((s) => ({ s: `${s.severity} · ${SEVERITY_LABEL[s.severity]}`, n: s.count }))}
            />
          }
        >
          <ColumnChart data={bySeverity} ariaLabel="Complaints by severity, 1 (minor) to 5 (critical)" />
        </ChartCard>

        <ChartCard
          testId="chart-provenance"
          className="lg:col-span-3"
          title="Who wrote the recommendations"
          subtitle="Provenance of every recommendation in the database. Rule-based output is never counted as AI."
          dimmed={dimmed}
          table={
            <DataTable
              caption="Recommendations by generator"
              columns={[
                { key: 'g', label: 'Generator' },
                { key: 'n', label: 'Recommendations', numeric: true },
              ]}
              rows={GENERATOR_TYPES.map((g) => ({ g: GENERATOR_SEGMENT_LABEL[g], n: o.recommendations.by_generator[g] ?? 0 }))}
            />
          }
          footer={
            <div className="mt-5 grid grid-cols-3 gap-3 border-t border-ink-700 pt-4" data-testid="pipeline">
              {RECOMMENDATION_STATUSES.filter((s) => s !== 'NEEDS_INFO').map((s) => (
                <div key={s}>
                  <div className="text-xl font-semibold text-fg" data-testid={`rec-status-${s}`}>
                    {formatInt(o.recommendations.by_status[s] ?? 0)}
                  </div>
                  <div className="text-xs text-fg-2">{RECOMMENDATION_STATUS_LABEL[s]}</div>
                </div>
              ))}
            </div>
          }
        >
          <SegmentedBar data={provenance} ariaLabel="Recommendations by generator" />
          {llmCount === 0 && o.recommendations.total > 0 && (
            <p className="mt-4 text-[13px] leading-5 text-fg-2" data-testid="no-llm-note">
              {o.recommendations.total === 1
                ? 'The one recommendation was not written by a language model.'
                : `None of the ${formatInt(o.recommendations.total)} recommendations were written by a language model.`}
            </p>
          )}
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-5">
        <Card className="flex flex-col xl:col-span-3" data-testid="top-hotspots">
          <CardHeader
            title="Top hotspots"
            subtitle={`Highest complaint counts per geo-cell and category, last ${o.hotspots.window_days} days (Db2 GROUP BY).`}
            actions={
              <Link to="/map" className="text-[13px] font-medium text-copper-400 hover:text-copper-300">
                Open the map
              </Link>
            }
          />
          <CardBody>
            {o.hotspots.items.length === 0 ? (
              <p className="py-6 text-center text-sm text-fg-2">No cell has reached the hotspot threshold in this window.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <caption className="sr-only">Top hotspots</caption>
                  <thead>
                    <tr className="border-b border-ink-700 text-left text-xs text-fg-2">
                      <th scope="col" className="px-2 py-2 font-medium">Category</th>
                      <th scope="col" className="px-2 py-2 font-medium">Cell</th>
                      <th scope="col" className="px-2 py-2 text-right font-medium">Complaints</th>
                      <th scope="col" className="hidden px-2 py-2 font-medium sm:table-cell">Avg severity</th>
                      <th scope="col" className="hidden px-2 py-2 font-medium sm:table-cell">Last reported</th>
                      <th scope="col" className="px-2 py-2"><span className="sr-only">Map</span></th>
                    </tr>
                  </thead>
                  <tbody>
                    {o.hotspots.items.map((h) => (
                      <tr key={hotspotKey(h)} className="border-b border-ink-700/60 last:border-0" data-testid="hotspot-row">
                        <td className="px-2 py-2 text-fg">{CATEGORY_LABEL[h.category]}</td>
                        <td className="px-2 py-2 font-mono text-xs text-fg-2">{h.geo_cell}</td>
                        <td className="px-2 py-2 text-right font-semibold text-fg tabular-nums">{h.complaint_count}</td>
                        <td className="hidden px-2 py-2 sm:table-cell">
                          <span className="inline-flex items-center gap-2">
                            <SeverityDots severity={Math.round(h.avg_severity)} />
                            <span className="text-xs text-fg-2 tabular-nums">{h.avg_severity.toFixed(1)}</span>
                          </span>
                        </td>
                        <td className="hidden px-2 py-2 whitespace-nowrap text-fg-2 sm:table-cell">{formatRelative(h.last_reported_at)}</td>
                        <td className="px-2 py-2 text-right">
                          <Link
                            to={`/map?hotspot=${encodeURIComponent(hotspotKey(h))}`}
                            className="text-[13px] font-medium text-copper-400 hover:text-copper-300"
                            aria-label={`Show ${CATEGORY_LABEL[h.category]} hotspot ${h.geo_cell} on the map`}
                          >
                            Show
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardBody>
          <p className="mt-auto border-t border-ink-700 px-5 py-3.5 text-[13px] leading-5 text-fg-2" data-testid="hotspot-method">
            <strong className="font-medium text-fg">How a hotspot is found.</strong> Db2 groups complaints by category and by a grid cell about{' '}
            {CELL_METERS} m wide, and keeps the groups with {o.hotspots.min_count} or more complaints in the last {o.hotspots.window_days} days.
            It counts reports; it does not predict anything.
          </p>
        </Card>
        <div className="min-w-0 xl:col-span-2">
          <OperationalStatus o={o} userLine={`Signed in as ${me.user_id} (${me.role})`} />
        </div>
      </div>

      <Card data-testid="recent-activity">
        <CardHeader
          title="Recent audited tool activity"
          subtitle="Latest entries from the audit log. The rule-based fallback uses the same audited tools, so these are not necessarily language-model actions."
          actions={<Chip icon={<Activity />}>{o.recent_agent_activity.length} shown</Chip>}
        />
        <CardBody>
          {o.recent_agent_activity.length === 0 ? (
            <p className="py-6 text-center text-sm text-fg-2">No agent runs have been recorded yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <caption className="sr-only">Recent audited tool activity</caption>
                <thead>
                  <tr className="border-b border-ink-700 text-left text-xs text-fg-2">
                    <th scope="col" className="px-1.5 py-2 sm:px-2 font-medium">When</th>
                    <th scope="col" className="px-1.5 py-2 sm:px-2 font-medium">Investigation</th>
                    <th scope="col" className="px-1.5 py-2 sm:px-2 font-medium">Event</th>
                    <th scope="col" className="hidden px-2 py-2 font-medium sm:table-cell">Tool</th>
                    <th scope="col" className="px-1.5 py-2 sm:px-2 font-medium">Result</th>
                    <th scope="col" className="hidden px-2 py-2 font-medium xl:table-cell">Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {o.recent_agent_activity.map((a) => (
                    <tr key={a.audit_id} className="border-b border-ink-700/60 last:border-0" data-testid="activity-row">
                      <td className="px-1.5 py-2 sm:px-2 text-fg-2 sm:whitespace-nowrap">{formatRelative(a.created_at)}</td>
                      <td className="px-1.5 py-2 sm:px-2">
                        {a.investigation_id ? (
                          <Link to={`/investigations/${a.investigation_id}`} className="font-mono text-xs text-copper-400 hover:text-copper-300">
                            #{a.investigation_id}
                          </Link>
                        ) : (
                          '–'
                        )}
                      </td>
                      <td className="px-1.5 py-2 sm:px-2 text-fg">{actionLabel(a.action)}</td>
                      <td className="hidden px-2 py-2 sm:table-cell">{a.tool_name ? <code className="font-mono text-xs text-fg-2">{a.tool_name}</code> : '–'}</td>
                      <td className="px-1.5 py-2 sm:px-2">
                        <span className="inline-flex items-center gap-1 text-xs text-fg-2">
                          {a.success ? <CircleCheck className="size-3.5 text-good" aria-hidden /> : <TriangleAlert className="size-3.5 text-warn" aria-hidden />}
                          <span className="max-sm:sr-only">{a.success ? 'ok' : 'failed'}</span>
                        </span>
                      </td>
                      <td className="hidden max-w-md truncate px-2 py-2 text-fg-2 xl:table-cell" title={a.output_summary ?? undefined}>{a.output_summary ?? ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>

      <p className="flex items-center gap-2 text-xs text-fg-3">
        <Bot className="size-3.5" aria-hidden />
        <ShieldCheck className="size-3.5" aria-hidden />
        Recommendations are only ever proposed by the system. A person must approve or reject each one.
      </p>
    </div>
  )
}
