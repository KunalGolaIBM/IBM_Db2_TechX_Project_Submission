import React, { useEffect, useState } from 'react';
import { AlertTriangle, ShieldAlert, ArrowRight, Play } from 'lucide-react';
import { SeverityBadge } from '../components/SeverityBadge';
import { SentinelApi } from '../services/api';
import { SecurityAlert } from '../types';
import { useNavigate } from 'react-router-dom';

export const Alerts: React.FC = () => {
  const [alerts, setAlerts] = useState<SecurityAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const fetchAlerts = async () => {
    try {
      const res = await SentinelApi.getAlerts();
      setAlerts(res.alerts || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
  }, []);

  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">Security Alerts</h2>
          <p className="text-xs text-slate-400 mt-1">
            Deterministic security rule breaches and anomaly detections in IBM Db2
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4">
        {loading ? (
          <div className="py-12 text-center text-cyan-400 text-xs">Evaluating alerts...</div>
        ) : alerts.length === 0 ? (
          <div className="bg-[#132238] border border-[#1E3A5F] rounded-2xl p-12 text-center text-slate-500 text-sm">
            No active alerts detected. Generate demo telemetry from header to inspect detection rules.
          </div>
        ) : (
          alerts.map((alrt) => (
            <div
              key={alrt.alert_id}
              className="bg-[#132238] border border-[#1E3A5F] hover:border-cyan-500/40 rounded-2xl p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 transition-all shadow-lg"
            >
              <div className="space-y-1.5 max-w-3xl">
                <div className="flex items-center gap-2.5">
                  <SeverityBadge severity={alrt.severity} />
                  <span className="text-xs font-mono font-bold text-cyan-400">ALERT #{alrt.alert_id}</span>
                  <span className="text-xs text-slate-500">• Event #{alrt.event_id}</span>
                  <span className="text-xs text-slate-500">• {alrt.created_at}</span>
                </div>
                <h3 className="text-base font-bold text-white">{alrt.alert_name}</h3>
                <p className="text-xs text-slate-300 leading-relaxed">{alrt.description}</p>
              </div>

              <div className="flex items-center gap-6 shrink-0 w-full md:w-auto justify-between md:justify-end border-t md:border-t-0 border-[#1E3A5F]/60 pt-3 md:pt-0">
                <div className="text-right">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold block">Risk Score</span>
                  <span className="text-lg font-bold text-white">{alrt.risk_score} / 100</span>
                </div>

                <button
                  onClick={() => navigate('/investigation')}
                  className="flex items-center gap-1.5 px-3.5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold shadow-md shadow-blue-500/20 transition-all"
                >
                  Investigate
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
