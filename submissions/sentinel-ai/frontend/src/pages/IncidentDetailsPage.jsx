import React, { useState } from 'react';
import { 
  ArrowLeft, 
  Flame, 
  ShieldAlert, 
  Lock, 
  CheckCircle2, 
  XCircle, 
  FileText, 
  User, 
  Radio, 
  Crosshair, 
  Cpu, 
  Clock, 
  ExternalLink,
  Laptop
} from 'lucide-react';
import RiskGauge from '../components/RiskGauge';
import MitreBadge from '../components/MitreBadge';
import ApprovalModal from '../components/ApprovalModal';

export default function IncidentDetailsPage({ 
  incidentDetails, 
  onBack, 
  onViewReport, 
  onExecuteRecommendation 
}) {
  const [selectedRecommendation, setSelectedRecommendation] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [activeAgentTab, setActiveAgentTab] = useState('ALL');

  if (!incidentDetails || !incidentDetails.incident) {
    return (
      <div className="p-8 text-center text-slate-400 font-mono-code">
        Incident telemetry not found. Select an incident from the dashboard.
      </div>
    );
  }

  const { incident, analyses = [], recommendations = [], recent_logins = [], recent_accesses = [] } = incidentDetails;

  const handleOpenApproval = (rec) => {
    setSelectedRecommendation(rec);
    setModalOpen(true);
  };

  return (
    <div className="space-y-6">
      {/* Top Navigation & Actions Bar */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div className="flex items-center space-x-3">
          <button
            onClick={onBack}
            className="p-2 rounded-lg bg-[#070d18] border border-[#1a2f55] text-slate-300 hover:text-white hover:border-blue-500 transition-all"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-mono-code text-sm font-bold text-cyan-400">{incident.incident_id}</span>
              <span className={`px-2 py-0.5 rounded text-[10px] font-mono-code font-bold uppercase ${
                incident.severity === 'CRITICAL' ? 'bg-rose-950 text-rose-300 border border-rose-800' : 'bg-amber-950 text-amber-300 border border-amber-800'
              }`}>
                {incident.severity}
              </span>
            </div>
            <h2 className="text-xl font-bold font-tech text-white tracking-wide">
              {incident.title}
            </h2>
          </div>
        </div>

        <button
          onClick={() => onViewReport(incident.incident_id)}
          className="flex items-center space-x-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-lg shadow-blue-900/40 transition-all"
        >
          <FileText className="w-4 h-4" />
          <span>Executive Security Report</span>
        </button>
      </div>

      {/* Target Account Dossier & Risk Gauge Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Target Dossier & Summary */}
        <div className="lg:col-span-2 cyber-card p-5 bg-[#0b1528] border border-[#1a2f55] space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-[#1a2f55]">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 rounded-lg bg-blue-950 border border-blue-600 flex items-center justify-center text-blue-300 font-bold">
                <User className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-semibold text-slate-100">{incident.full_name || incident.user_id}</h3>
                <p className="text-xs text-slate-400 font-mono-code">{incident.email} | {incident.department}</p>
              </div>
            </div>
            <div className="text-right">
              <span className="text-[10px] text-slate-400 font-mono-code block">CLEARANCE LEVEL</span>
              <span className="px-2 py-0.5 rounded text-xs font-mono-code font-bold bg-purple-950/80 text-purple-300 border border-purple-800">
                {incident.security_clearance || 'TOP_SECRET'}
              </span>
            </div>
          </div>

          <div>
            <h4 className="text-xs font-tech font-bold uppercase tracking-wider text-slate-400 mb-1">
              Multi-Agent Executive Correlation Summary
            </h4>
            <p className="text-xs text-slate-200 leading-relaxed bg-[#070d18] p-3 rounded-lg border border-[#152642]">
              {incident.summary}
            </p>
          </div>

          {/* MITRE ATT&CK Badges */}
          <div>
            <h4 className="text-xs font-tech font-bold uppercase tracking-wider text-slate-400 mb-2">
              Correlated MITRE ATT&CK Adversary Techniques
            </h4>
            <div className="flex flex-wrap gap-2">
              {(Array.isArray(incident.mitre_technique_ids) ? incident.mitre_technique_ids : []).map((tid) => (
                <MitreBadge key={tid} techniqueId={tid} />
              ))}
            </div>
          </div>
        </div>

        {/* Right 1 Col: Visual Risk Gauge */}
        <div className="space-y-4">
          <RiskGauge score={incident.risk_score} severity={incident.severity} />
          
          <div className="cyber-card p-4 bg-[#0b1528] border border-[#1a2f55] text-xs space-y-2">
            <div className="flex justify-between text-slate-400">
              <span>Status:</span>
              <span className="font-mono-code font-bold text-amber-400">{incident.status}</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>First Event Detected:</span>
              <span className="font-mono-code text-slate-300">{incident.created_at?.slice(0, 19)}</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Orchestration Engine:</span>
              <span className="font-mono-code text-purple-400 font-bold">LangGraph v1.2</span>
            </div>
          </div>
        </div>
      </div>

      {/* 5 Specialized AI Agent Findings Breakdown */}
      <div className="cyber-card p-5 bg-[#0b1528] border border-[#1a2f55] space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-[#1a2f55]">
          <div>
            <h3 className="font-tech text-base font-bold text-white uppercase tracking-wide flex items-center space-x-2">
              <Cpu className="w-4 h-4 text-cyan-400" />
              <span>Multi-Agent AI Analysis Dossier</span>
            </h3>
            <p className="text-xs text-slate-400">
              Explainable findings generated by each of the 5 specialized LangGraph AI agents
            </p>
          </div>
          <span className="text-[11px] font-mono-code text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800">
            5/5 Agents Completed
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {analyses.map((a) => (
            <div key={a.analysis_id} className="p-4 rounded-lg bg-[#070d18] border border-[#152642] space-y-2">
              <div className="flex justify-between items-center">
                <span className="font-tech text-xs font-bold text-cyan-300 uppercase">
                  {a.agent_name}
                </span>
                <span className="text-[10px] font-mono-code text-purple-400 bg-purple-950/40 px-1.5 py-0.5 rounded border border-purple-800/40">
                  Confidence: {Math.round(a.confidence_score * 100)}%
                </span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed font-sans">
                {a.findings}
              </p>
              {a.parsed_reasoning?.ai_reasoning && (
                <div className="mt-2 pt-2 border-t border-[#1a2f55]">
                  <span className="text-[10px] font-mono-code text-blue-400 font-semibold block mb-1">
                    EXPLAINABLE AI REASONING (IBM watsonx.ai):
                  </span>
                  <p className="text-[11px] text-slate-400 italic bg-[#0b1528] p-2 rounded border border-[#152642]">
                    "{a.parsed_reasoning.ai_reasoning}"
                  </p>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Human-in-the-Loop Defensive Recommendations */}
      <div className="cyber-card p-5 bg-[#0b1528] border border-[#1a2f55] space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-[#1a2f55]">
          <div>
            <h3 className="font-tech text-base font-bold text-white uppercase tracking-wide flex items-center space-x-2">
              <Lock className="w-4 h-4 text-amber-400" />
              <span>Recommended Defensive Actions (Human Approval Gate)</span>
            </h3>
            <p className="text-xs text-slate-400">
              Playbook containment steps generated by Agent 5. Authorization required before execution.
            </p>
          </div>
        </div>

        <div className="space-y-3">
          {recommendations.length === 0 ? (
            <p className="text-xs text-slate-500 font-mono-code text-center py-4">
              No defensive actions currently queued.
            </p>
          ) : (
            recommendations.map((rec) => (
              <div key={rec.recommendation_id} className="p-4 rounded-lg bg-[#070d18] border border-[#152642] flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <span className="font-mono-code text-xs font-bold text-cyan-400">{rec.action_type}</span>
                    <span className={`text-[10px] font-mono-code px-2 py-0.5 rounded font-bold uppercase ${
                      rec.status === 'EXECUTED' 
                        ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' 
                        : rec.status === 'REJECTED'
                        ? 'bg-rose-950 text-rose-400 border border-rose-800'
                        : 'bg-amber-950 text-amber-400 border border-amber-800'
                    }`}>
                      {rec.status}
                    </span>
                  </div>
                  <p className="text-xs text-slate-200">{rec.description}</p>
                  {rec.approved_by && (
                    <p className="text-[10px] font-mono-code text-slate-500">
                      Authorized by: <span className="text-slate-300 font-semibold">{rec.approved_by}</span> on {rec.approved_at?.slice(0, 19)}
                    </p>
                  )}
                </div>

                {rec.status === 'PENDING_APPROVAL' && (
                  <button
                    onClick={() => handleOpenApproval(rec)}
                    className="px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold shadow-lg shadow-amber-900/40 transition-all whitespace-nowrap"
                  >
                    Review & Authorize
                  </button>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Correlated Event Timeline */}
      <div className="cyber-card p-5 bg-[#0b1528] border border-[#1a2f55] space-y-4">
        <h3 className="font-tech text-base font-bold text-white uppercase tracking-wide flex items-center space-x-2">
          <Clock className="w-4 h-4 text-blue-400" />
          <span>Correlated Incident Timeline</span>
        </h3>

        <div className="space-y-2 max-h-[300px] overflow-y-auto pr-2">
          {recent_logins.slice(0, 10).map((l, i) => (
            <div key={l.event_id} className="p-2.5 rounded bg-[#070d18] border border-[#152642] flex items-center justify-between text-xs">
              <div className="flex items-center space-x-3">
                <span className="font-mono-code text-[11px] text-slate-500">#{i + 1}</span>
                <span className={`px-1.5 py-0.2 rounded text-[10px] font-mono-code ${
                  l.status === 'SUCCESS' ? 'text-emerald-400 bg-emerald-950/60' : 'text-rose-400 bg-rose-950/60'
                }`}>
                  {l.status}
                </span>
                <span className="font-semibold text-slate-200">{l.device_name || 'Standard Host'}</span>
                <span className="font-mono-code text-cyan-400 text-[11px]">{l.ip_address}</span>
              </div>
              <span className="font-mono-code text-[10px] text-slate-500">{l.timestamp?.slice(11, 19)}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Approval Confirmation Modal */}
      <ApprovalModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        recommendation={selectedRecommendation}
        onActionSuccess={onExecuteRecommendation}
      />
    </div>
  );
}

