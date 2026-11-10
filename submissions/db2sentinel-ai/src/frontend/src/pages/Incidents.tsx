import React, { useEffect, useState } from 'react';
import { FileSearch, ArrowRight, ShieldCheck, Clock } from 'lucide-react';
import { SeverityBadge } from '../components/SeverityBadge';
import { SentinelApi } from '../services/api';
import { SecurityIncident } from '../types';
import { useNavigate } from 'react-router-dom';

export const Incidents: React.FC = () => {
  const [incidents, setIncidents] = useState<SecurityIncident[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const fetchIncidents = async () => {
    try {
      const res = await SentinelApi.getIncidents();
      setIncidents(res.incidents || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIncidents();
  }, []);

  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto">
      <div>
        <h2 className="text-2xl font-bold text-white">Security Incidents</h2>
        <p className="text-xs text-slate-400 mt-1">
          Correlated multi-event investigation cases triageable by LangGraph agents
        </p>
      </div>

      <div className="space-y-4">
        {loading ? (
          <div className="py-12 text-center text-cyan-400 text-xs">Loading incident records...</div>
        ) : incidents.length === 0 ? (
          <div className="bg-[#132238] border border-[#1E3A5F] rounded-2xl p-12 text-center text-slate-500 text-sm">
            No incidents found. Run detection from the top bar to synthesize alerts into incident cases.
          </div>
        ) : (
          incidents.map((inc) => (
            <div
              key={inc.incident_id}
              className="bg-[#132238] border border-[#1E3A5F] rounded-2xl p-6 shadow-lg hover:border-cyan-500/40 transition-all space-y-4"
            >
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-mono font-bold text-cyan-400">{inc.incident_id}</span>
                    <SeverityBadge severity={inc.severity} />
                    <span className="text-xs px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 font-semibold">
                      {inc.status}
                    </span>
                  </div>
                  <h3 className="text-lg font-bold text-white">{inc.title}</h3>
                </div>

                <div className="flex items-center gap-4">
                  <div className="text-right">
                    <span className="text-[10px] text-slate-400 uppercase font-semibold block">Calculated Risk</span>
                    <span className="text-xl font-bold text-white">{inc.risk_score} / 100</span>
                  </div>
                  <button
                    onClick={() => navigate(`/investigation?incident_id=${inc.incident_id}`)}
                    className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-cyan-500/10 transition-all"
                  >
                    View Agent Dossier
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <p className="text-xs text-slate-300 leading-relaxed border-t border-[#1E3A5F]/60 pt-3">
                {inc.description}
              </p>

              {inc.ai_summary && (
                <div className="p-4 bg-[#0D182E] border border-[#1E3A5F] rounded-xl text-xs space-y-2">
                  <div className="flex items-center gap-2 text-cyan-400 font-semibold">
                    <ShieldCheck className="w-4 h-4" />
                    <span>LangGraph Investigation Summary:</span>
                  </div>
                  <p className="text-slate-300 leading-relaxed whitespace-pre-line font-mono text-[11px]">
                    {inc.ai_summary}
                  </p>
                </div>
              )}

              <div className="flex items-center gap-6 text-[11px] text-slate-500 pt-2">
                <span>Target: <strong className="text-slate-300 font-mono">{inc.assigned_to}</strong></span>
                <span>Created: {inc.created_at}</span>
                <span>Updated: {inc.updated_at}</span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
