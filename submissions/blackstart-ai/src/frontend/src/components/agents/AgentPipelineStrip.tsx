import { ArrowRight, Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { PIPELINE_AGENTS } from '../../lib/routes';
import { useDashboard } from '../../state/DashboardContext';

export function AgentPipelineStrip() {
  const { analysis, analysisState } = useDashboard();
  const navigate = useNavigate();
  const complete = analysisState === 'success' && analysis !== null;
  const running = analysisState === 'running';

  return (
    <div className="panel overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.06] px-5 py-4">
        <div>
          <p className="label-cap text-accent/80">LangGraph pipeline</p>
          <h2 className="mt-1 font-display text-base font-semibold text-slate-100">
            Five-agent intelligence chain
          </h2>
        </div>
        <button
          type="button"
          onClick={() => navigate('/agents')}
          className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400 transition hover:border-accent/40 hover:text-accent"
        >
          Open agent center
          <ArrowRight className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="px-5 py-4">
        <div className="flex flex-col gap-2 lg:flex-row lg:items-stretch">
          {PIPELINE_AGENTS.map((agent, index) => (
            <div key={agent.key} className="flex flex-1 items-center gap-2">
              <div
                className={`flex min-w-0 flex-1 flex-col rounded-lg border px-3 py-2.5 transition-colors ${
                  complete
                    ? 'border-emerald-400/25 bg-emerald-400/[0.05]'
                    : running
                      ? 'border-accent/30 bg-accent/[0.05]'
                      : 'border-white/[0.07] bg-ink-800/60'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-display text-[12px] font-bold tracking-[0.08em] text-slate-200">
                    {agent.name}
                  </span>
                  {complete ? (
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                  ) : running ? (
                    <Loader2 className="h-3 w-3 animate-spin text-accent" />
                  ) : (
                    <span className="h-1.5 w-1.5 rounded-full bg-slate-600" />
                  )}
                </div>
                <span className="mt-1 truncate text-[10px] uppercase tracking-[0.1em] text-slate-500">
                  {agent.role}
                </span>
              </div>
              {index < PIPELINE_AGENTS.length - 1 ? (
                <ArrowRight
                  className={`hidden h-3.5 w-3.5 shrink-0 lg:block ${
                    complete ? 'text-emerald-400/70' : 'text-slate-700'
                  }`}
                />
              ) : null}
            </div>
          ))}
        </div>

        <p className="mt-4 text-[11px] leading-relaxed text-slate-600">
          {complete
            ? `Last run executed ${analysis?.agents_executed.length ?? 5} agents · execution mode ${analysis?.execution_mode ?? 'ADVISORY_ONLY'} · findings persisted to IBM Db2 AGENT_EVENT.`
            : running
              ? 'Pipeline executing against IBM Db2 grid data…'
              : 'No analysis has been executed in this session. Findings appear after POST /api/v1/analyze completes.'}
        </p>
      </div>
    </div>
  );
}
