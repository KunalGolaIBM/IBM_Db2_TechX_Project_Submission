import React, { useState, useEffect } from 'react';
import { 
  ShieldCheck, AlertTriangle, MapPin, Activity, Plus, 
  RefreshCw, CheckCircle2, AlertCircle, Sparkles, Filter 
} from 'lucide-react';
import { api } from '../services/api';
import { CommunityInsights, CommunityHazard } from '../types';

export const CommunitySafetyDashboard: React.FC = () => {
  const [insights, setInsights] = useState<CommunityInsights | null>(null);
  const [hazards, setHazards] = useState<CommunityHazard[]>([]);
  const [loading, setLoading] = useState(true);

  // Report hazard modal
  const [modalOpen, setModalOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [hazardType, setHazardType] = useState('dark_street');
  const [severity, setSeverity] = useState('medium');
  const [address, setAddress] = useState('');
  const [saving, setSaving] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [insData, hazData] = await Promise.all([
        api.getCommunityInsights(),
        api.getHazards()
      ]);
      setInsights(insData);
      setHazards(hazData);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleReportHazard = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.reportHazard({
        title,
        hazard_type: hazardType,
        severity,
        address,
      });
      setTitle('');
      setAddress('');
      setModalOpen(false);
      await fetchData();
    } catch (err: any) {
      alert("Error reporting hazard: " + err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-slate-900">Community Safety & Hazard Registry</h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Aggregated neighbourhood metrics, environmental hazards, and proactive AI advisories.
          </p>
        </div>
        <button
          onClick={() => setModalOpen(true)}
          className="inline-flex items-center gap-2 bg-teal-600 hover:bg-teal-500 text-white font-bold px-4 py-2.5 rounded-xl shadow-md transition text-xs"
        >
          <Plus className="w-4 h-4" /> Report New Hazard
        </button>
      </div>

      {/* Aggregate Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
          <span className="text-xs font-semibold text-slate-500 block">Total Incidents</span>
          <span className="text-3xl font-extrabold text-slate-900 mt-1 block">{insights?.total_incidents || 0}</span>
          <span className="text-[11px] text-teal-600 font-medium">Audited & Logged</span>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
          <span className="text-xs font-semibold text-slate-500 block">Active Distress Reports</span>
          <span className="text-3xl font-extrabold text-red-600 mt-1 block">{insights?.active_incidents || 0}</span>
          <span className="text-[11px] text-slate-500 font-medium">Under active patrol</span>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
          <span className="text-xs font-semibold text-slate-500 block">Avg Response Time</span>
          <span className="text-3xl font-extrabold text-teal-600 mt-1 block">
            {insights?.average_response_time_minutes != null ? `${insights.average_response_time_minutes.toFixed(1)}m` : '—'}
          </span>
          <span className="text-[11px] text-slate-500 font-medium">Measured: report to acknowledgement</span>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
          <span className="text-xs font-semibold text-slate-500 block">Neighbourhood Health Score</span>
          <span className="text-3xl font-extrabold text-emerald-600 mt-1 block">
            {insights ? `${insights.safety_health_score}/100` : '—'}
          </span>
          <span className="text-[11px] text-emerald-700 font-medium">
            {insights?.sla_breaches ? `${insights.sla_breaches} response target(s) missed` : 'All response targets met'}
          </span>
        </div>
      </div>

      {/* AI Community Advisory Banner */}
      <div className="bg-gradient-to-r from-slate-900 via-slate-850 to-teal-950 text-white rounded-3xl p-6 border border-slate-800 shadow-md flex items-start gap-4">
        <div className="w-10 h-10 rounded-xl bg-teal-600/30 border border-teal-500/40 p-2 flex items-center justify-center shrink-0">
          <Sparkles className="w-6 h-6 text-teal-400" />
        </div>
        <div>
          <span className="text-xs font-bold text-teal-400 uppercase tracking-wider block">
            Community Intelligence Synthesis
          </span>
          <p className="text-sm text-slate-200 mt-1 leading-relaxed">
            {insights?.ai_safety_advisory || "Vigilance index optimal. Patrol routes active across Sector 4. No major violent hazards detected."}
          </p>
        </div>
      </div>

      {/* Response analytics computed in IBM Db2 */}
      {insights && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Response Times by Priority</h2>
                <p className="text-xs text-slate-500">Last {insights.window_days} days · report to first acknowledgement</p>
              </div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-teal-700 bg-teal-50 border border-teal-200 px-2 py-1 rounded-lg">
                {insights.analytics_engine}
              </span>
            </div>
            {insights.response_times.length === 0 ? (
              <p className="text-sm text-slate-500">No incidents in this period yet.</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-slate-500 border-b border-slate-100">
                    <th className="py-2 font-semibold">Priority</th>
                    <th className="py-2 font-semibold text-right">Incidents</th>
                    <th className="py-2 font-semibold text-right">Median</th>
                    <th className="py-2 font-semibold text-right">90th pct</th>
                    <th className="py-2 font-semibold text-right">Target</th>
                  </tr>
                </thead>
                <tbody>
                  {insights.response_times.map((r) => {
                    const fmt = (v: number | null) => (v == null ? '—' : `${v.toFixed(1)}m`);
                    const late = r.p90_ack_minutes != null && r.p90_ack_minutes > r.ack_target_minutes;
                    return (
                      <tr key={r.priority} className="border-b border-slate-50">
                        <td className="py-2 font-mono text-xs font-bold text-slate-700">{r.priority}</td>
                        <td className="py-2 text-right text-slate-700">{r.acknowledged}/{r.incidents}</td>
                        <td className="py-2 text-right text-slate-900 font-semibold">{fmt(r.median_ack_minutes)}</td>
                        <td className={`py-2 text-right font-semibold ${late ? 'text-red-600' : 'text-slate-900'}`}>{fmt(r.p90_ack_minutes)}</td>
                        <td className="py-2 text-right text-slate-500">{fmt(r.ack_target_minutes)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
          <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
            <h2 className="text-lg font-bold text-slate-900">Hotspots</h2>
            <p className="text-xs text-slate-500 mb-3">Locations with repeated reports (RANK over 30 days)</p>
            {insights.hotspots.length === 0 ? (
              <p className="text-sm text-slate-500">No repeated locations yet.</p>
            ) : (
              <ol className="space-y-2">
                {insights.hotspots.map((h) => (
                  <li key={h.location} className="flex items-start justify-between gap-3 text-sm">
                    <span className="flex items-start gap-2 text-slate-800">
                      <span className="w-5 h-5 shrink-0 rounded-full bg-slate-900 text-white text-[11px] font-bold flex items-center justify-center">{h.rank}</span>
                      {h.location}
                    </span>
                    <span className="text-xs text-slate-500 whitespace-nowrap">{h.incidents} reports{h.open_incidents ? ` · ${h.open_incidents} open` : ''}</span>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </div>
      )}

      {/* Hazard Registry */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Active Environmental & Infrastructure Hazards</h2>
            <p className="text-xs text-slate-500">Crowdsourced citizen reports verified by municipal coordinators</p>
          </div>
          <button
            onClick={fetchData}
            className="p-2 text-slate-400 hover:text-slate-600 rounded-lg"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {hazards.length === 0 ? (
          <div className="py-8 text-center text-xs text-slate-500">
            No active hazards logged in this sector.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
            {hazards.map((h) => (
              <div key={h.id} className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h3 className="font-bold text-slate-900 text-sm">{h.title}</h3>
                    <span className="text-[11px] font-semibold text-slate-500 capitalize">
                      {h.hazard_type.replace('_', ' ')}
                    </span>
                  </div>

                  <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${
                    h.status === 'verified' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                  }`}>
                    {h.status === 'verified' ? '✓ Verified' : 'Unverified Report'}
                  </span>
                </div>

                <div className="flex items-center gap-1.5 text-xs text-slate-600">
                  <MapPin className="w-3.5 h-3.5 text-slate-400" />
                  <span>{h.address}</span>
                </div>

                <div className="text-[10px] text-slate-400 pt-1 border-t border-slate-200 flex items-center justify-between">
                  <span>Severity: <strong className="text-slate-700 uppercase">{h.severity}</strong></span>
                  <span>Reported: {new Date(h.created_at).toLocaleDateString()}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-white rounded-3xl p-6 sm:p-8 max-w-md w-full border border-slate-200 shadow-2xl space-y-5">
            <h2 className="text-xl font-bold text-slate-900">Report Community Hazard</h2>
            <form onSubmit={handleReportHazard} className="space-y-4 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Hazard Title</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Broken streetlight on 4th Cross"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-xl focus:ring-2 focus:ring-teal-500 outline-none"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Hazard Type</label>
                <select
                  value={hazardType}
                  onChange={(e) => setHazardType(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-xl focus:ring-2 focus:ring-teal-500 outline-none bg-white"
                >
                  <option value="dark_street">Dark / Malfunctioning Streetlights</option>
                  <option value="road_block">Road Block / Construction Pit</option>
                  <option value="aggressive_animals">Aggressive Stray Animals</option>
                  <option value="electrical">Fallen Wires / Electrical Hazard</option>
                  <option value="flooding">Waterlogging / Sewage Overflow</option>
                </select>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Severity</label>
                <select
                  value={severity}
                  onChange={(e) => setSeverity(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-xl focus:ring-2 focus:ring-teal-500 outline-none bg-white"
                >
                  <option value="low">Low (Minor inconvenience)</option>
                  <option value="medium">Medium (Pedestrian caution required)</option>
                  <option value="high">High (Immediate danger to pedestrians)</option>
                </select>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Address / Landmark</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Corner of 7th Cross and Park Feeder"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-xl focus:ring-2 focus:ring-teal-500 outline-none"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="px-4 py-2 border border-slate-300 rounded-xl text-slate-700 font-semibold hover:bg-slate-50 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-5 py-2 bg-teal-600 hover:bg-teal-500 text-white font-bold rounded-xl shadow-md transition disabled:opacity-50"
                >
                  {saving ? 'Reporting...' : 'Publish Hazard Report'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
};
