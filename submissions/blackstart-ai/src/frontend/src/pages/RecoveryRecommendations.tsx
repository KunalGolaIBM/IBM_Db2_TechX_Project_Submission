import { AlertTriangle, Bot, CheckCircle2, ShieldCheck, UserCheck } from 'lucide-react';
import { useDashboard } from '../state/DashboardContext';
import { formatDateTime } from '../lib/format';
import { EmptyState, ErrorBlock, LoadingBlock } from '../components/ui/states';
import { Chip, RunAnalysisButton, SectionHeader } from '../components/ui/bits';

interface RecommendationMeta {
  priority: string;
  agent: string;
  priorityClass: string;
  agentClass: string;
}

const META_BY_TEXT: Record<string, RecommendationMeta> = {
  'Ask grid operators to inspect high-utilization transmission lines.': {
    priority: 'HIGH',
    agent: 'VOLT',
    priorityClass: 'border-red-500/40 bg-red-500/10 text-red-300',
    agentClass: 'border-accent/35 bg-accent/10 text-accent',
  },
  'Review load distribution and available reserve capacity.': {
    priority: 'MEDIUM',
    agent: 'CASCADE',
    priorityClass: 'border-amber-400/40 bg-amber-400/10 text-amber-200',
    agentClass: 'border-amber-400/35 bg-amber-400/10 text-amber-200',
  },
  'Escalate for immediate human operator assessment.': {
    priority: 'CRITICAL',
    agent: 'GUARDIAN',
    priorityClass: 'border-rose-500/40 bg-rose-500/10 text-rose-300',
    agentClass: 'border-red-500/35 bg-red-500/10 text-red-300',
  },
  'Continue monitoring and validate the latest grid measurements.': {
    priority: 'LOW',
    agent: 'PULSE',
    priorityClass: 'border-sky-400/40 bg-sky-400/10 text-sky-300',
    agentClass: 'border-sky-400/35 bg-sky-400/10 text-sky-300',
  },
  'Do not execute switching or recovery actions automatically.': {
    priority: 'ADVISORY',
    agent: 'BLACKSTART',
    priorityClass: 'border-emerald-400/40 bg-emerald-400/10 text-emerald-300',
    agentClass: 'border-emerald-400/35 bg-emerald-400/10 text-emerald-300',
  },
};

const FALLBACK_META: RecommendationMeta = {
  priority: 'REVIEW',
  agent: 'BLACKSTART',
  priorityClass: 'border-slate-500/40 bg-slate-500/10 text-slate-400',
  agentClass: 'border-emerald-400/35 bg-emerald-400/10 text-emerald-300',
};

export function RecoveryRecommendations() {
  const { analysis, analysisState, analysisError, lastAnalysisAt, analysisDurationMs } =
    useDashboard();

  const running = analysisState === 'running';
  const failed = analysisState === 'error';

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Recovery intelligence"
        title="Recovery Recommendations"
        description="Advisory output of the BLACKSTART agent. Recommendations are returned verbatim by POST /api/v1/analyze and require human operator review before any action."
        actions={
          <>
            <Chip className="border-amber-400/45 bg-amber-400/10 text-amber-200" dot="bg-amber-300">
              Advisory only
            </Chip>
            <RunAnalysisButton />
          </>
        }
      />

      {running ? (
        <div className="panel">
          <LoadingBlock label="BLACKSTART agent generating recommendations…" rows={3} />
        </div>
      ) : null}

      {failed ? (
        <div className="panel">
          <ErrorBlock
            title="Analysis request failed"
            message={analysisError ?? 'POST /api/v1/analyze returned an error.'}
          />
        </div>
      ) : null}

      {!running && !failed && !analysis ? (
        <div className="panel">
          <EmptyState
            icon={<ShieldCheck className="h-5 w-5" />}
            title="No recommendations yet"
            description="Run the five-agent intelligence analysis to generate advisory recovery recommendations from IBM Db2 grid data."
            action={<RunAnalysisButton />}
          />
        </div>
      ) : null}

      {analysis ? (
        <>
          <section className="panel p-5">
            <div className="flex flex-wrap items-center justify-between gap-4">
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
              <div className="text-right">
                <p className="label-cap">Generated</p>
                <p className="mono-num mt-1 text-xs text-slate-300">
                  {formatDateTime(lastAnalysisAt)}
                </p>
                {analysisDurationMs !== null ? (
                  <p className="text-[10px] text-slate-600">
                    {analysisDurationMs} ms round trip
                  </p>
                ) : null}
              </div>
            </div>
          </section>

          <section className="space-y-3">
            {analysis.recommendations.map((recommendation, index) => {
              const meta = META_BY_TEXT[recommendation] ?? FALLBACK_META;
              return (
                <article
                  key={recommendation}
                  className="panel panel-hover relative overflow-hidden p-5"
                >
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
                    <div className="flex items-center gap-4">
                      <span className="mono-num font-display text-2xl font-bold text-slate-700">
                        {String(index + 1).padStart(2, '0')}
                      </span>
                      <span
                        className="hidden h-10 w-px bg-white/10 lg:block"
                        aria-hidden="true"
                      />
                    </div>

                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <Chip className={meta.priorityClass}>{meta.priority}</Chip>
                        <Chip className={meta.agentClass}>
                          <Bot className="mr-1 h-3 w-3" />
                          {meta.agent} agent
                        </Chip>
                        <span className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-amber-200/80">
                          <UserCheck className="h-3.5 w-3.5" />
                          human review required
                        </span>
                      </div>
                      <p className="mt-3 text-[15px] leading-relaxed text-slate-200">
                        {recommendation}
                      </p>
                      <p className="mt-3 flex items-center gap-2 text-[11px] text-slate-600">
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400/70" />
                        Returned verbatim by /api/v1/analyze · advisory only ·
                        executed by no one automatically
                      </p>
                    </div>
                  </div>
                </article>
              );
            })}
          </section>

          <section className="flex items-start gap-3 rounded-xl border border-amber-400/25 bg-amber-400/[0.06] px-4 py-3.5">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />
            <p className="text-xs leading-relaxed text-amber-100/80">
              Priority and agent labels are presentation metadata assigned by the
              dashboard to the recommendations returned by the backend. The
              recommendation text itself is unchanged. This system never executes
              switching, isolation or recovery operations.
            </p>
          </section>
        </>
      ) : null}
    </div>
  );
}
