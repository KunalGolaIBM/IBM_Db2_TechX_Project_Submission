import React, { useEffect, useState } from 'react';
import { 
  Database, 
  AlertTriangle, 
  ShieldCheck, 
  Flame, 
  Gauge, 
  ArrowUpRight 
} from 'lucide-react';
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from 'recharts';
import { MetricCard } from '../components/MetricCard';
import { SeverityBadge } from '../components/SeverityBadge';
import { SentinelApi } from '../services/api';
import { Link } from 'react-router-dom';

export const Dashboard: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const fetchSummary = async () => {
    try {
      const summary = await SentinelApi.getDashboardSummary();
      setData(summary);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSummary();
  }, []);

  if (loading || !data) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[60vh]">
        <div className="flex items-center gap-3 text-cyan-400">
          <span className="w-4 h-4 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin"></span>
          <span>Loading SecOps Dashboard...</span>
        </div>
      </div>
    );
  }

  const { metrics, severity_distribution, recent_events, recent_incidents, pending_approvals } = data;

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      {/* Welcome Banner */}
      <div className="bg-gradient-to-r from-[#132238] via-[#0E1D3B] to-[#132238] border border-[#1E3A5F] rounded-2xl p-6 flex items-center justify-between shadow-xl">
        <div>
          <span className="text-xs font-semibold text-cyan-400 uppercase tracking-widest">Enterprise Database SOC</span>
          <h2 className="text-2xl font-bold text-white mt-1">Db2Sentinel AI Security Command Centre</h2>
          <p className="text-sm text-slate-400 mt-1">
            Real-time telemetry monitoring, automated LangGraph multi-agent triage, and human-governed remediation.
          </p>
        </div>
        <Link
          to="/investigation"
          className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-blue-500/20 transition-all"
        >
          View Active Investigation
          <ArrowUpRight className="w-4 h-4" />
        </Link>
      </div>

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <MetricCard
          title="Total Events"
          value={metrics.total_events}
          subtitle="Stored in IBM Db2"
          icon={Database}
          color="text-cyan-400"
        />
        <MetricCard
          title="Active Alerts"
          value={metrics.total_alerts}
          subtitle="Rule violations"
          icon={AlertTriangle}
          color="text-amber-400"
        />
        <MetricCard
          title="Open Incidents"
          value={metrics.open_incidents}
          subtitle="Multi-event sequences"
          icon={ShieldCheck}
          color="text-blue-400"
        />
        <MetricCard
          title="Critical Threats"
          value={metrics.critical_incidents}
          subtitle="Immediate triage"
          icon={Flame}
          color="text-red-400"
        />
        <MetricCard
          title="Avg Risk Score"
          value={`${metrics.avg_risk_score} / 100`}
          subtitle="Explainable score"
          icon={Gauge}
          color="text-purple-400"
        />
      </div>

      {/* Charts & Triage Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Severity Distribution Chart */}
        <div className="bg-[#132238] border border-[#1E3A5F] rounded-2xl p-6 flex flex-col justify-between shadow-lg">
          <div>
            <h3 className="text-base font-bold text-white">Alert Severity Breakdown</h3>
            <p className="text-xs text-slate-400 mt-0.5">Distribution across evaluated threat levels</p>
          </div>
          <div className="h-48 my-4">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={severity_distribution}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={75}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {severity_distribution.map((entry: any, index: number) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ backgroundColor: '#0D182E', borderColor: '#1E3A5F', borderRadius: '8px' }}
                  itemStyle={{ color: '#FFFFFF' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="grid grid-cols-2 gap-2 pt-2 border-t border-[#1E3A5F]/60">
            {severity_distribution.map((s: any) => (
              <div key={s.name} className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: s.color }}></span>
                <span className="text-xs text-slate-300 font-medium">{s.name}: {s.value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Pending Human Approvals */}
        <div className="lg:col-span-2 bg-[#132238] border border-[#1E3A5F] rounded-2xl p-6 shadow-lg flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-white">Pending Human-in-the-Loop Actions</h3>
                <p className="text-xs text-slate-400 mt-0.5">Containment actions waiting for authorized DBA sign-off</p>
              </div>
              <Link to="/approvals" className="text-xs text-cyan-400 hover:underline">View All</Link>
            </div>

            <div className="mt-4 space-y-3">
              {pending_approvals.length === 0 ? (
                <div className="py-8 text-center text-slate-500 text-sm">
                  No containment actions pending review. All database operations normal.
                </div>
              ) : (
                pending_approvals.map((app: any) => (
                  <div key={app.approval_id} className="p-3.5 bg-[#0D182E] border border-[#1E3A5F] rounded-xl flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono font-bold text-cyan-400">{app.approval_id}</span>
                        <span className="text-xs text-slate-400">• Incident: {app.incident_id}</span>
                      </div>
                      <p className="text-xs text-white font-medium mt-1">{app.proposed_action}</p>
                    </div>
                    <Link
                      to="/approvals"
                      className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold transition-all"
                    >
                      Review
                    </Link>
                  </div>
                ))
              )}
            </div>
          </div>
          <div className="text-[11px] text-slate-500 mt-3 pt-3 border-t border-[#1E3A5F]/60">
            Enforces NIST CSF & Zero-Autonomous-Destruction policies.
          </div>
        </div>
      </div>

      {/* Recent Security Incidents Table */}
      <div className="bg-[#132238] border border-[#1E3A5F] rounded-2xl p-6 shadow-lg">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-bold text-white">Active Security Incidents</h3>
            <p className="text-xs text-slate-400">Correlated multi-event investigation cases</p>
          </div>
          <Link to="/incidents" className="text-xs text-cyan-400 hover:underline">View All Incidents</Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#0D182E] text-slate-400 uppercase font-semibold">
              <tr>
                <th className="p-3 rounded-l-lg">Incident ID</th>
                <th className="p-3">Title</th>
                <th className="p-3">Severity</th>
                <th className="p-3">Risk Score</th>
                <th className="p-3">Assigned Target</th>
                <th className="p-3">Status</th>
                <th className="p-3 rounded-r-lg text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1E3A5F]/40 text-slate-200">
              {recent_incidents.map((inc: any) => (
                <tr key={inc.incident_id} className="hover:bg-[#1C2E4A]/40 transition-colors">
                  <td className="p-3 font-mono text-cyan-400 font-semibold">{inc.incident_id}</td>
                  <td className="p-3 font-medium text-white max-w-xs truncate">{inc.title}</td>
                  <td className="p-3"><SeverityBadge severity={inc.severity} /></td>
                  <td className="p-3 font-bold text-white">{inc.risk_score} / 100</td>
                  <td className="p-3 font-mono text-slate-300">{inc.assigned_to}</td>
                  <td className="p-3">
                    <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
                      {inc.status}
                    </span>
                  </td>
                  <td className="p-3 text-right">
                    <Link
                      to={`/investigation?incident_id=${inc.incident_id}`}
                      className="px-2.5 py-1 bg-[#1C2E4A] hover:bg-cyan-600 hover:text-white rounded text-[11px] font-medium transition-all"
                    >
                      Investigate
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
