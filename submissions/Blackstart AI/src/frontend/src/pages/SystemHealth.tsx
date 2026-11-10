import {
  Activity,
  ArrowUpRight,
  Clock,
  Database,
  RefreshCw,
  Server,
  Zap,
} from 'lucide-react';
import type { ReactNode } from 'react';
import { useDashboard } from '../state/DashboardContext';
import { API_BASE_URL, SWAGGER_URL } from '../services/api';
import { formatDateTime, formatTime } from '../lib/format';
import { Chip, RefreshButton, SectionHeader, StatusDot } from '../components/ui/bits';
import { ErrorBlock } from '../components/ui/states';

function StatusCard({
  title,
  icon,
  state,
  children,
  footer,
}: {
  title: string;
  icon: ReactNode;
  state: 'ok' | 'warn' | 'error' | 'idle';
  children: ReactNode;
  footer?: ReactNode;
}) {
  const toneClass =
    state === 'ok'
      ? 'border-emerald-400/30'
      : state === 'error'
        ? 'border-red-500/35'
        : state === 'warn'
          ? 'border-amber-400/30'
          : 'border-white/[0.07]';

  return (
    <div className={`panel flex flex-col p-5 ${toneClass}`}>
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 bg-ink-800 text-slate-400">
            {icon}
          </span>
          <p className="label-cap">{title}</p>
        </div>
        <StatusDot tone={state} pulse={state === 'idle'} />
      </div>
      <div className="mt-4 flex-1">{children}</div>
      {footer ? (
        <div className="mt-4 border-t border-white/[0.06] pt-3">{footer}</div>
      ) : null}
    </div>
  );
}

const endpoints = [
  { method: 'GET', path: '/api/v1/health', purpose: 'FastAPI liveness + version' },
  { method: 'GET', path: '/api/v1/overview', purpose: 'Grid rows from IBM Db2' },
  { method: 'POST', path: '/api/v1/analyze', purpose: 'Five-agent LangGraph run' },
  { method: 'GET', path: '/api/v1/db2/status', purpose: 'IBM Db2 connection probe' },
];

