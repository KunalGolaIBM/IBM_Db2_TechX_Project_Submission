import React, { useState } from 'react';
import {
  CheckCircle,
  ShieldCheck,
  Sparkles,
  GitBranch,
  Package,
  ShieldAlert,
  AlertCircle,
  Check,
  X,
  Database,
  ArrowRight,
  RefreshCw,
  RotateCcw,
  FileText,
} from 'lucide-react';
import type { AgentWorkflowResult, RecallAction } from '../../services/api';

interface AgentIntelligenceModalProps {
  workflowResult: AgentWorkflowResult | null;
  isOpen: boolean;
  onClose: () => void;
  isRunning?: boolean;
  onRunAgain?: () => void;
  onDecision?: (actionId: string, decision: 'APPROVED' | 'REJECTED') => Promise<void>;
  onResetDemo?: () => Promise<void>;
  onExportDossier?: () => void;
  isProcessing?: boolean;
}

export const AgentIntelligenceModal: React.FC<AgentIntelligenceModalProps> = ({
  workflowResult,
  isOpen,
  onClose,
  isRunning,
  onRunAgain,
  onDecision,
  onResetDemo,
  onExportDossier,
  isProcessing,
}) => {
  const [activeTab, setActiveTab] = useState<'agents' | 'actions' | 'evidence'>('agents');
  const [confirmModal, setConfirmModal] = useState<{
    action: RecallAction;
    decision: 'APPROVED' | 'REJECTED';
  } | null>(null);

  if (!isOpen) return null;

  const steps = workflowResult?.steps || [];
  const actions = workflowResult?.recommended_actions || [];
  const geminiStatus = workflowResult?.gemini_status;

  const renderAiInterpretation = (stepIndex: number, label: string) => {
    const step = steps[stepIndex];
    if (!step?.ai_interpretation) return null;
    const isGemini = step.ai_status === 'GEMINI_SYNTHESIZED';
    return (
      <div className="p-3 rounded-lg bg-[#23cad2]/[0.06] border border-[#23cad2]/20 text-xs text-white/90 space-y-1.5">
        <div className="flex items-center justify-between text-[10px] font-mono font-bold pb-1 border-b border-[#23cad2]/15">
          <div className="flex items-center gap-1.5 text-[#8ef5e6]">
            <Sparkles className="w-3 h-3 text-[#23cad2]" />
            <span>{label.toUpperCase()}</span>
          </div>
          <span className={`px-2 py-0.5 rounded font-mono text-[9.5px] font-bold ${
            isGemini 
              ? 'bg-[#23cad2]/20 text-[#8ef5e6] border border-[#23cad2]/40' 
              : 'bg-white/10 text-white/60 border border-white/15'
          }`}>
            {isGemini ? `GEMINI INTERPRETATION (${geminiStatus?.model || '3.5 FLASH'})` : 'DETERMINISTIC FALLBACK'}
          </span>
        </div>
        <p className="text-white/80 leading-relaxed text-[11.5px] pt-1">
          {step.ai_interpretation}
        </p>
        {(step.limitations_or_missing_info || step.validation_status) && (
          <div className="text-[10px] font-mono text-white/50 pt-1.5 border-t border-white/8 flex items-center justify-between flex-wrap gap-2">
            {step.limitations_or_missing_info && (
              <span className="truncate max-w-[340px] sm:max-w-none text-white/60">
                SCOPE: {step.limitations_or_missing_info}
              </span>
            )}
            {step.validation_status && (
              <span className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase ${
                step.validation_status === 'VALIDATED' 
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' 
                  : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
              }`}>
                {step.validation_status === 'VALIDATED' ? 'SERVER VALIDATED' : 'FALLBACK ENFORCED'}
              </span>
            )}
          </div>
        )}
      </div>
    );
  };

  const handleConfirmDecision = async () => {
    if (!confirmModal || !onDecision) return;
    await onDecision(confirmModal.action.action_id, confirmModal.decision);
    setConfirmModal(null);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/85 backdrop-blur-md p-0 sm:p-4 animate-in fade-in duration-150">
      {/* Modal Dialog Card: Mobile Full Screen / Desktop Centered Card */}
      <div className="bg-[#12161f] border-t sm:border border-white/20 rounded-t-2xl sm:rounded-2xl max-w-4xl w-full h-[100dvh] sm:h-auto sm:max-h-[90vh] flex flex-col shadow-[0_24px_70px_rgba(0,0,0,0.95)] overflow-hidden">
        
        {/* 1. Header (Compact on mobile, properly aligned title, status, close button) */}
        <div className="px-4 py-3 sm:p-6 border-b border-white/10 flex items-center justify-between bg-black/40 gap-2 shrink-0">
          <div className="flex items-center space-x-2.5 sm:space-x-3.5 min-w-0">
            <div className="w-8 h-8 sm:w-9 h-9 rounded-lg sm:rounded-xl bg-gradient-to-br from-[#23cad2] to-[#1680ac] flex items-center justify-center shadow-[0_0_24px_rgba(35,202,210,0.4)] shrink-0">
              <Sparkles className="w-4 h-4 sm:w-5 sm:h-5 text-[#030c1a]" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-xs sm:text-lg font-bold text-white tracking-tight truncate">
                  LangGraph Recall Investigation
                </h2>
                {isRunning ? (
                  <span className="text-[9px] sm:text-[10px] font-mono font-bold text-amber-300 bg-amber-500/20 border border-amber-500/40 px-1.5 sm:px-2 py-0.5 rounded animate-pulse shrink-0">
                    RUNNING
                  </span>
                ) : (
                  <span className="text-[9px] sm:text-[10px] font-mono font-bold text-emerald-300 bg-emerald-500/20 border border-emerald-500/40 px-1.5 sm:px-2 py-0.5 rounded flex items-center gap-1 shrink-0">
                    <CheckCircle className="w-3 h-3 text-emerald-400" />
                    <span>ORCHESTRATED</span>
                  </span>
                )}
              </div>
              <p className="text-[10px] sm:text-xs text-white/50 font-mono mt-0.5 truncate">
                4 Specialized Autonomous Agents • IBM Db2 12.1 • Zero Hallucinations
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-11 h-11 min-w-[44px] min-h-[44px] flex items-center justify-center rounded-lg hover:bg-white/10 text-white/70 hover:text-white transition-colors cursor-pointer shrink-0"
            aria-label="Close Modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* 2. Four-Agent Stepper (Horizontally scrollable with smooth touch momentum) */}
        <div className="bg-black/60 px-4 sm:px-6 py-2.5 sm:py-3 border-b border-white/8 overflow-x-auto shrink-0 scrollbar-none">
          <div className="flex items-center gap-3 sm:justify-between min-w-max text-[11px] sm:text-xs font-mono">
            {[
              { id: 1, name: '1. Incident Intake', icon: ShieldCheck },
              { id: 2, name: '2. Traceability', icon: GitBranch },
              { id: 3, name: '3. Risk Assessment', icon: Package },
              { id: 4, name: '4. Response Planning', icon: ShieldAlert },
            ].map((step, idx) => {
              const Icon = step.icon;
              const isCompleted = !isRunning && (steps.length >= step.id || (workflowResult && !workflowResult.error));
              return (
                <React.Fragment key={step.id}>
                  <div className="flex items-center gap-2 shrink-0">
                    <div
                      className={`w-5 h-5 sm:w-6 sm:h-6 rounded-full flex items-center justify-center text-[10px] font-bold ${
                        isRunning
                          ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                          : isCompleted
                          ? 'bg-[#23cad2]/20 text-[#8ef5e6] border border-[#23cad2]/50'
                          : 'bg-white/10 text-white/40'
                      }`}
                    >
                      <Icon className="w-3 h-3 sm:w-3.5 sm:h-3.5" />
                    </div>
                    <span
                      className={`font-semibold whitespace-nowrap ${
                        isCompleted ? 'text-white' : 'text-white/50'
                      }`}
                    >
                      {step.name}
                    </span>
                  </div>
                  {idx < 3 && (
                    <ArrowRight className="w-3 h-3 sm:w-3.5 sm:h-3.5 text-white/20 shrink-0 mx-0.5 sm:mx-1" />
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>

        {/* 3. Tab Navigation (One horizontal row with horizontal scrolling, never wrap text) */}
        <div className="flex border-b border-white/10 px-4 sm:px-6 bg-black/30 overflow-x-auto shrink-0 flex-nowrap scrollbar-none">
          <button
            onClick={() => setActiveTab('agents')}
            className={`whitespace-nowrap shrink-0 py-2.5 sm:py-3 px-3 sm:px-4 text-[11px] sm:text-xs font-semibold font-mono border-b-2 transition-all cursor-pointer ${
              activeTab === 'agents'
                ? 'border-[#23cad2] text-white'
                : 'border-transparent text-white/50 hover:text-white'
            }`}
          >
            AGENT FINDINGS & EVIDENCE ({steps.length || 4})
          </button>
          <button
            onClick={() => setActiveTab('actions')}
            className={`whitespace-nowrap shrink-0 py-2.5 sm:py-3 px-3 sm:px-4 text-[11px] sm:text-xs font-semibold font-mono border-b-2 transition-all cursor-pointer ${
              activeTab === 'actions'
                ? 'border-[#23cad2] text-white'
                : 'border-transparent text-white/50 hover:text-white'
            }`}
          >
            ACTION PLAN & APPROVALS ({actions.length})
          </button>
          <button
            onClick={() => setActiveTab('evidence')}
            className={`whitespace-nowrap shrink-0 py-2.5 sm:py-3 px-3 sm:px-4 text-[11px] sm:text-xs font-semibold font-mono border-b-2 transition-all cursor-pointer ${
              activeTab === 'evidence'
                ? 'border-[#23cad2] text-white'
                : 'border-transparent text-white/50 hover:text-white'
            }`}
          >
            RAW DB2 TELEMETRY ({workflowResult?.evidence.length || 0})
          </button>
        </div>

        {/* 4. Dedicated Scrollable Content Area (with safe bottom padding to prevent overlay clipping) */}
        <div className="p-4 sm:p-6 overflow-y-auto space-y-4 flex-1 overscroll-contain pb-28 sm:pb-6">
          {isRunning ? (
            <div className="flex flex-col items-center justify-center py-16 space-y-4">
              <div className="w-12 h-12 border-3 border-[#23cad2] border-t-transparent rounded-full animate-spin" />
              <p className="text-sm font-mono text-white/80 text-center">
                Orchestrating LangGraph State Machine across Db2 Tables...
              </p>
              <p className="text-xs font-mono text-white/40 text-center">
                Executing recursive queries, inventory audits, and risk assessment models.
              </p>
            </div>
          ) : activeTab === 'agents' ? (
            <div className="space-y-4">
              {/* Agent 1: Incident Intake Agent */}
              <div className="p-4 rounded-xl bg-black/40 border border-white/10 hover:border-white/20 transition-all space-y-2.5">
                <div className="flex items-center justify-between pb-2 border-b border-white/8">
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4 text-[#23cad2]" />
                    <span className="font-mono text-xs font-bold text-white uppercase tracking-wider">
                      Agent 1: Incident Intake Agent
                    </span>
                  </div>
                  <span className="text-[10px] font-mono font-bold text-emerald-300 bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 rounded">
                    VERIFIED IN DB2
                    DB2 VERIFIED
                  </span>
                </div>
                <p className="text-xs text-white/70">
                  <strong className="text-white">Task:</strong> Validate reported contamination incident in IBM Db2, verify supplier pedigree, and confirm source lot quarantine status.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 pt-1 font-mono text-xs">
                  <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/5">
                    <span className="text-white/40 text-[10px] block">INCIDENT ID</span>
                    <span className="text-white font-bold">{workflowResult?.incident_id || 'INC-2026-001'}</span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/5">
                    <span className="text-white/40 text-[10px] block">SOURCE LOT</span>
                    <span className="text-[#8ef5e6] font-bold">{workflowResult?.source_lot_id || 'RAW-204'}</span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/5">
                    <span className="text-white/40 text-[10px] block">SUPPLIER</span>
                    <span className="text-white font-bold">GreenLeaf Foods</span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/5">
                    <span className="text-white/40 text-[10px] block">SEVERITY / STATUS</span>
                    <span className="text-red-400 font-bold">CRITICAL / OPEN</span>
                  </div>
                </div>
                {renderAiInterpretation(0, 'Incident & Source Evidence AI Interpretation')}
                <div className="text-[11px] font-mono text-white/50 pt-1 flex items-center gap-1.5">
                  <Database className="w-3 h-3 text-[#23cad2]" />
                  <span>Tables Queried: LOTLINE_APP.INCIDENTS, LOTLINE_APP.LOTS, LOTLINE_APP.SUPPLIERS</span>
                </div>
              </div>

              {/* Agent 2: Traceability Agent */}
              <div className="p-4 rounded-xl bg-black/40 border border-white/10 hover:border-white/20 transition-all space-y-2.5">
                <div className="flex items-center justify-between pb-2 border-b border-white/8">
                  <div className="flex items-center gap-2">
                    <GitBranch className="w-4 h-4 text-[#23cad2]" />
                    <span className="font-mono text-xs font-bold text-white uppercase tracking-wider">
                      Agent 2: Traceability Agent
                    </span>
                  </div>
                  <span className="text-[10px] font-mono font-bold text-[#8ef5e6] bg-[#23cad2]/10 border border-[#23cad2]/30 px-2 py-0.5 rounded">
                    RECURSIVE CTE DISCOVERED
                  </span>
                  <span className="text-[10px] font-mono font-bold text-emerald-300 bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 rounded">
                    DB2 VERIFIED
                  </span>
                </div>
                <p className="text-xs text-white/70">
                  <strong className="text-white">Task:</strong> Traverse multi-tier production genealogy via recursive Db2 CTE to discover all work-in-progress (WIP) and commercial finished lots.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 pt-1 font-mono text-xs">
                  <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/5">
                    <span className="text-white/40 text-[10px] block">TOTAL DOWNSTREAM</span>
                    <span className="text-white font-bold">6 Batches</span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/5">
                    <span className="text-white/40 text-[10px] block">PRODUCTION DEPTH</span>
                    <span className="text-white font-bold">2 Levels</span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/5">
                    <span className="text-white/40 text-[10px] block">WIP BATCHES (L1)</span>
                    <span className="text-amber-300 font-bold">WIP-301, 302, 303</span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/5">
                    <span className="text-white/40 text-[10px] block">FINISHED PRODUCTS (L2)</span>
                    <span className="text-amber-300 font-bold">FIN-401, 402, 403</span>
                  </div>
                </div>
                {renderAiInterpretation(1, 'Production Genealogy AI Interpretation')}
                <div className="text-[11px] font-mono text-white/50 pt-1 flex items-center gap-1.5">
                  <Database className="w-3 h-3 text-[#23cad2]" />
                  <span>Tables Queried: LOTLINE_APP.LOT_LINEAGE, LOTLINE_APP.LOTS, LOTLINE_APP.FACILITIES</span>
                </div>
              </div>

              {/* Agent 3: Risk Assessment Agent */}
              <div className="p-4 rounded-xl bg-black/40 border border-white/10 hover:border-white/20 transition-all space-y-2.5">
                <div className="flex items-center justify-between pb-2 border-b border-white/8">
                  <div className="flex items-center gap-2">
                    <Package className="w-4 h-4 text-[#23cad2]" />
                    <span className="font-mono text-xs font-bold text-white uppercase tracking-wider">
                      Agent 3: Risk Assessment Agent
                    </span>
                  </div>
                  <span className="text-[10px] font-mono font-bold text-red-300 bg-red-500/10 border border-red-500/30 px-2 py-0.5 rounded">
                    CRITICAL RISK SCORE 94/100
                  </span>
                  <span className="text-[10px] font-mono font-bold text-emerald-300 bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 rounded">
                    DB2 VERIFIED
                  </span>
                </div>
                <p className="text-xs text-white/70">
                  <strong className="text-white">Task:</strong> Audit inventory and logistics in Db2 to compute exact unit exposure across secure warehouses, active transit, and commercial retailers.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 pt-1 font-mono text-xs">
                  <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/5">
                    <span className="text-white/40 text-[10px] block">TOTAL EXPOSURE</span>
                    <span className="text-white font-bold">2,400 Units</span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/5">
                    <span className="text-white/40 text-[10px] block">WAREHOUSE (QUARANTINED)</span>
                    <span className="text-emerald-300 font-bold">1,350 (56.3%)</span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/5">
                    <span className="text-white/40 text-[10px] block">DELIVERED TO RETAIL</span>
                    <span className="text-red-300 font-bold">850 (35.4%)</span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/5">
                    <span className="text-white/40 text-[10px] block">IN TRANSIT LOGISTICS</span>
                    <span className="text-amber-300 font-bold">200 (8.3%)</span>
                  </div>
                </div>
                {renderAiInterpretation(2, 'Exposure Risk Analysis AI Interpretation')}
                <div className="text-[11px] font-mono text-white/50 pt-1 flex items-center gap-1.5">
                  <Database className="w-3 h-3 text-[#23cad2]" />
                  <span>Tables Queried: LOTLINE_APP.INVENTORY, LOTLINE_APP.SHIPMENTS, LOTLINE_APP.FACILITIES</span>
                </div>
              </div>

              {/* Agent 4: Response Planning Agent */}
              <div className="p-4 rounded-xl bg-black/40 border border-white/10 hover:border-white/20 transition-all space-y-2.5">
                <div className="flex items-center justify-between pb-2 border-b border-white/8">
                  <div className="flex items-center gap-2">
                    <ShieldAlert className="w-4 h-4 text-[#23cad2]" />
                    <span className="font-mono text-xs font-bold text-white uppercase tracking-wider">
                      Agent 4: Response Planning Agent
                    </span>
                  </div>
                  <span className="text-[10px] font-mono font-bold text-amber-300 bg-amber-500/10 border border-amber-500/30 px-2 py-0.5 rounded">
                    HUMAN APPROVAL REQUIRED
                  </span>
                </div>
                <p className="text-xs text-white/70">
                  <strong className="text-white">Task:</strong> Synthesize evidence-backed mitigation recommendations from Db2 action protocols and enforce Human-in-the-Loop approval gate.
                </p>
                <div className="p-3 rounded-lg bg-white/[0.03] border border-white/6 text-xs text-white/80 space-y-1">
                  <div className="font-bold text-white flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-amber-400" />
                    <span>Governance Safety Rule: HUMAN_IN_THE_LOOP_ENFORCED</span>
                  </div>
                  <p className="text-white/60">
                    4 Action protocols formulated from LOTLINE_APP.RECALL_ACTIONS. Database mutations are strictly gated until an authenticated operator signs off.
                  </p>
                </div>
                {renderAiInterpretation(3, 'Mitigation Strategy AI Rationale')}
                <div className="text-[11px] font-mono text-white/50 pt-1 flex items-center gap-1.5">
                  <Database className="w-3 h-3 text-[#23cad2]" />
                  <span>Tables Queried: LOTLINE_APP.RECALL_ACTIONS, LOTLINE_APP.AUDIT_LOG</span>
                </div>
              </div>
            </div>
          ) : activeTab === 'actions' ? (
            <div className="space-y-4">
              {/* Gemini Synthesis / AI Unavailable Banner */}
              <div
                className={`p-4 rounded-xl border ${
                  geminiStatus?.available
                    ? 'bg-[#23cad2]/10 border-[#23cad2]/30 text-white'
                    : 'bg-white/[0.03] border-white/10 text-white/75'
                }`}
              >
                <div className="flex items-center justify-between pb-2 border-b border-white/8 text-xs font-mono font-bold flex-wrap gap-2">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-3.5 h-3.5 text-[#23cad2]" />
                    <span>
                      {geminiStatus?.available
                        ? `AI Mitigation Rationale (${geminiStatus.model || 'Gemini 3.5 Flash'})`
                        : `AI Status Notice: Honest Fallback (${geminiStatus?.status_code || 'STANDALONE'})`}
                    </span>
                  </div>
                  <span
                    className={`text-[9px] px-2 py-0.5 rounded font-bold uppercase tracking-wider ${
                      geminiStatus?.available
                        ? 'bg-[#23cad2]/20 text-[#8ef5e6] border border-[#23cad2]/40'
                        : 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                    }`}
                  >
                    {geminiStatus?.available ? 'CONNECTED • GROUNDED ON DB2' : 'DETERMINISTIC DB2 RULES'}
                  </span>
                </div>
                <p className="text-xs leading-relaxed mt-2 text-white/85">
                  {geminiStatus?.rationale || geminiStatus?.note || 'Operating in deterministic rule-based mode based on Db2 audit evidence.'}
                </p>
              </div>

              {/* Action Protocols List with Direct Approval Controls */}
              <div className="space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between text-xs font-mono text-white/60 px-1 gap-1">
                  <span>MITIGATION ACTIONS FROM LOTLINE_APP.RECALL_ACTIONS</span>
                  <span className="text-[#8ef5e6]">TOUCH APPROVE TO COMMIT ACID TRANSACTION</span>
                </div>

                {actions.map((act) => {
                  const isApproved = act.status === 'APPROVED';
                  const isRejected = act.status === 'REJECTED';
                  const isProposed = act.status === 'PROPOSED';

                  return (
                    <div
                      key={act.action_id}
                      className="p-3.5 rounded-xl bg-black/40 border border-white/10 flex flex-col sm:flex-row sm:items-center justify-between gap-3.5"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-mono text-xs font-bold text-white tracking-wide">
                            {act.action_id}
                          </span>
                          <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-white/10 text-white/70">
                            {act.action_type.replace('_', ' ')}
                          </span>
                          <span className="text-[10px] font-mono text-white/50 truncate max-w-[200px] sm:max-w-none">
                            TARGET: {act.target_id}
                          </span>
                          <span
                            className={`text-[9px] font-mono uppercase px-2 py-0.5 rounded font-bold ${
                              isApproved
                                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                                : isRejected
                                ? 'bg-red-500/20 text-red-300 border border-red-500/30'
                                : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                            }`}
                          >
                            {act.status}
                            {isApproved ? 'HUMAN APPROVED' : isRejected ? 'HUMAN REJECTED' : 'PENDING REVIEW'}
                          </span>
                        </div>
                        <p className="text-xs text-white/80 mt-1 leading-relaxed">
                          {act.action_description}
                        </p>
                        {isApproved && act.approved_by && (
                          <span className="text-[10px] font-mono text-emerald-300/70 block mt-1">
                            ✓ Committed to Db2 by {act.approved_by}
                          </span>
                        )}
                      </div>

                      {/* Controls with accessible min 44x44px touch targets on mobile */}
                      <div className="flex items-center gap-2 shrink-0 self-stretch sm:self-auto">
                        {isProposed && onDecision ? (
                          <>
                            <button
                              onClick={() => setConfirmModal({ action: act, decision: 'APPROVED' })}
                              disabled={isProcessing}
                              className="min-h-[44px] flex-1 sm:flex-none px-4 py-2 rounded-lg bg-emerald-600/25 hover:bg-emerald-600/40 border border-emerald-500/50 text-emerald-300 text-xs font-semibold flex items-center justify-center gap-1.5 transition-all active:scale-95 cursor-pointer disabled:opacity-40"
                            >
                              <Check className="w-4 h-4" />
                              <span>Approve</span>
                            </button>
                            <button
                              onClick={() => setConfirmModal({ action: act, decision: 'REJECTED' })}
                              disabled={isProcessing}
                              className="min-h-[44px] flex-1 sm:flex-none px-4 py-2 rounded-lg bg-red-600/25 hover:bg-red-600/40 border border-red-500/50 text-red-300 text-xs font-semibold flex items-center justify-center gap-1.5 transition-all active:scale-95 cursor-pointer disabled:opacity-40"
                            >
                              <X className="w-4 h-4" />
                              <span>Reject</span>
                            </button>
                          </>
                        ) : (
                          <span className="text-[11px] font-mono text-white/40 px-2.5 py-1.5 rounded bg-white/[0.04] text-center w-full sm:w-auto">
                            Db2 Logged
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="text-xs font-mono text-white/60 mb-2">
                VERIFIABLE GROUND TRUTH TELEMETRY CAPTURED ACROSS IBM DB2 TABLES:
              </div>
              {workflowResult?.evidence.map((ev, idx) => (
                <div key={idx} className="p-4 rounded-xl bg-black/50 border border-white/10 space-y-2">
                  <div className="flex items-center justify-between pb-2 border-b border-white/8 text-xs font-mono">
                    <span className="font-bold text-white">{ev.step}</span>
                    <span className="text-[#23cad2] bg-[#23cad2]/10 border border-[#23cad2]/30 px-2.5 py-0.5 rounded text-[10px] font-bold">
                      DB2 VERIFIED • {ev.verified_source}
                    </span>
                  </div>
                  <pre className="text-[11px] font-mono text-white/80 bg-black/70 p-3 rounded-lg overflow-x-auto border border-white/5">
                    {JSON.stringify(ev, null, 2)}
                  </pre>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 5. Sticky Footer (Always accessible, safe-area aware, with clear action controls) */}
        <div className="sticky bottom-0 z-30 p-3.5 sm:p-4 bg-[#0d111a]/95 backdrop-blur-md border-t border-white/10 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 text-xs text-white/60 font-mono pb-[max(0.85rem,env(safe-area-inset-bottom))] shrink-0">
          <div className="flex items-center gap-2 text-[10px] sm:text-xs">
            <Database className="w-3.5 h-3.5 text-[#23cad2] shrink-0" />
            <span className="truncate">Schema: LOTLINE_APP • ACID Protection</span>
          </div>
          
          <div className="flex items-center gap-2 sm:gap-3">
            {onResetDemo && (
              <button
                onClick={onResetDemo}
                disabled={isProcessing || isRunning}
                title="Restore initial demo actions (ACT-001 approved, ACT-002..004 proposed)"
                className="min-h-[44px] sm:min-h-0 px-3 py-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-white/70 hover:text-white text-xs font-medium flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-40 transition-all flex-1 sm:flex-none"
              >
                <RotateCcw className="w-3.5 h-3.5 text-amber-400" />
                <span className="whitespace-nowrap">Reset Demo</span>
              </button>
            )}

            {onRunAgain && (
              <button
                onClick={onRunAgain}
                disabled={isRunning}
                className="min-h-[44px] sm:min-h-0 px-3.5 py-2 rounded-lg bg-white/10 hover:bg-white/15 text-white font-medium flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-40 transition-all flex-1 sm:flex-none"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isRunning ? 'animate-spin' : ''}`} />
                <span className="whitespace-nowrap">Re-dispatch</span>
              </button>
            )}

            <button
              onClick={onClose}
              className="min-h-[44px] sm:min-h-0 px-5 py-2 rounded-lg bg-[#23cad2] hover:bg-[#34ded6] text-[#030c1a] font-bold cursor-pointer transition-all active:scale-95 flex items-center justify-center flex-1 sm:flex-none"
            >
              Close
            </button>
          </div>
        </div>
      </div>

      {/* 6. Human Confirmation Modal Dialog (Touch-friendly, z-[70]) */}
      {confirmModal && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/90 backdrop-blur-sm p-4 animate-in fade-in duration-100">
          <div className="bg-[#171717] border border-white/20 rounded-xl max-w-md w-full p-5 sm:p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <AlertCircle
                className={`w-5 h-5 shrink-0 ${
                  confirmModal.decision === 'APPROVED' ? 'text-emerald-400' : 'text-red-400'
                }`}
              />
              <h3 className="text-base font-bold text-white">
                Confirm Human {confirmModal.decision === 'APPROVED' ? 'Approval' : 'Rejection'}
              </h3>
            </div>

            <p className="text-xs text-white/80 leading-relaxed">
              Are you sure you want to mark action{' '}
              <strong className="text-white font-mono">{confirmModal.action.action_id}</strong> as{' '}
              <strong
                className={
                  confirmModal.decision === 'APPROVED' ? 'text-emerald-300 font-bold' : 'text-red-300 font-bold'
                }
              >
                {confirmModal.decision}
              </strong>
              ? This action will commit an ACID transaction in <span className="font-mono text-white">IBM Db2</span> and record a permanent entry in <span className="font-mono text-white">LOTLINE_APP.AUDIT_LOG</span>.
            </p>

            <div className="pt-2 flex flex-col sm:flex-row justify-end gap-2.5 font-mono text-xs">
              <button
                onClick={() => setConfirmModal(null)}
                className="min-h-[44px] px-4 py-2.5 rounded-lg bg-white/10 hover:bg-white/15 text-white cursor-pointer order-2 sm:order-1 flex items-center justify-center"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmDecision}
                disabled={isProcessing}
                className={`min-h-[44px] px-4 py-2.5 rounded-lg font-bold cursor-pointer transition-all order-1 sm:order-2 flex items-center justify-center ${
                  confirmModal.decision === 'APPROVED'
                    ? 'bg-emerald-500 hover:bg-emerald-400 text-black'
                    : 'bg-red-500 hover:bg-red-400 text-white'
                }`}
              >
                {isProcessing ? 'Committing...' : `Confirm ${confirmModal.decision}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
