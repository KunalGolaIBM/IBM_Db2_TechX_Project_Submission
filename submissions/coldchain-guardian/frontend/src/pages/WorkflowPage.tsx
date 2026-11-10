import { useState } from 'react';
import { api, WorkflowResult } from '../api';
import Badge from '../components/SeverityBadge';
import CrewAnalysisPanel from '../components/CrewAnalysisPanel';
import { Zap, CheckCircle, XCircle } from 'lucide-react';

export default function WorkflowPage() {
  const [readingId, setReadingId] = useState('');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<WorkflowResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    const id = parseInt(readingId);
    if (!id || id <= 0) { setError('Enter a valid reading ID'); return; }
    setRunning(true); setError(null); setResult(null);
    try {
      setResult(await api.runWorkflow(id));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Workflow failed');
    } finally { setRunning(false); }
  };

  const ok = result?.workflow_status === 'SUCCESS';
  const stages = result ? [
    {
      name: 'Monitoring',
      detail: result.temperature_status
        ? `${result.temperature_status}${result.temperature_deviation !== null ? ` · ${result.temperature_deviation}°C` : ''}`
        : '—',
      reached: ok || result.temperature_status !== null,
    },
    {
      name: 'Incident Detection',
      detail: result.incident_id ? `#${result.incident_id}${result.incident_created ? ' created' : ' reused'}` : 'No violation',
      reached: ok || result.incident_id !== null || !result.violation_detected,
    },
    {
      name: 'Risk Assessment',
      detail: result.risk_level ? `${result.risk_level} · ${result.risk_score}/100${result.risk_reused ? ' · reused' : ''}` : '—',
      reached: ok || result.risk_assessment_id !== null,
    },
    {
      name: 'CrewAI Analysis',
      detail: result.crew_status || '—',
      reached: ok || result.crew_status !== null,
    },
    {
      name: 'Recommendations',
      detail: result.recommendations?.length
        ? `${result.recommendations.length} actions${result.recommendations_generated ? '' : ' · existing'}`
        : '—',
      reached: ok || (result.recommendations?.length ?? 0) > 0,
    },
  ] : [];

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Workflow Execution</h1>
        <p className="text-slate-400 text-sm mt-1">Run the LangGraph + CrewAI workflow for a sensor reading</p>
      </div>

      {/* Input */}
      <div className="bg-navy-800 border border-navy-600 rounded-xl p-6">
        <label className="block text-sm font-medium text-slate-300 mb-2">Sensor Reading ID</label>
        <div className="flex gap-3">
          <input
            type="number"
            value={readingId}
            onChange={e => setReadingId(e.target.value)}
            placeholder="e.g. 283"
            className="flex-1 bg-navy-700 border border-navy-500 text-white rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-teal-500"
            onKeyDown={e => e.key === 'Enter' && run()}
          />
          <button
            onClick={run}
            disabled={running || !readingId}
            className="flex items-center gap-2 px-6 py-2.5 bg-teal-600 hover:bg-teal-500 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-60"
          >
            <Zap className={`w-4 h-4 ${running ? 'animate-pulse' : ''}`} />
            {running ? 'Running...' : 'Run Workflow'}
          </button>
        </div>
        {error && <p className="text-red-400 text-sm mt-2">{error}</p>}
      </div>

      {/* Result */}
      {result && (
        <div className="space-y-4">
          {/* Status summary */}
          <div className="bg-navy-800 border border-navy-600 rounded-xl p-5">
            <div className="flex items-center gap-3 mb-4">
              {result.workflow_status === 'SUCCESS'
                ? <CheckCircle className="w-6 h-6 text-green-400" />
                : <XCircle className="w-6 h-6 text-red-400" />
              }
              <h2 className="text-white font-semibold">Workflow {result.workflow_status}</h2>
              <Badge label={result.workflow_status} />
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <p className="text-slate-400 text-xs">Reading ID</p>
                <p className="text-white font-medium">{result.reading_id}</p>
              </div>
              <div>
                <p className="text-slate-400 text-xs">Violation</p>
                <p className={result.violation_detected ? 'text-red-400 font-medium' : 'text-green-400 font-medium'}>
                  {result.violation_detected ? 'Yes' : 'No'}
                </p>
              </div>
              <div>
                <p className="text-slate-400 text-xs">Incident</p>
                <p className="text-white font-medium">{result.incident_id ? `#${result.incident_id}` : 'None'}</p>
              </div>
              <div>
                <p className="text-slate-400 text-xs">Risk Score</p>
                <p className="text-white font-medium">{result.risk_score !== null ? `${result.risk_score}/100` : '—'}</p>
              </div>
            </div>
          </div>

          {/* Stage pipeline */}
          <div className="bg-navy-800 border border-navy-600 rounded-xl p-5">
            <h2 className="text-white font-semibold mb-4">Workflow Stages</h2>
            <div className="grid grid-cols-1 sm:grid-cols-5 gap-3">
              {stages.map((s, i) => (
                <div key={s.name} className="bg-navy-700/50 border border-navy-600 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`w-5 h-5 flex items-center justify-center rounded-full text-xs font-bold ${s.reached ? 'bg-teal-600/30 text-teal-400' : 'bg-navy-600 text-slate-500'}`}>
                      {i + 1}
                    </span>
                    <p className="text-white text-xs font-semibold">{s.name}</p>
                  </div>
                  <p className="text-slate-400 text-xs">{s.detail}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Risk Assessment */}
          {result.risk_level && (
            <div className="bg-navy-800 border border-navy-600 rounded-xl p-5">
              <h2 className="text-white font-semibold mb-3">Risk Assessment</h2>
              <div className="flex items-center gap-3 mb-3">
                <Badge label={result.risk_level} />
                <span className="text-slate-300 text-sm">
                  Score: <strong className="text-white">{result.risk_score}/100</strong>
                </span>
                {result.risk_reused && <Badge label="REUSED" />}
              </div>
              {result.temperature_deviation !== null && (
                <p className="text-slate-400 text-xs mb-3">
                  Temperature status: {result.temperature_status || '—'} · deviation {result.temperature_deviation}°C
                  {result.risk_reused ? ' · existing assessment reused (no duplicate created)' : ''}
                </p>
              )}
              {result.risk_explanation && (
                <p className="text-slate-400 text-sm bg-navy-700 rounded-lg p-3">{result.risk_explanation}</p>
              )}
            </div>
          )}

          {/* Recommendations */}
          {result.recommendations && result.recommendations.length > 0 && (
            <div className="bg-navy-800 border border-navy-600 rounded-xl p-5">
              <h2 className="text-white font-semibold mb-3">
                Generated Recommendations ({result.recommendations.length})
              </h2>
              <div className="space-y-2">
                {result.recommendations.map((rec, i) => (
                  <div key={i} className="flex items-start gap-3 py-2 border-b border-navy-600 last:border-0">
                    <span className="text-teal-400 text-xs font-bold mt-0.5">P{rec.priority}</span>
                    <div>
                      <p className="text-white text-sm">{rec.action}</p>
                      <p className="text-slate-400 text-xs mt-0.5">{rec.justification}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* CrewAI Analysis (structured findings, live or deterministic fallback) */}
          {result.crew_analysis && <CrewAnalysisPanel findings={result.crew_analysis} />}

          {/* Error */}
          {result.error && (
            <div className="bg-red-900/20 border border-red-700/50 rounded-xl p-4">
              <p className="text-red-400 text-sm">{result.error}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
