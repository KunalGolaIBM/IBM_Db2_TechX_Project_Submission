import { useMemo } from 'react';
import {
  Activity,
  Bot,
  FlaskConical,
  Network,
  ShieldAlert,
  ShieldCheck,
  Zap,
} from 'lucide-react';
import { useDashboard } from '../state/DashboardContext';
import {
  formatDateTime,
  formatNumber,
  riskStyle,
  utilizationBand,
} from '../lib/format';
import {
  AgentCard,
  AgentEmpty,
  FindingRow,
  type AgentCardStatus,
} from '../components/agents/AgentCard';
import { ErrorBlock, LoadingBlock } from '../components/ui/states';
import { Chip, RunAnalysisButton, SectionHeader } from '../components/ui/bits';

export function AgentIntelligence() {
  const {
    overview,
    analysis,
    analysisState,
    analysisError,
    lastAnalysisAt,
    analysisDurationMs,
    refreshAll,
  } = useDashboard();

  const running = analysisState === 'running';
  const complete = analysisState === 'success' && analysis !== null;
  const failed = analysisState === 'error';

  const status: AgentCardStatus = running
    ? 'running'
    : complete
      ? 'complete'
      : failed
        ? 'error'
        : 'idle';

  const substationName = useMemo(() => {
    const map = new Map<number, string>();
    overview?.substations.forEach((substation) =>
      map.set(substation.substation_id, substation.substation_name),
    );
    return map;
  }, [overview]);

  const overviewFailed = !overview && !analysis;

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Five-agent intelligence center"
        title="Agent Intelligence"
        description="A single POST /api/v1/analyze executes the LangGraph pipeline — VOLT → PULSE → CASCADE → GUARDIAN → BLACKSTART — against IBM Db2 rows and persists each event to AGENT_EVENT."
        actions={<RunAnalysisButton />}
      />

      <section className="panel overflow-hidden">
        <div className="grid gap-5 p-5 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Chip
                className={
                  complete
                    ? 'border-emerald-400/40 bg-emerald-400/10 text-emerald-300'
                    : running
                      ? 'border-accent/40 bg-accent/10 text-accent'
                      : failed
                        ? 'border-red-500/40 bg-red-500/10 text-red-300'
                        : 'border-slate-500/40 bg-slate-500/10 text-slate-400'
                }
                dot={
                  complete
                    ? 'bg-emerald-400'
                    : running
                      ? 'bg-accent'
                      : failed
                        ? 'bg-red-400'
                        : 'bg-slate-500'
                }
              >
                {running
                  ? 'pipeline executing'
                  : complete
                    ? 'pipeline complete'
                    : failed
                      ? 'pipeline failed'
                      : 'pipeline idle'}
              </Chip>
              {analysis ? (
                <Chip className="border-amber-400/35 bg-amber-400/10 text-amber-200">
                  {analysis.execution_mode}
                </Chip>
              ) : null}
              {analysis ? (
                <Chip className="border-white/10 bg-ink-800/70 text-slate-400">
                  source · {analysis.data_source}
                </Chip>
              ) : null}
            </div>

            <p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-400">
              {running
                ? 'Agents are reading infrastructure rows and returning findings. This panel updates when the request completes.'
                : complete
                  ? `Executed ${analysis?.agents_executed.length ?? 5} agents in ${analysisDurationMs ?? 0} ms on ${formatDateTime(lastAnalysisAt)}. Every card below shows findings returned by the API — no client-side inference.`
                  : failed
                    ? analysisError ?? 'The analysis request failed.'
                    : 'No analysis has run in this session. Execute the pipeline to populate all five agent cards with API findings.'}
            </p>

            {running ? (
              <div className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-ink-600">
                <div className="h-full w-1/3 animate-sweep rounded-full bg-accent" />
              </div>
            ) : null}
          </div>

          <div className="flex flex-col items-start gap-2 lg:items-end">
            <RunAnalysisButton />
            <p className="text-[10px] uppercase tracking-[0.12em] text-slate-600">
              advisory · human review required
            </p>
          </div>
        </div>
      </section>

      {running ? (
        <section className="panel">
          <LoadingBlock label="LangGraph pipeline executing…" rows={4} />
        </section>
      ) : null}

      {failed && !running ? (
        <section className="panel">
          <ErrorBlock
            title="Analysis request failed"
            message={analysisError ?? 'POST /api/v1/analyze returned an error.'}
          />
        </section>
      ) : null}

      {overviewFailed && !running && !complete && !failed ? (
        <section className="panel">
          <ErrorBlock
            title="Grid context unavailable"
            message="The overview request failed, so agent cards cannot display supporting Db2 context."
            onRetry={() => void refreshAll()}
          />
        </section>
      ) : null}

      <section className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        <AgentCard
          name="VOLT"
          role="Incident Intelligence"
          description="Detects open incidents and overloaded transmission lines from Db2 rows."
          icon={Zap}
          accent="cyan"
          status={status}
        >
          {!analysis ? (
            <AgentEmpty message="VOLT findings appear after an analysis run: open incidents from GRID_INCIDENT and any line at or above 80% utilization." />
          ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg border border-white/[0.07] bg-ink-900/60 p-3">
                  <p className="label-cap">Open incidents</p>
                  <p className="mt-1.5 font-display text-2xl font-semibold text-red-300">
                    {analysis.findings.volt.open_incidents.length}
                  </p>
                </div>
                <div className="rounded-lg border border-white/[0.07] bg-ink-900/60 p-3">
                  <p className="label-cap">Lines ≥ 80%</p>
                  <p className="mt-1.5 font-display text-2xl font-semibold text-amber-200">
                    {analysis.findings.volt.overloaded_lines.length}
                  </p>
                </div>
              </div>

              <div>
                <p className="label-cap mb-1">Incident detection</p>
                {analysis.findings.volt.open_incidents.length === 0 ? (
                  <AgentEmpty message="No open incidents detected." />
                ) : (
                  analysis.findings.volt.open_incidents.map((incident) => (
                    <div
                      key={incident.incident_id}
                      className="flex items-start justify-between gap-3 border-b border-white/[0.05] py-2.5 last:border-0"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-xs font-medium text-slate-300">
                          {incident.incident_type} · {incident.location}
                        </p>
                        <p className="mt-0.5 truncate text-[11px] text-slate-600">
                          {incident.description}
                        </p>
                      </div>
                      <Chip className="border-red-500/40 bg-red-500/10 text-red-300">
                        {incident.severity}
                      </Chip>
                    </div>
                  ))
                )}
              </div>

              <div>
                <p className="label-cap mb-1">Overload detection</p>
                {analysis.findings.volt.overloaded_lines.length === 0 ? (
                  <AgentEmpty message="All transmission lines are below the 80% demonstration threshold." />
                ) : (
                  analysis.findings.volt.overloaded_lines.map((line) => {
                    const band = utilizationBand(line.utilization);
                    const tone =
                      band.key === 'overcapacity'
                        ? 'text-rose-400'
                        : band.key === 'critical'
                          ? 'text-red-300'
                          : band.key === 'warning'
                            ? 'text-amber-200'
                            : 'text-emerald-300';
                    return (
                      <FindingRow
                        key={line.line}
                        label={line.line}
                        value={`${formatNumber(line.utilization, 1)}%`}
                        tone={tone}
                      />
                    );
                  })
                )}
              </div>
            </div>
          )}
        </AgentCard>

        <AgentCard
          name="PULSE"
          role="Grid Topology Intelligence"
          description="Analyzes substations and maps transmission connections across the network."
          icon={Network}
          accent="sky"
          status={status}
        >
          {!analysis ? (
            <AgentEmpty message="PULSE findings appear after an analysis run: substation counts, line counts and the full connection map." />
          ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-3">
                <div className="rounded-lg border border-white/[0.07] bg-ink-900/60 p-3">
                  <p className="label-cap">Substations</p>
                  <p className="mt-1.5 font-display text-2xl font-semibold text-sky-200">
                    {analysis.findings.pulse.substation_count}
                  </p>
                </div>
                <div className="rounded-lg border border-white/[0.07] bg-ink-900/60 p-3">
                  <p className="label-cap">Lines</p>
                  <p className="mt-1.5 font-display text-2xl font-semibold text-sky-200">
                    {analysis.findings.pulse.transmission_line_count}
                  </p>
                </div>
                <div className="rounded-lg border border-white/[0.07] bg-ink-900/60 p-3">
                  <p className="label-cap">Online</p>
                  <p className="mt-1.5 font-display text-2xl font-semibold text-emerald-300">
                    {analysis.findings.pulse.online_substations}
                  </p>
                </div>
              </div>

              <div>
                <p className="label-cap mb-1">Connection map</p>
                <div className="space-y-1.5">
                  {analysis.findings.pulse.line_connections.map((connection) => (
                    <div
                      key={connection.line}
                      className="flex items-center justify-between gap-3 rounded-lg border border-white/[0.06] bg-ink-900/50 px-3 py-2.5"
                    >
                      <span className="truncate text-xs font-medium text-slate-300">
                        {connection.line}
                      </span>
                      <span className="mono-num shrink-0 text-[11px] text-slate-500">
                        {substationName.get(connection.from) ?? connection.from} →{' '}
                        {substationName.get(connection.to) ?? connection.to}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </AgentCard>

        <AgentCard
          name="CASCADE"
          role="Failure Propagation Intelligence"
          description="Estimates cascading-failure exposure from overloaded transmission paths."
          icon={FlaskConical}
          accent="amber"
          status={status}
        >
          {!analysis ? (
            <AgentEmpty message="CASCADE findings appear after an analysis run: overall risk level and the lines carried forward by VOLT." />
          ) : (
            <div className="space-y-4">
              <div className="flex items-center justify-between gap-3 rounded-lg border border-amber-400/25 bg-amber-400/[0.06] p-3">
                <div>
                  <p className="label-cap">Cascade risk</p>
                  <p
                    className={`mt-1 font-display text-2xl font-semibold ${riskStyle(analysis.findings.cascade.risk_level).textClass}`}
                  >
                    {analysis.findings.cascade.risk_level}
                  </p>
                </div>
                <Chip className="border-amber-400/40 bg-amber-400/10 text-amber-200">
                  {analysis.findings.cascade.simulation_mode.replace('_', ' ')}
                </Chip>
              </div>

              <div className="rounded-lg border border-amber-400/20 bg-ink-900/60 p-3">
                <p className="text-[11px] leading-relaxed text-amber-100/70">
                  <span className="font-semibold uppercase tracking-[0.12em] text-amber-200">
                    Demonstration only ·
                  </span>{' '}
                  This panel visualizes utilization-derived exposure for the
                  hackathon demo. It is not an operational grid simulation and
                  does not model protection schemes.
                </p>
              </div>

              <div>
                <p className="label-cap mb-1">
                  At-risk lines ({analysis.findings.cascade.overloaded_line_count})
                </p>
                {analysis.findings.cascade.at_risk_lines.length === 0 ? (
                  <AgentEmpty message="No lines carried forward at or above the 80% threshold." />
                ) : (
                  analysis.findings.cascade.at_risk_lines.map((line) => {
                    const band = utilizationBand(line.utilization);
                    return (
                      <div key={line.line} className="py-2.5 last:pb-0">
                        <div className="flex items-center justify-between gap-3">
                          <span className="truncate text-xs text-slate-300">
                            {line.line}
                          </span>
                          <span
                            className="mono-num text-xs font-semibold"
                            style={{ color: band.color }}
                          >
                            {formatNumber(line.utilization, 1)}%
                          </span>
                        </div>
                        <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-ink-600">
                          <div
                            className={`h-full rounded-full ${band.barClass}`}
                            style={{ width: `${Math.min(line.utilization, 100)}%` }}
                          />
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          )}
        </AgentCard>

        <AgentCard
          name="GUARDIAN"
          role="Infrastructure Impact Intelligence"
          description="Translates risk exposure into operational impact and alerting guidance."
          icon={ShieldAlert}
          accent="red"
          status={status}
        >
          {!analysis ? (
            <AgentEmpty message="GUARDIAN findings appear after an analysis run: critical alert state, open incident count and the impact assessment." />
          ) : (
            <div className="space-y-4">
              {analysis.findings.guardian.critical_alert ? (
                <div className="flex items-start gap-3 rounded-lg border border-red-500/35 bg-red-500/[0.08] p-3">
                  <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-red-300" />
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.12em] text-red-200">
                      Critical alert active
                    </p>
                    <p className="mt-1 text-[11px] leading-relaxed text-red-100/70">
                      Infrastructure impact assessment requires immediate
                      operator attention.
                    </p>
                  </div>
                </div>
              ) : (
                <div className="rounded-lg border border-emerald-400/25 bg-emerald-400/[0.06] p-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-emerald-300">
                    No critical alert
                  </p>
                  <p className="mt-1 text-[11px] leading-relaxed text-emerald-100/60">
                    Continue monitoring operational thresholds.
                  </p>
                </div>
              )}

              <div>
                <FindingRow
                  label="Risk level"
                  value={analysis.findings.guardian.risk_level}
                  tone={riskStyle(analysis.findings.guardian.risk_level).textClass}
                />
                <FindingRow
                  label="Open incidents"
                  value={String(analysis.findings.guardian.open_incident_count)}
                  tone="text-red-300"
                />
                <FindingRow
                  label="Assessment source"
                  value="/api/v1/analyze"
                  tone="text-slate-400"
                />
              </div>

              <div className="rounded-lg border-l-2 border-red-400/60 bg-ink-900/60 p-3">
                <p className="label-cap mb-1">Assessment</p>
                <p className="text-sm leading-relaxed text-slate-300">
                  {analysis.findings.guardian.assessment}
                </p>
              </div>
            </div>
          )}
        </AgentCard>

        <AgentCard
          name="BLACKSTART"
          role="Recovery Intelligence"
          description="Generates advisory recovery recommendations for human operators."
          icon={ShieldCheck}
          accent="emerald"
          status={status}
          className="md:col-span-2 xl:col-span-2"
        >
          {!analysis ? (
            <AgentEmpty message="BLACKSTART findings appear after an analysis run: prioritized advisory recommendations under ADVISORY_ONLY execution mode." />
          ) : (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <Chip className="border-emerald-400/40 bg-emerald-400/10 text-emerald-300">
                  {analysis.execution_mode}
                </Chip>
                <Chip className="border-amber-400/35 bg-amber-400/10 text-amber-200">
                  Human review required
                </Chip>
                <Chip className="border-white/10 bg-ink-800/70 text-slate-400">
                  {analysis.recommendations.length} recommendations
                </Chip>
                <Chip className="border-white/10 bg-ink-800/70 text-slate-400">
                  {analysis.agents_executed.join(' → ')}
                </Chip>
              </div>

              <ol className="space-y-2">
                {analysis.recommendations.map((recommendation, index) => (
                  <li
                    key={recommendation}
                    className="flex items-start gap-3 rounded-lg border border-white/[0.06] bg-ink-900/50 px-3.5 py-3"
                  >
                    <span className="mono-num mt-0.5 text-[11px] font-semibold text-emerald-400">
                      {String(index + 1).padStart(2, '0')}
                    </span>
                    <span className="text-sm leading-relaxed text-slate-300">
                      {recommendation}
                    </span>
                  </li>
                ))}
              </ol>

              <p className="flex items-center gap-2 text-[11px] text-slate-600">
                <Activity className="h-3.5 w-3.5 text-slate-600" />
                Recommendations are returned verbatim by the BLACKSTART agent.
                No switching, isolation or recovery action is executed.
              </p>
            </div>
          )}
        </AgentCard>
      </section>

      <section className="panel flex flex-wrap items-center gap-4 px-5 py-4">
        <Bot className="h-4 w-4 text-accent" />
        <p className="text-[11px] leading-relaxed text-slate-500">
          Architecture: FastAPI → LangGraph StateGraph → five agent nodes →
          IBM Db2 AGENT_EVENT insert. Findings shown here are the exact JSON
          returned by the backend.
        </p>
        <span className="ml-auto text-[10px] uppercase tracking-[0.14em] text-slate-600">
          {complete ? `run ${formatDateTime(lastAnalysisAt)}` : 'no run yet'}
        </span>
      </section>
    </div>
  );
}
