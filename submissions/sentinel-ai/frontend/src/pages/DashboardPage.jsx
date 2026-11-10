import React, { useState } from 'react';
import { 
  Activity, 
  ShieldAlert, 
  AlertTriangle, 
  Lock, 
  Users, 
  Radio, 
  Play, 
  Flame, 
  ChevronRight, 
  ArrowUpRight,
  RefreshCw
} from 'lucide-react';
import MetricCard from '../components/MetricCard';
import AgentFlowVisualizer from '../components/AgentFlowVisualizer';
import MitreBadge from '../components/MitreBadge';

export default function DashboardPage({ 
  stats, 
  incidents = [], 
  alerts = [], 
  onSelectIncident, 
  onTriggerSimulation,
  onInvestigateUser,
  loading,
  onRefresh
}) {
  const [selectedUserToInvestigate, setSelectedUserToInvestigate] = useState('USR-101');
  const [investigating, setInvestigating] = useState(false);

  const handleRunInvestigation = async () => {
    setInvestigating(true);
    try {
      await onInvestigateUser(selectedUserToInvestigate);
    } finally {
      setInvestigating(false);
    }
  };

  const getSeverityBadge = (sev) => {
    switch (sev?.toUpperCase()) {
      case 'CRITICAL':
        return 'bg-rose-950/80 text-rose-300 border-rose-700 glow-crimson';
      case 'HIGH':
        return 'bg-orange-950/80 text-orange-300 border-orange-700 glow-amber';
      case 'MEDIUM':
        return 'bg-amber-950/80 text-amber-300 border-amber-700';
      default:
        return 'bg-emerald-950/80 text-emerald-300 border-emerald-700';
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner: Attack Simulation & Multi-Agent Investigation Trigger */}
      <div className="p-5 rounded-xl bg-gradient-to-r from-[#0d1c38] via-[#0f2347] to-[#0d1a33] border border-[#2563eb]/50 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4 shadow-xl">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <span className="px-2 py-0.5 rounded text-[10px] font-mono-code font-bold bg-cyan-950 text-cyan-400 border border-cyan-800 uppercase">
              AGENTIC CORRELATION ENGINE
            </span>
            <span className="text-xs text-slate-400 font-mono-code">IBM Db2 + watsonx.ai</span>
          </div>
          <h2 className="text-xl font-bold font-tech text-white tracking-wide">
            Multi-Agent Account Compromise Correlation
          </h2>
          <p className="text-xs text-slate-300 max-w-2xl leading-relaxed">
            Correlate 15+ authentication failures, unfamiliar device intrusions, and classified resource queries into explainable intelligence incidents via LangGraph.
          </p>
        </div>

        <div className="flex items-center space-x-3 w-full lg:w-auto">
          {/* Simulation Button */}
          <button
            onClick={onTriggerSimulation}
            disabled={loading}
            className="flex-1 lg:flex-none flex items-center justify-center space-x-2 px-4 py-2.5 rounded-lg bg-gradient-to-r from-rose-600 to-rose-700 hover:from-rose-500 hover:to-rose-600 text-white text-xs font-semibold shadow-lg shadow-rose-900/40 border border-rose-400/40 transition-all hover:scale-[1.02]"
          >
            <Play className="w-4 h-4 fill-current" />
            <span>Simulate Section 8 Attack</span>
          </button>

          {/* Quick Refresh */}
          <button
            onClick={onRefresh}
            className="p-2.5 rounded-lg bg-[#0b1528] border border-[#1a2f55] text-slate-300 hover:text-white hover:border-blue-500 transition-all"
            title="Refresh Telemetry"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-cyan-400' : ''}`} />
          </button>
        </div>
      </div>

      {/* Top 5 SOC Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <MetricCard 
          title="Total Events Logged"
          value={stats?.total_events || 0}
          subtitle="IBM Db2 Central Relational DB"
          icon={Activity}
          color="cyan"
          trend="+18/min"
        />
        <MetricCard 
          title="Auth Failures"
          value={stats?.failed_logins || 0}
          subtitle={`${stats?.successful_logins || 0} successful logons`}
          icon={ShieldAlert}
          color="rose"
          trend={stats?.failed_logins > 10 ? 'SPIKE' : 'Nominal'}
        />
        <MetricCard 
          title="Suspicious Activities"
          value={stats?.suspicious_activities || 0}
          subtitle="Unfamiliar devices & IPs"
          icon={AlertTriangle}
          color="amber"
          trend="Flagged"
        />
        <MetricCard 
          title="Active Incidents"
          value={stats?.active_incidents || 0}
          subtitle={`${stats?.severity_breakdown?.CRITICAL || 0} Critical / ${stats?.severity_breakdown?.HIGH || 0} High`}
          icon={Flame}
          color="rose"
          trend="Correlated"
        />
        <MetricCard 
          title="Pending Approvals"
          value={stats?.pending_approvals || 0}
          subtitle="Human-in-the-Loop Gate"
          icon={Lock}
          color="amber"
          trend="Action Req."
        />
      </div>

      {/* LangGraph Multi-Agent Visualizer */}
      <AgentFlowVisualizer activeStep={5} />

      {/* Two Column Grid: Correlated Incidents & Real-Time Alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Identified Security Incidents */}
        <div className="lg:col-span-2 cyber-card p-5 bg-[#0b1528] border border-[#1a2f55]">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-tech text-base font-bold text-white uppercase tracking-wide flex items-center space-x-2">
                <Flame className="w-4 h-4 text-rose-400" />
                <span>Correlated Security Incidents</span>
              </h3>
              <p className="text-xs text-slate-400">
                Incidents synthesized across multiple security events by the 5 LangGraph agents
              </p>
            </div>
            <span className="text-xs font-mono-code text-slate-400">
              {incidents.length} Records in Db2
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#070d18] border-b border-[#1a2f55] text-[10px] font-mono-code text-slate-400 uppercase">
                <tr>
                  <th className="py-2.5 px-3">Incident ID</th>
                  <th className="py-2.5 px-3">Target Account</th>
                  <th className="py-2.5 px-3">Severity</th>
                  <th className="py-2.5 px-3">Risk Score</th>
                  <th className="py-2.5 px-3">MITRE ATT&CK</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#152642]">
                {incidents.length === 0 ? (
                  <tr>
                    <td colSpan="6" className="py-8 text-center text-slate-500 font-mono-code">
                      No security incidents recorded. Click 'Simulate Section 8 Attack' to trigger.
                    </td>
                  </tr>
                ) : (
                  incidents.map((inc) => (
                    <tr key={inc.incident_id} className="hover:bg-[#0f1f3d] transition-colors">
                      <td className="py-3 px-3 font-mono-code font-bold text-cyan-400">
                        {inc.incident_id}
                      </td>
                      <td className="py-3 px-3">
                        <div className="font-semibold text-slate-200">{inc.full_name || inc.user_id}</div>
                        <div className="text-[10px] font-mono-code text-slate-400">{inc.email || inc.department}</div>
                      </td>
                      <td className="py-3 px-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-mono-code font-bold border ${getSeverityBadge(inc.severity)}`}>
                          {inc.severity}
                        </span>
                      </td>
                      <td className="py-3 px-3 font-mono-code font-bold">
                        <span className={inc.risk_score >= 80 ? 'text-rose-400' : inc.risk_score >= 50 ? 'text-amber-400' : 'text-emerald-400'}>
                          {inc.risk_score}/100
                        </span>
                      </td>
                      <td className="py-3 px-3">
                        <div className="flex flex-wrap gap-1">
                          {(Array.isArray(inc.mitre_technique_ids) ? inc.mitre_technique_ids : []).slice(0, 2).map((tid) => (
                            <MitreBadge key={tid} techniqueId={tid} />
                          ))}
                        </div>
                      </td>
                      <td className="py-3 px-3 text-right">
                        <button
                          onClick={() => onSelectIncident(inc.incident_id)}
                          className="px-2.5 py-1 rounded bg-blue-600/30 hover:bg-blue-600/50 text-blue-300 border border-blue-500/40 text-[11px] font-medium transition-all"
                        >
                          Investigate →
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Col: Live Security Alerts Feed */}
        <div className="cyber-card p-5 bg-[#0b1528] border border-[#1a2f55] flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-tech text-base font-bold text-white uppercase tracking-wide flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                <span>Security Alerts Stream</span>
              </h3>
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
            </div>

            <div className="space-y-2.5 max-h-[380px] overflow-y-auto pr-1">
              {alerts.length === 0 ? (
                <div className="py-8 text-center text-slate-500 font-mono-code text-xs">
                  No active security alerts.
                </div>
              ) : (
                alerts.slice(0, 8).map((alt) => (
                  <div key={alt.alert_id} className="p-2.5 rounded bg-[#070d18] border border-[#152642] text-xs">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono-code text-[10px] text-cyan-400 font-bold">{alt.event_type}</span>
                      <span className={`text-[9px] font-mono-code px-1.5 py-0.2 rounded border ${getSeverityBadge(alt.severity)}`}>
                        {alt.severity}
                      </span>
                    </div>
                    <p className="text-slate-300 text-[11px] leading-tight mb-1">{alt.description}</p>
                    <div className="flex items-center justify-between text-[10px] font-mono-code text-slate-500">
                      <span>{alt.full_name || alt.user_id}</span>
                      <span>{alt.timestamp ? alt.timestamp.slice(11, 19) : ''}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="pt-3 border-t border-[#1a2f55] text-center">
            <span className="text-[10px] text-slate-400 font-mono-code">
              TELEMETRY STREAM CONNECTED TO IBM Db2
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

