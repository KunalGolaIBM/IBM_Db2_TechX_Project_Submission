import { useMemo } from 'react';
import { AlertTriangle, MapPin, RefreshCw, Siren, Clock } from 'lucide-react';
import { useDashboard } from '../state/DashboardContext';
import {
  formatDateTime,
  severityChip,
  statusChip,
} from '../lib/format';
import { ErrorBlock, EmptyState, LoadingBlock } from '../components/ui/states';
import { Chip, SectionHeader } from '../components/ui/bits';

const SEVERITY_ORDER = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];

export function IncidentIntelligence() {
  const { overview, overviewState, overviewError, refreshAll, refreshOverview } =
    useDashboard();

  const loading = overviewState === 'loading' && !overview;
  const failed = overviewState === 'error' && !overview;

  const incidents = useMemo(() => {
    if (!overview) return [];
    return [...overview.incidents].sort((a, b) => {
      const severityRank = (value: string) => {
        const index = SEVERITY_ORDER.indexOf((value ?? '').toUpperCase());
        return index === -1 ? SEVERITY_ORDER.length : index;
      };
      const rankDiff = severityRank(a.severity) - severityRank(b.severity);
      if (rankDiff !== 0) return rankDiff;
      return b.incident_id - a.incident_id;
    });
  }, [overview]);

  const severityCounts = useMemo(() => {
    const counts = new Map<string, number>();
    incidents.forEach((incident) => {
      const key = (incident.severity ?? 'UNKNOWN').toUpperCase();
      counts.set(key, (counts.get(key) ?? 0) + 1);
    });
    return counts;
  }, [incidents]);

  const openCount = incidents.filter(
    (incident) => incident.status.toUpperCase() === 'OPEN',
  ).length;

  if (failed) {
    return (
      <div>
        <SectionHeader
          eyebrow="Incident intelligence"
          title="Incident Intelligence"
          description="Open incidents detected in IBM Db2 GRID_INCIDENT."
        />
        <div className="panel">
          <ErrorBlock
            title="Incident feed unavailable"
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
        eyebrow="Incident intelligence"
        title="Incident Intelligence"
        description="Incidents are read from the GRID_INCIDENT table via GET /api/v1/overview and are surfaced to the VOLT agent during analysis."
        actions={
          <button
            type="button"
            onClick={() => void refreshOverview()}
            className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-ink-800/70 px-3.5 py-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400 transition hover:border-accent/40 hover:text-accent"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh incidents
          </button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((severity) => {
          const count = severityCounts.get(severity) ?? 0;
          return (
            <div key={severity} className="panel p-4">
              <div className="flex items-center justify-between">
                <Chip
                  className={
                    severity === 'CRITICAL'
                      ? 'border-rose-500/40 bg-rose-500/10 text-rose-300'
                      : severity === 'HIGH'
                        ? 'border-red-500/40 bg-red-500/10 text-red-300'
                        : severity === 'MEDIUM'
                          ? 'border-amber-400/40 bg-amber-400/10 text-amber-200'
                          : 'border-sky-400/40 bg-sky-400/10 text-sky-300'
                  }
                >
                  {severity}
                </Chip>
                <span className="font-display text-2xl font-semibold text-slate-100">
                  {loading ? '–' : count}
                </span>
              </div>
              <p className="mt-3 text-[11px] uppercase tracking-[0.12em] text-slate-600">
                incidents at this severity
              </p>
            </div>
          );
        })}
      </div>

      {loading ? (
        <div className="panel">
          <LoadingBlock label="Reading GRID_INCIDENT from IBM Db2…" rows={5} />
        </div>
      ) : null}

      {overview && !loading ? (
        incidents.length === 0 ? (
          <div className="panel">
            <EmptyState
              icon={<Siren className="h-5 w-5" />}
              title="No incidents recorded"
              description="GRID_INCIDENT currently contains no rows. The VOLT agent will report zero open incidents on the next analysis."
            />
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-[11px] uppercase tracking-[0.14em] text-slate-600">
                {incidents.length} total · {openCount} open
              </p>
              <p className="text-[11px] text-slate-600">
                Sorted by severity, then recency
              </p>
            </div>

            {incidents.map((incident) => {
              const isOpen = incident.status.toUpperCase() === 'OPEN';
              const severity = (incident.severity ?? '').toUpperCase();
              const accentClass =
                severity === 'CRITICAL'
                  ? 'bg-rose-500'
                  : severity === 'HIGH'
                    ? 'bg-red-500'
                    : severity === 'MEDIUM'
                      ? 'bg-amber-400'
                      : 'bg-sky-400';
              return (
                <article
                  key={incident.incident_id}
                  className="panel panel-hover relative overflow-hidden p-5"
                >
                  <span
                    className={`absolute inset-y-0 left-0 w-1 ${accentClass}`}
                    aria-hidden="true"
                  />
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="mono-num text-[11px] font-semibold text-slate-500">
                          #{String(incident.incident_id).padStart(4, '0')}
                        </span>
                        <Chip className={severityChip(incident.severity)}>
                          {incident.severity}
                        </Chip>
                        <Chip
                          className={
                            isOpen
                              ? 'border-red-500/40 bg-red-500/10 text-red-300'
                              : statusChip(incident.status)
                          }
                        >
                          {incident.status}
                        </Chip>
                        <span className="font-display text-[11px] font-semibold uppercase tracking-[0.14em] text-accent/90">
                          {incident.incident_type}
                        </span>
                      </div>

                      <p className="mt-3 text-sm leading-relaxed text-slate-300">
                        {incident.description}
                      </p>

                      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-[11px] text-slate-500">
                        <span className="flex items-center gap-1.5">
                          <MapPin className="h-3.5 w-3.5 text-slate-600" />
                          {incident.location}
                        </span>
                        <span className="flex items-center gap-1.5">
                          <Clock className="h-3.5 w-3.5 text-slate-600" />
                          {formatDateTime(incident.detected_at)}
                        </span>
                      </div>
                    </div>

                    <div className="flex shrink-0 items-center gap-2 lg:flex-col lg:items-end">
                      {isOpen ? (
                        <span className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-red-300">
                          <AlertTriangle className="h-3.5 w-3.5" />
                          Requires review
                        </span>
                      ) : (
                        <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">
                          Closed
                        </span>
                      )}
                      <span className="text-[10px] uppercase tracking-[0.12em] text-slate-600">
                        GRID_INCIDENT
                      </span>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        )
      ) : null}
    </div>
  );
}
