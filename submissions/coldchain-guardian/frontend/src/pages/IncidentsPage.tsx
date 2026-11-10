import { useEffect, useState } from 'react';
import { api, Incident } from '../api';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import Badge from '../components/SeverityBadge';
import { RefreshCw } from 'lucide-react';

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [detecting, setDetecting] = useState(false);
  const [detectMsg, setDetectMsg] = useState<string | null>(null);

  const load = async () => {
    setLoading(true); setError(null);
    try { setIncidents(await api.getIncidents()); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : 'Failed to load'); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const detect = async () => {
    setDetecting(true); setDetectMsg(null);
    try {
      const r = await api.detectIncidents() as { incidents_created: number; duplicate_incidents_skipped?: number; violations_found?: number };
      const skipped = r.duplicate_incidents_skipped ?? 0;
      setDetectMsg(`Detection complete: ${r.incidents_created} new incidents created${skipped ? `, ${skipped} duplicates skipped` : ''}.`);
      load();
    } catch (e: unknown) {
      setDetectMsg(`Detection failed: ${e instanceof Error ? e.message : 'Unknown error'}`);
    } finally { setDetecting(false); }
  };

  if (loading) return <LoadingSpinner text="Loading incidents..." />;
  if (error) return <div className="p-6"><ErrorMessage message={error} onRetry={load} /></div>;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Incident Management</h1>
          <p className="text-slate-400 text-sm mt-1">{incidents.length} total incidents</p>
        </div>
        <button
          onClick={detect}
          disabled={detecting}
          className="flex items-center gap-2 px-4 py-2 bg-teal-600 hover:bg-teal-500 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-60"
        >
          <RefreshCw className={`w-4 h-4 ${detecting ? 'animate-spin' : ''}`} />
          {detecting ? 'Detecting...' : 'Detect Anomalies'}
        </button>
      </div>

      {detectMsg && (
        <div className="bg-teal-900/20 border border-teal-700/40 rounded-lg p-3 text-teal-400 text-sm">
          {detectMsg}
        </div>
      )}

      <div className="bg-navy-800 border border-navy-600 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-navy-700/50 border-b border-navy-600">
            <tr>
              {['ID', 'Shipment', 'Type', 'Severity', 'Risk', 'Status', 'Created'].map(h => (
                <th key={h} className="text-left text-xs text-slate-400 uppercase tracking-wide px-4 py-3">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {incidents.length === 0 ? (
              <tr>
                <td colSpan={7} className="text-center text-slate-500 py-12">No incidents found</td>
              </tr>
            ) : incidents.map(inc => (
              <tr key={inc.incident_id} className="border-b border-navy-600/50 hover:bg-navy-700/30 transition-colors">
                <td className="px-4 py-3 text-white font-medium">#{inc.incident_id}</td>
                <td className="px-4 py-3 text-slate-300">{inc.shipment_id}</td>
                <td className="px-4 py-3 text-slate-300 max-w-[220px]">
                  <span className="block truncate">{inc.incident_type}</span>
                  {inc.description && (
                    <span className="block truncate text-slate-500 text-xs mt-0.5" title={inc.description}>{inc.description}</span>
                  )}
                </td>
                <td className="px-4 py-3"><Badge label={inc.severity} /></td>
                <td className="px-4 py-3">
                  {inc.risk_score !== null ? (
                    <div className="flex items-center gap-2">
                      <span className="text-white font-medium">{inc.risk_score}</span>
                      {inc.risk_level && <Badge label={inc.risk_level} />}
                    </div>
                  ) : <span className="text-slate-500">—</span>}
                </td>
                <td className="px-4 py-3"><Badge label={inc.status} /></td>
                <td className="px-4 py-3 text-slate-400 text-xs">
                  {inc.created_at ? new Date(inc.created_at).toLocaleString() : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
