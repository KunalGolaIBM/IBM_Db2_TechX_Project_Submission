import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  Building2,
  Cable,
  Factory,
  Gauge,
  Info,
  Siren,
} from 'lucide-react';
import { useDashboard } from '../state/DashboardContext';
import {
  average,
  formatDateTime,
  formatMw,
  formatNumber,
  riskStyle,
  toNumber,
  utilizationBand,
  utilizationOf,
} from '../lib/format';
import { MetricCard } from '../components/dashboard/MetricCard';
import { RiskDial } from '../components/dashboard/RiskDial';
import { LineUtilizationChart } from '../components/visualizations/LineUtilizationChart';
import { AgentPipelineStrip } from '../components/agents/AgentPipelineStrip';
import { ErrorBlock, LoadingBlock } from '../components/ui/states';
import { Chip, RunAnalysisButton } from '../components/ui/bits';

export function CommandOverview() {
  const {
    overview,
    overviewState,
    overviewError,
    overviewFetchedAt,
    refreshOverview,
    analysis,
    analysisState,
    lastAnalysisAt,
    analysisDurationMs,
  } = useDashboard();

  const loading = overviewState === 'loading' && !overview;
  const failed = overviewState === 'error' && !overview;

  const stats = useMemo(() => {
    if (!overview) return null;
    const totalCapacity = overview.plants.reduce(
      (sum, plant) => sum + toNumber(plant.capacity_mw),
      0,
    );
    const totalLoad = overview.substations.reduce(
      (sum, substation) => sum + toNumber(substation.load_mw),
      0,
    );
    const utilizations = overview.lines.map((line) =>
      utilizationOf(line.current_load_mw, line.capacity_mw),
    );
    const openIncidents = overview.incidents.filter(
      (incident) => incident.status.toUpperCase() === 'OPEN',
    );
    const onlineSubstations = overview.substations.filter(
      (substation) => substation.status.toUpperCase() === 'ONLINE',
    ).length;
    const onlineLines = overview.lines.filter(
      (line) => line.status.toUpperCase() === 'ONLINE',
    ).length;
    const stressed = utilizations.filter((value) => value >= 80).length;

    return {
      totalCapacity,
      totalLoad,
      avgUtilization: average(utilizations),
      maxUtilization: utilizations.length ? Math.max(...utilizations) : 0,
      openIncidentCount: openIncidents.length,
      onlineSubstations,
      onlineLines,
      stressed,
      lineCount: overview.lines.length,
      plantCount: overview.plants.length,
      substationCount: overview.substations.length,
      incidentCount: overview.incidents.length,
    };
  }, [overview]);

  const risk = analysis?.overall_risk ?? null;
  const riskInfo = riskStyle(risk);
  const running = analysisState === 'running';

  return (
    <div className="space-y-6">
      <section className="panel relative overflow-hidden">
        <div className="grid-lines pointer-events-none absolute inset-0 opacity-70" />
        <div className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-accent/[0.06] blur-3xl" />
        <div className="relative grid gap-8 p-6 sm:p-8 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Chip className="border-accent/35 bg-accent/[0.08] text-accent" dot="bg-accent">
                IBM Db2 · connected demonstration grid data
              </Chip>
              <Chip className="border-emerald-400/30 bg-emerald-400/[0.08] text-emerald-300">
                FastAPI · LangGraph
              </Chip>
              <Chip className="border-amber-400/30 bg-amber-400/[0.08] text-amber-200">
                Advisory only
              </Chip>
            </div>

            <h1 className="mt-5 font-display text-4xl font-bold leading-[1.05] tracking-tight text-slate-50 sm:text-5xl">
              BLACKSTART <span className="text-accent">AI</span>
            </h1>
            <p className="mt-3 font-display text-[11px] font-semibold uppercase tracking-[0.34em] text-accent/90 sm:text-xs">
              Autonomous grid intelligence
            </p>
            <p className="mt-4 max-w-xl text-sm leading-relaxed text-slate-400">
              Five specialized agents read connected demonstration grid rows from IBM Db2,
              assess cascading-failure exposure and return advisory recovery
              recommendations — always under human operator control.
            </p>

            <div className="mt-6 flex flex-wrap items-center gap-3">
              <RunAnalysisButton />
              <Link
                to="/agents"
                className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-ink-800/70 px-4 py-2.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-300 transition hover:border-accent/40 hover:text-accent"
              >
                Inspect agent findings
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
              <span className="text-[11px] text-slate-600">
                POST /api/v1/analyze · no switching executed
              </span>
            </div>
          </div>

          <div className="flex flex-col items-center gap-4 rounded-2xl border border-white/[0.07] bg-ink-900/70 px-6 py-6 lg:min-w-[300px]">
            <div className="flex w-full items-center justify-between">
              <p className="label-cap">Overall grid risk</p>
              <Chip
                className={riskInfo.chipClass}
                dot={riskInfo.dotClass}
              >
                {running ? 'computing' : riskInfo.label}
              </Chip>
            </div>
            <RiskDial
              risk={running ? null : risk}
              caption={
                analysis
                  ? `via /analyze · ${formatDateTime(lastAnalysisAt)}`
                  : 'run analysis to compute'
              }
            />
            <p className="w-full border-t border-white/[0.06] pt-3 text-center text-[11px] leading-relaxed text-slate-500">
              {analysis ? (
                <>
                  Returned by the BLACKSTART agent ·{' '}
                  <span className="font-mono text-slate-400">
                    {analysis.data_source}
                  </span>
                  {analysisDurationMs !== null ? (
                    <span className="text-slate-600"> · {analysisDurationMs} ms</span>
                  ) : null}
                </>
              ) : (
                'No analysis executed yet in this session.'
              )}
            </p>
          </div>
        </div>
      </section>

      {failed ? (
        <section className="panel">
          <ErrorBlock
            title="Grid overview unavailable"
            message={overviewError ?? 'The backend did not return grid data.'}
            onRetry={() => void refreshOverview()}
          />
        </section>
      ) : (
        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <MetricCard
            label="Power plants"
            value={loading ? '' : String(stats?.plantCount ?? 0)}
            sub={
              loading
                ? ''
                : `${formatMw(stats?.totalCapacity ?? 0)} installed capacity`
            }
            icon={Factory}
            tone="cyan"
            loading={loading}
            footer={
              !loading && overview ? (
                <span className="text-[10px] uppercase tracking-[0.12em] text-slate-600">
                  POWER_PLANT · {overview.plants.filter((p) => p.status.toUpperCase() === 'ONLINE').length} online
                </span>
              ) : null
            }
          />
          <MetricCard
            label="Substations"
            value={loading ? '' : String(stats?.substationCount ?? 0)}
            sub={
              loading
                ? ''
                : `${formatMw(stats?.totalLoad ?? 0)} total load · ${stats?.onlineSubstations ?? 0} online`
            }
            icon={Building2}
            tone="sky"
            loading={loading}
            footer={
              !loading && overview ? (
                <span className="text-[10px] uppercase tracking-[0.12em] text-slate-600">
                  SUBSTATION · IBM Db2
                </span>
              ) : null
            }
          />
          <MetricCard
            label="Transmission lines"
            value={loading ? '' : String(stats?.lineCount ?? 0)}
            sub={
              loading
                ? ''
                : `Avg utilization ${formatNumber(stats?.avgUtilization ?? 0, 1)}%`
            }
            icon={Cable}
            tone="emerald"
            loading={loading}
            footer={
              !loading && stats ? (
                <span className="text-[10px] uppercase tracking-[0.12em] text-slate-600">
                  {stats.onlineLines}/{stats.lineCount} in service ·{' '}
                  {stats.stressed} ≥80%
                </span>
              ) : null
            }
          />
          <MetricCard
            label="Open incidents"
            value={loading ? '' : String(stats?.openIncidentCount ?? 0)}
            sub={
              loading
                ? ''
                : `${stats?.incidentCount ?? 0} total in GRID_INCIDENT`
            }
            icon={Siren}
            tone={
              (stats?.openIncidentCount ?? 0) > 0 ? 'red' : 'emerald'
            }
            loading={loading}
            footer={
              !loading && overview ? (
                <span className="text-[10px] uppercase tracking-[0.12em] text-slate-600">
                  source · /api/v1/overview
                </span>
              ) : null
            }
          />
          <MetricCard
            label="Overall grid risk"
            value={loading ? '' : riskInfo.label}
            sub={
              loading
                ? ''
                : analysis
                  ? `Max line utilization ${formatNumber(stats?.maxUtilization ?? 0, 1)}%`
                  : 'Awaiting intelligence analysis'
            }
            icon={Gauge}
            tone={
              risk === 'HIGH' ? 'red' : risk === 'MODERATE' ? 'amber' : risk === 'LOW' ? 'emerald' : 'slate'
            }
            loading={loading}
            footer={
              !loading ? (
                <span className="text-[10px] uppercase tracking-[0.12em] text-slate-600">
                  {analysis
                    ? `analyzed ${formatDateTime(lastAnalysisAt)}`
                    : 'run analysis to populate'}
                </span>
              ) : null
            }
          />
        </section>
      )}

      {loading ? (
        <section className="panel">
          <LoadingBlock rows={5} />
        </section>
      ) : null}

      {!loading && !failed && overview && stats ? (
        <section className="grid gap-6 xl:grid-cols-3">
          <div className="panel p-5 xl:col-span-2">
            <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="label-cap text-accent/80">Transmission stress</p>
                <h2 className="mt-1 font-display text-base font-semibold text-slate-100">
                  Line utilization vs. capacity
                </h2>
              </div>
              <p className="text-[10px] uppercase tracking-[0.12em] text-slate-600">
                {overviewFetchedAt
                  ? `refreshed ${formatDateTime(overviewFetchedAt)}`
                  : 'IBM Db2 · TRANSMISSION_LINE'}
              </p>
            </div>
            <LineUtilizationChart lines={overview.lines} />
          </div>

          <div className="panel p-5">
            <p className="label-cap text-accent/80">Derived grid posture</p>
            <h2 className="mt-1 font-display text-base font-semibold text-slate-100">
              Computed from Db2 rows
            </h2>
            <dl className="mt-4 space-y-3">
              {[
                ['Installed capacity', formatMw(stats.totalCapacity)],
                ['Substation load', formatMw(stats.totalLoad)],
                ['Avg. line utilization', `${formatNumber(stats.avgUtilization, 1)}%`],
                ['Peak line utilization', `${formatNumber(stats.maxUtilization, 1)}%`],
                ['Lines ≥ 80% load', `${stats.stressed} of ${stats.lineCount}`],
                ['Open incidents', `${stats.openIncidentCount} of ${stats.incidentCount}`],
              ].map(([label, value]) => (
                <div
                  key={label}
                  className="flex items-center justify-between gap-3 border-b border-white/[0.05] pb-2.5 last:border-0 last:pb-0"
                >
                  <dt className="text-xs text-slate-500">{label}</dt>
                  <dd className="mono-num text-xs font-semibold text-slate-200">
                    {value}
                  </dd>
                </div>
              ))}
            </dl>
            <div className="mt-4 flex items-start gap-2 rounded-lg border border-white/[0.07] bg-ink-900/60 p-3">
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-500" />
              <p className="text-[11px] leading-relaxed text-slate-500">
                Utilization bands (80/90/100%) are demonstration thresholds for
                visualization only — not official grid operating standards.
              </p>
            </div>
            {analysis ? (
              <div
                className={`mt-3 rounded-lg border p-3 ${utilizationBand(stats.maxUtilization).chipClass}`}
              >
                <p className="text-[11px] leading-relaxed">
                  CASCADE agent classified exposure as{' '}
                  <span className="font-semibold">{analysis.overall_risk}</span>{' '}
                  risk with {analysis.findings.cascade.overloaded_line_count} line(s)
                  at or above 80% utilization.
                </p>
              </div>
            ) : null}
          </div>
        </section>
      ) : null}

      <AgentPipelineStrip />
    </div>
  );
}
