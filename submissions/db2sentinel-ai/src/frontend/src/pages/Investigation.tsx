import React, { useState } from 'react';
import { 
  Workflow, 
  Play, 
  CheckCircle2, 
  ShieldAlert, 
  FileText, 
  Activity, 
  Lock, 
  ArrowRight,
  Database
} from 'lucide-react';
import { SentinelApi } from '../services/api';
import { useNavigate } from 'react-router-dom';

export const Investigation: React.FC = () => {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<any>(null);
  const navigate = useNavigate();

  const handleRunInvestigation = async () => {
    setRunning(true);
    try {
      const data = await SentinelApi.investigateIncident('INC-2026-0884');
      setResult(data);
    } catch (err) {
      console.error(err);
    } finally {
      setRunning(false);
    }
  };

  const agents = [
    {
      name: '1. Detection Agent',
      role: 'Rule Classification & Scoping',
      status: result ? 'COMPLETED' : 'STANDBY',
      output: result ? 'Flagged compound violations: Brute force, sensitive financial access, and catalog reconnaissance.' : 'Waiting for trigger...'
    },
    {
      name: '2. Evidence Agent',
      role: 'Chronological Telemetry Correlation',
      status: result ? 'COMPLETED' : 'STANDBY',
      output: result ? 'Correlated 11 normalized events from IBM Db2; reconstructed user session and confirmed 28,400 row fetch.' : 'Waiting for trigger...'
    },
    {
      name: '3. Investigation Agent',
      role: 'Hypothesis Formulation & MITRE Mapping',
      status: result ? 'COMPLETED' : 'STANDBY',
      output: result ? `Mapped observed techniques: ${result.mitre_tactics?.join(', ')}.` : 'Waiting for trigger...'
    },
    {
      name: '4. Risk Assessment Agent',
      role: 'Transparent 4-Factor Mathematical Scoring',
      status: result ? 'COMPLETED' : 'STANDBY',
      output: result ? `Calculated Score: ${result.risk_evaluation?.risk_score} / 100 [${result.risk_evaluation?.severity}]. Formula: ${result.risk_evaluation?.formula}` : 'Waiting for trigger...'
    },
    {
      name: '5. Response Recommendation Agent',
      role: 'Containment Action Formulation',
      status: result ? 'AWAITING APPROVAL' : 'STANDBY',
      output: result ? 'Proposed terminating active Db2 session and revoking CONNECT authority pending human DBA approval.' : 'Waiting for trigger...'
    },
    {
      name: '6. Report Agent',
      role: 'Executive Dossier Generation',
      status: result ? 'COMPLETED' : 'STANDBY',
      output: result ? 'Generated executive report with immutable Db2 event_id citations and audit hashes.' : 'Waiting for trigger...'
    }
  ];

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      {/* Title Banner */}
      <div className="bg-[#132238] border border-[#1E3A5F] rounded-2xl p-6 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-xl">
        <div>
          <span className="text-xs font-semibold text-purple-400 uppercase tracking-widest">LangGraph Multi-Agent Orchestrator</span>
          <h2 className="text-2xl font-bold text-white mt-1">AI Incident Investigation Engine</h2>
          <p className="text-xs text-slate-400 mt-1">
            Coordinated StateGraph workflow: 6 specialized agents, immutable Db2 evidence, and human approval interrupts.
          </p>
        </div>

        <button
          onClick={handleRunInvestigation}
          disabled={running}
          className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white rounded-xl text-xs font-bold shadow-lg shadow-purple-500/20 transition-all disabled:opacity-50"
        >
          <Play className="w-4 h-4 fill-current" />
          {running ? 'Orchestrating Agents...' : 'Execute LangGraph Investigation'}
        </button>
      </div>

      {/* Target Case Info */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-4 bg-[#132238] border border-[#1E3A5F] rounded-xl">
          <span className="text-[10px] text-slate-400 uppercase font-semibold block">Target Case</span>
          <span className="text-sm font-mono font-bold text-cyan-400">INC-2026-0884</span>
        </div>
        <div className="p-4 bg-[#132238] border border-[#1E3A5F] rounded-xl">
          <span className="text-[10px] text-slate-400 uppercase font-semibold block">Compromised User</span>
          <span className="text-sm font-mono font-bold text-white">REPORT_USER</span>
        </div>
        <div className="p-4 bg-[#132238] border border-[#1E3A5F] rounded-xl">
          <span className="text-[10px] text-slate-400 uppercase font-semibold block">Attacker IP</span>
          <span className="text-sm font-mono font-bold text-rose-400">198.51.100.44</span>
        </div>
        <div className="p-4 bg-[#132238] border border-[#1E3A5F] rounded-xl">
          <span className="text-[10px] text-slate-400 uppercase font-semibold block">Status</span>
          <span className="text-sm font-bold text-emerald-400">
            {result ? result.workflow_status : 'READY'}
          </span>
        </div>
      </div>

      {/* Agent Workflow Execution Nodes */}
      <div className="space-y-4">
        <h3 className="text-base font-bold text-white">LangGraph Supervisor & Agent Execution Pipeline</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {agents.map((ag, i) => (
            <div
              key={i}
              className={`p-5 rounded-2xl border transition-all ${
                result
                  ? 'bg-[#132238] border-cyan-500/40 shadow-lg'
                  : 'bg-[#0D182E] border-[#1E3A5F]'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-white">{ag.name}</span>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                  ag.status === 'COMPLETED'
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                    : ag.status === 'AWAITING APPROVAL'
                    ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                    : 'bg-slate-800 text-slate-400'
                }`}>
                  {ag.status}
                </span>
              </div>
              <span className="text-[11px] text-cyan-400 font-semibold block mb-2">{ag.role}</span>
              <p className="text-xs text-slate-300 leading-relaxed font-mono text-[11px] bg-[#0A1128] p-3 rounded-lg border border-[#1E3A5F]/40">
                {ag.output}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Investigation Dossier Output */}
      {result && (
        <div className="bg-[#132238] border border-cyan-500/50 rounded-2xl p-6 shadow-2xl space-y-6">
          <div className="flex items-center justify-between border-b border-[#1E3A5F] pb-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-emerald-500/20 text-emerald-400 rounded-lg">
                <CheckCircle2 className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">Executive Dossier & Human Approval Gate</h3>
                <p className="text-xs text-slate-400">All findings verified with immutable IBM Db2 event citations</p>
              </div>
            </div>

            <button
              onClick={() => navigate('/approvals')}
              className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold shadow-lg shadow-emerald-500/20 transition-all"
            >
              Open Approval Console
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="space-y-3">
              <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Recommended Containment Actions</h4>
              <div className="space-y-2">
                {result.recommended_actions?.map((act: any, idx: number) => (
                  <div key={idx} className="p-3 bg-[#0D182E] border border-[#1E3A5F] rounded-xl text-xs space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-white">{act.action_type}</span>
                      <span className="text-[10px] text-amber-400 font-semibold bg-amber-500/10 px-2 py-0.5 rounded">
                        Requires Approval
                      </span>
                    </div>
                    <p className="text-slate-300">{act.risk_mitigation}</p>
                    <code className="text-cyan-400 block mt-1 text-[11px]">{act.proposed_sql}</code>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-3">
              <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Executive Report Summary</h4>
              <div className="bg-[#0D182E] border border-[#1E3A5F] rounded-xl p-4 font-mono text-xs text-slate-300 leading-relaxed max-h-72 overflow-y-auto whitespace-pre-line">
                {result.report}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
