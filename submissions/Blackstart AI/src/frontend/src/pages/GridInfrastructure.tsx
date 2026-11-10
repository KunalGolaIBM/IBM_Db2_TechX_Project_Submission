import { useMemo, useState, type ReactNode } from 'react';
import {
  ArrowRight,
  Building2,
  Cable,
  Factory,
  Info,
} from 'lucide-react';
import { useDashboard } from '../state/DashboardContext';
import {
  formatNumber,
  formatTime,
  statusChip,
  toNumber,
  utilizationBand,
  utilizationOf,
} from '../lib/format';
import { NetworkTopology } from '../components/grid/NetworkTopology';
import { ErrorBlock, LoadingBlock, EmptyState } from '../components/ui/states';
import { Chip, SectionHeader } from '../components/ui/bits';

function TableShell({
  title,
  source,
  icon,
  children,
}: {
  title: string;
  source: string;
  icon: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="panel flex min-w-0 flex-col overflow-hidden">
      <div className="flex items-center justify-between gap-3 border-b border-white/[0.06] px-5 py-4">
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 bg-ink-800 text-accent">
            {icon}
          </span>
          <div>
            <h2 className="font-display text-sm font-semibold text-slate-100">
              {title}
            </h2>
            <p className="text-[10px] uppercase tracking-[0.12em] text-slate-600">
              {source}
            </p>
          </div>
        </div>
      </div>
      <div className="min-w-0 flex-1 overflow-x-auto">{children}</div>
    </div>
  );
}

const thClass =
  'whitespace-nowrap px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500';
const tdClass = 'whitespace-nowrap px-4 py-3 text-sm text-slate-300';

