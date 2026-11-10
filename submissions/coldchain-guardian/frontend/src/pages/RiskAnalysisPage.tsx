import { useEffect, useState } from 'react';
import { api, Incident, CrewAnalysisResponse } from '../api';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import Badge from '../components/SeverityBadge';
import CrewAnalysisPanel from '../components/CrewAnalysisPanel';
import { Brain } from 'lucide-react';

export default function RiskAnalysisPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [analysis, setAnalysis] = useState<CrewAnalysisResponse | null>(null);
  const [analysing, setAnalysing] = useState(false);
  const [analyseError, setAnalyseError] = useState<string | null>(null);

  useEffect(() => {
    api.getIncidents()
      .then(setIncidents)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false));
  }, []);

  const runAnalysis = async () => {
    if (!selectedId) return;
    setAnalysing(true); setAnalysis(null); setAnalyseError(null);
    try {
      setAnalysis(await api.analyseIncident(selectedId));
    } catch (e: unknown) {
      setAnalyseError(e instanceof Error ? e.message : 'Analysis failed');
    } finally { setAnalysing(false); }
  };

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="p-6"><ErrorMessage message={error} /></div>;

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">AI Risk Analysis</h1>
        <p className="text-slate-400 text-sm mt-1">CrewAI collaborative analysis for incidents</p>
      </div>

      {/* Select incident */}
      <div className="bg-navy-800 border border-navy-600 rounded-xl p-6">
        <label className="block text-sm font-medium text-slate-300 mb-2">Select Incident</label>
        <div className="flex gap-3">
          <select
            value={selectedId ?? ''}
            onChange={e => setSelectedId(Number(e.target.value) || null)}
            className="flex-1 bg-navy-700 border border-navy-500 text-white rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-teal-500"
          >
            <option value="">— Select an incident —</option>
            {incidents.map(inc => (
              <option key={inc.incident_id} value={inc.incident_id}>
                #{inc.incident_id} · Shipment {inc.shipment_id} · {inc.severity} · {inc.status}
              </option>
            ))}
          </select>
          <button
            onClick={runAnalysis}
            disabled={!selectedId || analysing}
            className="flex items-center gap-2 px-6 py-2.5 bg-teal-600 hover:bg-teal-500 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-60"
          >
            <Brain className={`w-4 h-4 ${analysing ? 'animate-pulse' : ''}`} />
            {analysing ? 'Analysing...' : 'Run Analysis'}
          </button>
        </div>
        {incidents.length === 0 && (
          <p className="text-slate-500 text-sm mt-3">No incidents available. Run anomaly detection from the Incidents page first.</p>
        )}
      </div>

      {analyseError && (
        <div className="bg-red-900/20 border border-red-700/50 rounded-lg p-4 text-red-400 text-sm">
          {analyseError}
        </div>
      )}

      {/* Analysis result */}
      {analysis && (
        <div className="space-y-4">
          {/* Deterministic overview */}
          <div className="bg-navy-800 border border-navy-600 rounded-xl p-5">
            <h2 className="text-white font-semibold mb-4">
              Incident #{analysis.incident_id} — Deterministic Risk{analysis.product_name ? ` · ${analysis.product_name}` : ''}
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm mb-4">
              <div>
                <p className="text-slate-400 text-xs mb-1">Severity</p>
                {analysis.severity ? <Badge label={analysis.severity} /> : <span className="text-slate-500">—</span>}
              </div>
              <div>
                <p className="text-slate-400 text-xs mb-1">Risk Level</p>
                {analysis.risk_level ? <Badge label={analysis.risk_level} /> : <span className="text-slate-500">—</span>}
              </div>
              <div>
                <p className="text-slate-400 text-xs">Risk Score</p>
                <p className="text-white font-medium mt-1">
                  {analysis.risk_score !== null ? `${analysis.risk_score}/100` : '—'}
                </p>
              </div>
              <div>
                <p className="text-slate-400 text-xs">Temp Deviation</p>
                <p className="text-white font-medium mt-1">
                  {analysis.temperature_deviation !== null ? `${analysis.temperature_deviation}°C` : '—'}
                </p>
              </div>
              <div>
                <p className="text-slate-400 text-xs mb-1">Product Sensitivity</p>
                {analysis.product_sensitivity ? <Badge label={analysis.product_sensitivity} /> : <span className="text-slate-500">—</span>}
              </div>
            </div>
            {analysis.risk_explanation && (
              <p className="text-slate-400 text-sm bg-navy-700 rounded-lg p-3">{analysis.risk_explanation}</p>
            )}
            <p className="text-slate-500 text-xs mt-3">
              This deterministic score from Db2 is authoritative. CrewAI analysis below is explanatory only and never changes it.
            </p>
          </div>

          {/* Structured crew findings (live or fallback) */}
          {analysis.crew_analysis && <CrewAnalysisPanel findings={analysis.crew_analysis} />}
        </div>
      )}
    </div>
  );
}
