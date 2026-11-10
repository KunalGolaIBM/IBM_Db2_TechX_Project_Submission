import { useMemo } from 'react';
import { AlertTriangle, FlaskConical, Info, Play } from 'lucide-react';
import { useDashboard } from '../state/DashboardContext';
import {
  formatNumber,
  riskStyle,
  toNumber,
  utilizationBand,
  utilizationOf,
} from '../lib/format';
import { EmptyState, ErrorBlock, LoadingBlock } from '../components/ui/states';
import { Chip, RunAnalysisButton, SectionHeader } from '../components/ui/bits';

const THRESHOLDS = [
  { value: 80, label: '80%', color: '#F59E0B' },
  { value: 90, label: '90%', color: '#EF4444' },
  { value: 100, label: '100%', color: '#E11D48' },
];

export function CascadeSimulation() {
  const {
    overview,
    overviewState,
    overviewError,
    analysis,
    analysisState,
    refreshAll,
  } = useDashboard();

  const loading = overviewState === 'loading' && !overview;
  const failed = overviewState === 'error' && !overview;

  const rows = useMemo(() => {
    if (!overview) return [];
    return overview.lines
      .map((line) => {
        const utilization = utilizationOf(line.current_load_mw, line.capacity_mw);
        return {
          id: line.line_id,
          name: line.line_name,
          capacity: toNumber(line.capacity_mw),
          load: toNumber(line.current_load_mw),
          utilization,
          band: utilizationBand(utilization),
          status: line.status,
        };
      })
      .sort((a, b) => b.utilization - a.utilization);
  }, [overview]);

  const distribution = useMemo(() => {
    const counts = { normal: 0, warning: 0, critical: 0, overcapacity: 0 };
    rows.forEach((row) => {
      counts[row.band.key] += 1;
    });
    return counts;
  }, [rows]);

  const cascade = analysis?.findings.cascade;
  const risk = cascade?.risk_level ?? analysis?.overall_risk ?? null;
  const riskInfo = riskStyle(risk);

  if (failed) {
    return (
      <div>
        <SectionHeader
          eyebrow="Cascade simulation"
          title="Cascade Simulation"
          description="Transmission utilization bands and demonstration cascade exposure."
        />
        <div className="panel">
          <ErrorBlock
            title="Utilization data unavailable"
            message={overviewError ?? 'No data returned by /api/v1/overview.'}
            onRetry={() => void refreshAll()}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Cascade simulation"
        title="Cascade Simulation"
        description="Horizontal utilization bars built from capacity and current-load rows. Colors follow demonstration bands — not official grid operating standards."
        actions={
          <>
            <Chip className="border-amber-400/45 bg-amber-400/10 text-amber-200" dot="bg-amber-300">
              Demonstration only
            </Chip>
            <RunAnalysisButton />
          </>
        }
      />

      <div className="flex items-start gap-3 rounded-xl border border-amber-400/25 bg-amber-400/[0.06] px-4 py-3.5">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />
        <p className="text-xs leading-relaxed text-amber-100/80">
          <span className="font-semibold uppercase tracking-[0.12em] text-amber-200">
            Demonstration thresholds ·
          </span>{' '}
          Bands at 80% / 90% / 100% exist purely for visualization in this
          hackathon build. They are not IEEE/NERC limits, not utility operating
          standards, and CASCADE output is labeled{' '}
          <span className="font-mono">DEMONSTRATION_ONLY</span> by the backend.
        </p>
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <section className="panel p-5 xl:col-span-2">
          <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="label-cap text-accent/80">Line loading</p>
              <h2 className="mt-1 font-display text-base font-semibold text-slate-100">
                Transmission utilization bars
              </h2>
            </div>
            <div className="flex flex-wrap gap-3 text-[10px] uppercase tracking-[0.12em] text-slate-500">
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-sm bg-emerald-400" /> normal
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-sm bg-amber-400" /> warning
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-sm bg-red-500" /> critical
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-sm bg-rose-600" /> overcap
              </span>
            </div>
          </div>

          {loading ? (
            <LoadingBlock label="Computing utilization bands…" rows={5} />
          ) : rows.length === 0 ? (
            <EmptyState
              icon={<FlaskConical className="h-5 w-5" />}
              title="No transmission lines"
              description="There are no rows in TRANSMISSION_LINE to visualize."
            />
          ) : (
            <div className="space-y-5">
              <div className="hidden items-center gap-4 sm:flex">
                <div className="w-[190px] shrink-0" />
                <div className="relative h-4 flex-1">
                  {[0, 20, 40, 60, 80, 100].map((tick) => (
                    <span
                      key={tick}
                      className="mono-num absolute top-0 text-[9px] font-medium text-slate-600"
                      style={{
                        left: `${tick}%`,
                        transform:
                          tick === 0
                            ? 'none'
                            : tick === 100
                              ? 'translateX(-100%)'
                              : 'translateX(-50%)',
                      }}
                    >
                      {tick}%
                    </span>
                  ))}
                </div>
                <div className="w-[64px] shrink-0" />
              </div>

              {rows.map((row) => (
                <div
                  key={row.id}
                  className="group flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4"
                >
                  <div className="w-full shrink-0 sm:w-[190px]">
                    <p className="truncate text-xs font-medium text-slate-200">
                      {row.name}
                    </p>
                    <p className="mono-num mt-0.5 text-[10px] text-slate-600">
                      {formatNumber(row.load, 0)} / {formatNumber(row.capacity, 0)}{' '}
                      MW · {row.status}
                    </p>
                  </div>

                  <div className="relative h-8 min-w-0 flex-1 overflow-hidden rounded-lg border border-white/[0.06] bg-ink-900">
                    <div
                      className={`absolute inset-y-0 left-0 ${row.band.barClass} opacity-85 transition-all duration-500`}
                      style={{
                        width: `${Math.min(row.utilization, 100)}%`,
                        boxShadow: `inset 0 0 18px ${row.band.color}55`,
                      }}
                    />
                    {row.utilization > 100 ? (
                      <div
                        className="absolute inset-y-0 right-0 w-2 animate-pulse-dot bg-rose-500"
                        title="Load exceeds rated capacity"
                      />
                    ) : null}
                    {THRESHOLDS.map((threshold) => (
                      <span
                        key={threshold.value}
                        className="absolute inset-y-0 w-px"
                        style={{
                          left: `${threshold.value}%`,
                          background: `${threshold.color}aa`,
                        }}
                      >
                        <span
                          className="absolute -top-px left-0 h-1.5 w-px"
                          style={{ background: threshold.color }}
                        />
                      </span>
                    ))}
                    <span className="absolute inset-y-0 right-3 flex items-center font-mono text-[11px] font-semibold text-white/90 drop-shadow">
                      {formatNumber(row.utilization, 1)}%
                    </span>
                  </div>

                  <div className="flex shrink-0 items-center justify-between gap-2 sm:w-[64px] sm:justify-end">
                    <Chip className={row.band.chipClass}>{row.band.shortLabel}</Chip>
                  </div>
                </div>
              ))}

              <div className="flex items-start gap-2 border-t border-white/[0.06] pt-4">
                <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-600" />
                <p className="text-[11px] leading-relaxed text-slate-600">
                  Bars are clamped at 100% for display; values above 100% pulse on
                  the right edge and are labeled OVERCAP. Source: GET
                  /api/v1/overview.
                </p>
              </div>
            </div>
          )}
        </section>

        <div className="space-y-6">
          <section className="panel p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="label-cap text-accent/80">CASCADE agent</p>
                <h2 className="mt-1 font-display text-base font-semibold text-slate-100">
                  Propagation exposure
                </h2>
              </div>
              <Chip
                className={
                  analysisState === 'success'
                    ? 'border-emerald-400/40 bg-emerald-400/10 text-emerald-300'
                    : 'border-slate-500/40 bg-slate-500/10 text-slate-400'
                }
              >
                {analysisState === 'success' ? 'analyzed' : 'not analyzed'}
              </Chip>
            </div>

            {analysisState === 'running' ? (
              <div className="mt-4">
                <LoadingBlock label="Analyzing cascade exposure…" rows={2} />
              </div>
            ) : cascade ? (
              <div className="mt-4 space-y-4">
                <div className="flex items-center justify-between rounded-xl border border-white/[0.07] bg-ink-900/70 p-4">
                  <div>
                    <p className="label-cap">Overall risk</p>
                    <p
                      className={`mt-1.5 font-display text-3xl font-bold ${riskInfo.textClass}`}
                    >
                      {cascade.risk_level}
                    </p>
                  </div>
                  <span
                    className="h-12 w-12 rounded-full border-4"
                    style={{
                      borderColor: riskInfo.color,
                      boxShadow: `0 0 18px ${riskInfo.color}55`,
                    }}
                  />
                </div>

                <div>
                  <FindingBar
                    label="Lines at or above 80%"
                    value={cascade.overloaded_line_count}
                    total={rows.length}
                  />
                  <FindingBar
                    label="Open incidents (VOLT)"
                    value={analysis?.findings.volt.open_incidents.length ?? 0}
                    total={Math.max(
                      overview?.incidents.length ?? 1,
                      analysis?.findings.volt.open_incidents.length ?? 1,
                    )}
                  />
                </div>

                <div className="rounded-lg border border-amber-400/25 bg-amber-400/[0.06] p-3">
                  <p className="text-[11px] leading-relaxed text-amber-100/75">
                    Simulation mode:{' '}
                    <span className="font-mono font-semibold text-amber-200">
                      {cascade.simulation_mode}
                    </span>{' '}
                    — propagation estimates are illustrative for this submission.
                  </p>
                </div>

                {cascade.at_risk_lines.length > 0 ? (
                  <div>
                    <p className="label-cap mb-2">At-risk lines</p>
                    <ul className="space-y-1.5">
                      {cascade.at_risk_lines.map((line) => (
                        <li
                          key={line.line}
                          className="flex items-center justify-between gap-3 rounded-lg border border-white/[0.06] bg-ink-900/50 px-3 py-2"
                        >
                          <span className="truncate text-xs text-slate-300">
                            {line.line}
                          </span>
                          <span
                            className="mono-num text-xs font-semibold"
                            style={{
                              color: utilizationBand(line.utilization).color,
                            }}
                          >
                            {formatNumber(line.utilization, 1)}%
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="mt-4">
                <EmptyState
                  icon={<Play className="h-5 w-5" />}
                  title="No cascade assessment yet"
                  description="Run the intelligence analysis to have the CASCADE agent classify exposure from the current utilization rows."
                  action={<RunAnalysisButton size="sm" />}
                />
              </div>
            )}
          </section>

          <section className="panel p-5">
            <p className="label-cap text-accent/80">Band distribution</p>
            <h2 className="mt-1 font-display text-base font-semibold text-slate-100">
              Lines by utilization band
            </h2>
            <div className="mt-4 space-y-3">
              {(
                [
                  ['normal', 'Normal · <80%', 'bg-emerald-400', distribution.normal],
                  ['warning', 'Warning · 80–89%', 'bg-amber-400', distribution.warning],
                  ['critical', 'Critical · 90–99%', 'bg-red-500', distribution.critical],
                  [
                    'overcapacity',
                    'Overcapacity · ≥100%',
                    'bg-rose-600',
                    distribution.overcapacity,
                  ],
                ] as const
              ).map(([key, label, barClass, count]) => (
                <div key={key}>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-500">{label}</span>
                    <span className="mono-num font-semibold text-slate-300">
                      {count}
                    </span>
                  </div>
                  <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-ink-700">
                    <div
                      className={`h-full rounded-full ${barClass} transition-all duration-500`}
                      style={{
                        width: `${
                          rows.length ? (count / rows.length) * 100 : 0
                        }%`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
            <p className="mt-4 border-t border-white/[0.06] pt-3 text-[10px] uppercase tracking-[0.12em] text-slate-600">
              {rows.length} lines evaluated · demonstration bands
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}

function FindingBar({
  label,
  value,
  total,
}: {
  label: string;
  value: number;
  total: number;
}) {
  const percent = total ? (value / total) * 100 : 0;
  return (
    <div className="py-2">
      <div className="flex items-center justify-between text-[11px]">
        <span className="text-slate-500">{label}</span>
        <span className="mono-num font-semibold text-slate-300">
          {value} / {total}
        </span>
      </div>
      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-ink-700">
        <div
          className="h-full rounded-full bg-accent transition-all duration-500"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}