export function GridInfrastructure() {
  const {
    overview,
    overviewState,
    overviewError,
    overviewFetchedAt,
    refreshAll,
  } = useDashboard();
  const [selectedLineId, setSelectedLineId] = useState<number | null>(null);

  const loading = overviewState === 'loading' && !overview;
  const failed = overviewState === 'error' && !overview;

  const nameById = useMemo(() => {
    const map = new Map<number, string>();
    overview?.substations.forEach((substation) =>
      map.set(substation.substation_id, substation.substation_name),
    );
    return map;
  }, [overview]);

  const selectedLine = overview?.lines.find(
    (line) => line.line_id === selectedLineId,
  );

  if (failed) {
    return (
      <div>
        <SectionHeader
          eyebrow="Infrastructure"
          title="Grid Infrastructure"
          description="Plants, substations and transmission assets stored in IBM Db2."
        />
        <div className="panel">
          <ErrorBlock
            title="Infrastructure data unavailable"
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
        eyebrow="Infrastructure"
        title="Grid Infrastructure"
        description="Power plants, substations and transmission lines returned by GET /api/v1/overview. Utilization is calculated as current load ÷ capacity."
        actions={
          <Chip className="border-white/10 bg-ink-800/70 text-slate-400">
            {overviewFetchedAt
              ? `refreshed ${formatTime(overviewFetchedAt)}`
              : overview
                ? 'loaded from Db2'
                : 'connecting…'}
          </Chip>
        }
      />

      <section className="panel p-5">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="label-cap text-accent/80">Network topology</p>
            <h2 className="mt-1 font-display text-base font-semibold text-slate-100">
              Substations &amp; transmission interconnections
            </h2>
          </div>
          <p className="max-w-md text-[11px] leading-relaxed text-slate-600">
            Node positions are a fixed presentation layout; connections, voltage,
            load and utilization are real Db2 values.
          </p>
        </div>

        {loading ? (
          <LoadingBlock label="Mapping network topology…" rows={3} />
        ) : overview ? (
          <NetworkTopology
            substations={overview.substations}
            lines={overview.lines}
            plants={overview.plants}
            selectedLineId={selectedLineId}
            onSelectLine={setSelectedLineId}
          />
        ) : null}

        {selectedLine && overview ? (
          <div className="mt-4 animate-fade-up rounded-xl border border-accent/25 bg-accent/[0.04] p-4">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <Cable className="h-4 w-4 text-accent" />
                  <h3 className="font-display text-sm font-semibold text-slate-100">
                    {selectedLine.line_name}
                  </h3>
                  <Chip className={statusChip(selectedLine.status)}>
                    {selectedLine.status}
                  </Chip>
                </div>
                <p className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-400">
                  {nameById.get(selectedLine.from_substation) ?? '—'}
                  <ArrowRight className="h-3.5 w-3.5 text-accent" />
                  {nameById.get(selectedLine.to_substation) ?? '—'}
                </p>
              </div>
              <div className="flex flex-wrap gap-5">
                <div>
                  <p className="label-cap">Capacity</p>
                  <p className="mono-num mt-1 text-sm font-semibold text-slate-200">
                    {formatNumber(toNumber(selectedLine.capacity_mw), 0)} MW
                  </p>
                </div>
                <div>
                  <p className="label-cap">Current load</p>
                  <p className="mono-num mt-1 text-sm font-semibold text-slate-200">
                    {formatNumber(toNumber(selectedLine.current_load_mw), 0)} MW
                  </p>
                </div>
                <div>
                  <p className="label-cap">Utilization</p>
                  {(() => {
                    const utilization = utilizationOf(
                      selectedLine.current_load_mw,
                      selectedLine.capacity_mw,
                    );
                    const band = utilizationBand(utilization);
                    return (
                      <p
                        className="mono-num mt-1 text-sm font-semibold"
                        style={{ color: band.color }}
                      >
                        {formatNumber(utilization, 1)}% · {band.shortLabel}
                      </p>
                    );
                  })()}
                </div>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setSelectedLineId(null)}
              className="mt-3 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500 transition hover:text-accent"
            >
              Clear selection
            </button>
          </div>
        ) : null}
      </section>

      {loading ? (
        <section className="panel">
          <LoadingBlock label="Loading asset registers…" rows={6} />
        </section>
      ) : null}

      {overview ? (
        <>
          <div className="grid gap-6 2xl:grid-cols-2">
            <TableShell
              title="Power plants"
              source="POWER_PLANT · IBM Db2"
              icon={<Factory className="h-4 w-4" />}
            >
              {overview.plants.length === 0 ? (
                <EmptyState
                  title="No power plants"
                  description="The POWER_PLANT table returned no rows."
                />
              ) : (
                <table className="w-full border-collapse">
                  <thead className="bg-ink-900/60">
                    <tr>
                      <th className={thClass}>Plant</th>
                      <th className={thClass}>Type</th>
                      <th className={`${thClass} text-right`}>Capacity MW</th>
                      <th className={thClass}>Region</th>
                      <th className={thClass}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {overview.plants.map((plant) => (
                      <tr
                        key={plant.plant_id}
                        className="border-t border-white/[0.05] transition hover:bg-white/[0.02]"
                      >
                        <td className={`${tdClass} font-medium text-slate-200`}>
                          {plant.plant_name}
                        </td>
                        <td className={tdClass}>
                          <span className="font-mono text-[11px] uppercase tracking-wider text-accent/90">
                            {plant.plant_type}
                          </span>
                        </td>
                        <td className={`${tdClass} mono-num text-right`}>
                          {formatNumber(toNumber(plant.capacity_mw), 0)}
                        </td>
                        <td className={tdClass}>
                          <span className="text-slate-500">{plant.region}</span>
                        </td>
                        <td className={tdClass}>
                          <Chip className={statusChip(plant.status)}>
                            {plant.status}
                          </Chip>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </TableShell>

            <TableShell
              title="Substations"
              source="SUBSTATION · IBM Db2"
              icon={<Building2 className="h-4 w-4" />}
            >
              {overview.substations.length === 0 ? (
                <EmptyState
                  title="No substations"
                  description="The SUBSTATION table returned no rows."
                />
              ) : (
                <table className="w-full border-collapse">
                  <thead className="bg-ink-900/60">
                    <tr>
                      <th className={thClass}>Substation</th>
                      <th className={`${thClass} text-right`}>Voltage kV</th>
                      <th className={`${thClass} text-right`}>Load MW</th>
                      <th className={thClass}>Region</th>
                      <th className={thClass}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {overview.substations.map((substation) => (
                      <tr
                        key={substation.substation_id}
                        className="border-t border-white/[0.05] transition hover:bg-white/[0.02]"
                      >
                        <td className={`${tdClass} font-medium text-slate-200`}>
                          {substation.substation_name}
                        </td>
                        <td className={`${tdClass} mono-num text-right text-sky-200`}>
                          {formatNumber(toNumber(substation.voltage_kv), 0)}
                        </td>
                        <td className={`${tdClass} mono-num text-right`}>
                          {formatNumber(toNumber(substation.load_mw), 0)}
                        </td>
                        <td className={tdClass}>
                          <span className="text-slate-500">{substation.region}</span>
                        </td>
                        <td className={tdClass}>
                          <Chip className={statusChip(substation.status)}>
                            {substation.status}
                          </Chip>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </TableShell>
          </div>

          <TableShell
            title="Transmission lines"
            source="TRANSMISSION_LINE · utilization = current load ÷ capacity"
            icon={<Cable className="h-4 w-4" />}
          >
            {overview.lines.length === 0 ? (
              <EmptyState
                title="No transmission lines"
                description="The TRANSMISSION_LINE table returned no rows."
              />
            ) : (
              <table className="w-full border-collapse">
                <thead className="bg-ink-900/60">
                  <tr>
                    <th className={thClass}>Line</th>
                    <th className={thClass}>Connected substations</th>
                    <th className={`${thClass} text-right`}>Capacity MW</th>
                    <th className={`${thClass} text-right`}>Load MW</th>
                    <th className={`${thClass} w-[220px]`}>Utilization</th>
                    <th className={thClass}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {overview.lines.map((line) => {
                    const utilization = utilizationOf(
                      line.current_load_mw,
                      line.capacity_mw,
                    );
                    const band = utilizationBand(utilization);
                    return (
                      <tr
                        key={line.line_id}
                        onClick={() =>
                          setSelectedLineId(
                            selectedLineId === line.line_id ? null : line.line_id,
                          )
                        }
                        className={`cursor-pointer border-t border-white/[0.05] transition hover:bg-white/[0.02] ${
                          selectedLineId === line.line_id
                            ? 'bg-accent/[0.05]'
                            : ''
                        }`}
                      >
                        <td className={`${tdClass} font-medium text-slate-200`}>
                          {line.line_name}
                        </td>
                        <td className={tdClass}>
                          <span className="flex items-center gap-1.5 text-slate-400">
                            {nameById.get(line.from_substation) ?? line.from_substation}
                            <ArrowRight className="h-3 w-3 text-slate-600" />
                            {nameById.get(line.to_substation) ?? line.to_substation}
                          </span>
                        </td>
                        <td className={`${tdClass} mono-num text-right`}>
                          {formatNumber(toNumber(line.capacity_mw), 0)}
                        </td>
                        <td className={`${tdClass} mono-num text-right`}>
                          {formatNumber(toNumber(line.current_load_mw), 0)}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-3">
                            <div className="h-1.5 min-w-[90px] flex-1 overflow-hidden rounded-full bg-ink-600">
                              <div
                                className={`h-full rounded-full ${band.barClass}`}
                                style={{
                                  width: `${Math.min(utilization, 100)}%`,
                                }}
                              />
                            </div>
                            <span
                              className="mono-num w-16 text-right text-xs font-semibold"
                              style={{ color: band.color }}
                            >
                              {formatNumber(utilization, 1)}%
                            </span>
                          </div>
                        </td>
                        <td className={tdClass}>
                          <Chip className={statusChip(line.status)}>
                            {line.status}
                          </Chip>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </TableShell>

          <div className="flex items-start gap-2 rounded-xl border border-white/[0.07] bg-ink-850/70 p-4">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" />
            <p className="text-xs leading-relaxed text-slate-500">
              All values are read directly from IBM Db2 through FastAPI — no
              synthetic telemetry is rendered. Band thresholds (80 / 90 / 100%)
              are demonstration visualization thresholds only.
            </p>
          </div>
        </>
      ) : null}
    </div>
  );
}