export function SystemHealth() {
  const {
    health,
    db2,
    statusState,
    statusError,
    apiLatencyMs,
    analysis,
    analysisState,
    analysisError,
    lastAnalysisAt,
    analysisDurationMs,
    overviewFetchedAt,
    refreshStatus,
    refreshAll,
  } = useDashboard();

  if (statusState === 'error' && !health && !db2) {
    return (
      <div>
        <SectionHeader
          eyebrow="System health"
          title="System Health"
          description="FastAPI, IBM Db2 and API connectivity status."
        />
        <div className="panel">
          <ErrorBlock
            title="Backend unreachable"
            message={statusError ?? 'Could not reach the backend.'}
            onRetry={() => void refreshAll()}
          />
        </div>
      </div>
    );
  }

  const loading = statusState === 'loading' && !health && !db2;

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="System health"
        title="System Health"
        description="Direct probes of the FastAPI process, the IBM Db2 connector and the analysis pipeline. Status polls every 45 seconds; no synthetic telemetry is shown."
        actions={
          <>
            <RefreshButton />
            <button
              type="button"
              onClick={() => void refreshStatus()}
              className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-ink-800/70 px-3.5 py-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400 transition hover:border-accent/40 hover:text-accent"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Probe status
            </button>
          </>
        }
      />

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatusCard
          title="FastAPI service"
          icon={<Server className="h-4 w-4" />}
          state={
            loading ? 'idle' : health?.status === 'healthy' ? 'ok' : 'error'
          }
          footer={
            <p className="text-[10px] uppercase tracking-[0.12em] text-slate-600">
              GET /api/v1/health
            </p>
          }
        >
          {loading ? (
            <p className="text-xs text-slate-500">Probing…</p>
          ) : health ? (
            <div className="space-y-2">
              <p className="font-display text-xl font-semibold text-emerald-300">
                {health.status}
              </p>
              <p className="text-xs text-slate-500">
                {health.application} · v{health.version}
              </p>
              <p className="mono-num text-[11px] text-slate-600">
                responded in {apiLatencyMs ?? '—'} ms
              </p>
            </div>
          ) : (
            <p className="text-xs text-red-300">{statusError}</p>
          )}
        </StatusCard>

        <StatusCard
          title="IBM Db2 connection"
          icon={<Database className="h-4 w-4" />}
          state={
            loading
              ? 'idle'
              : statusState === 'success' && db2?.connected
                ? 'ok'
                : 'error'
          }
          footer={
            <p className="text-[10px] uppercase tracking-[0.12em] text-slate-600">
              GET /api/v1/db2/status · ibm_db
            </p>
          }
        >
          {loading ? (
            <p className="text-xs text-slate-500">Probing…</p>
          ) : db2 ? (
            <div className="space-y-2">
              <p
                className={`font-display text-xl font-semibold ${
                  db2.connected ? 'text-emerald-300' : 'text-red-300'
                }`}
              >
                {db2.connected ? 'connected' : 'disconnected'}
              </p>
              <p className="break-words text-xs leading-relaxed text-slate-500">
                {db2.message}
              </p>
            </div>
          ) : (
            <p className="text-xs text-red-300">{statusError}</p>
          )}
        </StatusCard>

        <StatusCard
          title="API connectivity"
          icon={<Activity className="h-4 w-4" />}
          state={
            statusState === 'success'
              ? 'ok'
              : statusState === 'error'
                ? 'error'
                : 'idle'
          }
          footer={
            <p className="text-[10px] uppercase tracking-[0.12em] text-slate-600">
              probe round trip {apiLatencyMs ?? '—'} ms
            </p>
          }
        >
          <div className="space-y-2">
            <p
              className={`font-display text-xl font-semibold ${
                statusState === 'success'
                  ? 'text-accent'
                  : statusState === 'error'
                    ? 'text-red-300'
                    : 'text-slate-400'
              }`}
            >
              {statusState === 'success'
                ? 'reachable'
                : statusState === 'error'
                  ? 'unreachable'
                  : 'probing…'}
            </p>
            <p className="break-all font-mono text-[11px] leading-relaxed text-slate-500">
              {API_BASE_URL}
            </p>
            <p className="mono-num text-[11px] text-slate-600">
              round trip {apiLatencyMs ?? '—'} ms
            </p>
          </div>
        </StatusCard>

        <StatusCard
          title="Last successful analysis"
          icon={<Clock className="h-4 w-4" />}
          state={
            analysisState === 'success'
              ? 'ok'
              : analysisState === 'error'
                ? 'error'
                : analysisState === 'running'
                  ? 'warn'
                  : 'idle'
          }
          footer={
            <p className="text-[10px] uppercase tracking-[0.12em] text-slate-600">
              POST /api/v1/analyze
            </p>
          }
        >
          {analysisState === 'running' ? (
            <div className="space-y-2">
              <p className="font-display text-xl font-semibold text-amber-200">
                running…
              </p>
              <p className="text-xs text-slate-500">Pipeline in flight</p>
            </div>
          ) : analysis && lastAnalysisAt ? (
            <div className="space-y-2">
              <p className="font-display text-xl font-semibold text-slate-100">
                {analysis.overall_risk} risk
              </p>
              <p className="mono-num text-[11px] text-slate-500">
                {formatDateTime(lastAnalysisAt)}
              </p>
              <p className="text-[11px] text-slate-600">
                {analysis.agents_executed.length} agents ·{' '}
                {analysisDurationMs ?? '—'} ms · {analysis.execution_mode}
              </p>
            </div>
          ) : analysisState === 'error' ? (
            <div className="space-y-2">
              <p className="font-display text-lg font-semibold text-red-300">
                failed
              </p>
              <p className="text-xs leading-relaxed text-slate-500">
                {analysisError}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              <p className="font-display text-xl font-semibold text-slate-500">
                not run
              </p>
              <p className="text-xs text-slate-600">
                Execute an analysis to populate this card.
              </p>
            </div>
          )}
        </StatusCard>
      </section>

      <section className="grid gap-6 xl:grid-cols-3">
        <div className="panel overflow-hidden xl:col-span-2">
          <div className="border-b border-white/[0.06] px-5 py-4">
            <p className="label-cap text-accent/80">Endpoint reference</p>
            <h2 className="mt-1 font-display text-base font-semibold text-slate-100">
              Backend API surface
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead className="bg-ink-900/60">
                <tr>
                  <th className="whitespace-nowrap px-5 py-3 text-left text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                    Method
                  </th>
                  <th className="whitespace-nowrap px-5 py-3 text-left text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                    Path
                  </th>
                  <th className="whitespace-nowrap px-5 py-3 text-left text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                    Purpose
                  </th>
                </tr>
              </thead>
              <tbody>
                {endpoints.map((endpoint) => (
                  <tr
                    key={endpoint.path}
                    className="border-t border-white/[0.05] transition hover:bg-white/[0.02]"
                  >
                    <td className="px-5 py-3">
                      <span
                        className={`mono-num rounded px-2 py-1 text-[10px] font-bold ${
                          endpoint.method === 'POST'
                            ? 'bg-accent/10 text-accent'
                            : 'bg-emerald-400/10 text-emerald-300'
                        }`}
                      >
                        {endpoint.method}
                      </span>
                    </td>
                    <td className="mono-num whitespace-nowrap px-5 py-3 text-xs text-slate-300">
                      {endpoint.path}
                    </td>
                    <td className="px-5 py-3 text-xs text-slate-500">
                      {endpoint.purpose}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="border-t border-white/[0.06] px-5 py-4">
            <a
              href={SWAGGER_URL}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-lg border border-accent/30 bg-accent/[0.07] px-4 py-2.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-accent transition hover:bg-accent/15"
            >
              Open Swagger UI
              <ArrowUpRight className="h-3.5 w-3.5" />
            </a>
            <span className="ml-3 font-mono text-[11px] text-slate-600">
              {SWAGGER_URL}
            </span>
          </div>
        </div>

        <div className="panel p-5">
          <p className="label-cap text-accent/80">Runtime</p>
          <h2 className="mt-1 font-display text-base font-semibold text-slate-100">
            Environment signals
          </h2>
          <div className="mt-4 space-y-3">
            <div className="flex items-center justify-between gap-3 border-b border-white/[0.05] pb-3">
              <span className="flex items-center gap-2 text-xs text-slate-500">
                <Zap className="h-3.5 w-3.5 text-slate-600" /> Status poll
              </span>
              <span className="mono-num text-xs font-semibold text-slate-300">
                45 s
              </span>
            </div>
            <div className="flex items-center justify-between gap-3 border-b border-white/[0.05] pb-3">
              <span className="flex items-center gap-2 text-xs text-slate-500">
                <Clock className="h-3.5 w-3.5 text-slate-600" /> Last overview fetch
              </span>
              <span className="mono-num text-xs font-semibold text-slate-300">
                {formatTime(overviewFetchedAt)}
              </span>
            </div>
            <div className="flex items-center justify-between gap-3 border-b border-white/[0.05] pb-3">
              <span className="flex items-center gap-2 text-xs text-slate-500">
                <Activity className="h-3.5 w-3.5 text-slate-600" /> Analysis state
              </span>
              <Chip
                className={
                  analysisState === 'success'
                    ? 'border-emerald-400/40 bg-emerald-400/10 text-emerald-300'
                    : analysisState === 'running'
                      ? 'border-accent/40 bg-accent/10 text-accent'
                      : analysisState === 'error'
                        ? 'border-red-500/40 bg-red-500/10 text-red-300'
                        : 'border-slate-500/40 bg-slate-500/10 text-slate-400'
                }
              >
                {analysisState}
              </Chip>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="flex items-center gap-2 text-xs text-slate-500">
                <Database className="h-3.5 w-3.5 text-slate-600" /> Data source
              </span>
              <span className="text-xs font-semibold text-slate-300">
                IBM Db2
              </span>
            </div>
          </div>
          <p className="mt-4 border-t border-white/[0.06] pt-3 text-[11px] leading-relaxed text-slate-600">
            All probes hit real backend endpoints. Values only update when a
            request succeeds — nothing on this page is simulated.
          </p>
        </div>
      </section>
    </div>
  );
}
