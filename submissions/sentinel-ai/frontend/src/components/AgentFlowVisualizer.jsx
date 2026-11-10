import React from 'react';
import { 
  Radio, 
  UserCheck, 
  Crosshair, 
  Gauge, 
  ShieldAlert, 
  ArrowRight, 
  CheckCircle2, 
  Loader2 
} from 'lucide-react';

export default function AgentFlowVisualizer({ activeStep = 5, agentLogs = [] }) {
  const agents = [
    {
      id: 1,
      name: 'Event Monitoring Agent',
      shortName: 'Event Monitoring',
      icon: Radio,
      role: 'Db2 Telemetry & Velocity',
      tactic: 'Monitors failed login bursts & access anomalies'
    },
    {
      id: 2,
      name: 'Behaviour Analysis Agent',
      shortName: 'Behaviour Analysis',
      icon: UserCheck,
      role: 'Baseline Deviations',
      tactic: 'Identifies unfamiliar devices & off-hours activity'
    },
    {
      id: 3,
      name: 'Threat Intelligence Agent',
      shortName: 'Threat Intelligence',
      icon: Crosshair,
      role: 'MITRE ATT&CK Mapping',
      tactic: 'Classifies T1110, T1078, T1530 attack techniques'
    },
    {
      id: 4,
      name: 'Risk Assessment Agent',
      shortName: 'Risk Assessment',
      icon: Gauge,
      role: 'Explainable AI Scoring',
      tactic: 'Computes 0-100 score & assigns Low/Med/High/Critical'
    },
    {
      id: 5,
      name: 'Incident Response Agent',
      shortName: 'Incident Response',
      icon: ShieldAlert,
      role: 'Human-in-the-Loop Actions',
      tactic: 'Formulates defense playbook requiring admin approval'
    }
  ];

  return (
    <div className="cyber-card p-5 bg-[#0b1528] border border-[#1a2f55]">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-tech text-base font-bold text-white tracking-wide uppercase flex items-center space-x-2">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
            <span>LangGraph Multi-Agent Orchestration Flow</span>
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            5 Specialized AI Agents sequentially correlating telemetry from IBM Db2
          </p>
        </div>
        <span className="text-[11px] font-mono-code px-2.5 py-1 rounded bg-purple-950/60 text-purple-300 border border-purple-800/60">
          StateGraph Active
        </span>
      </div>

      {/* Agents Linear Progression Grid */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-3 relative">
        {agents.map((agent, index) => {
          const Icon = agent.icon;
          const isCompleted = activeStep >= agent.id;
          const isCurrent = activeStep === agent.id;
          const log = agentLogs.find(l => l.stage === agent.id);

          return (
            <div key={agent.id} className="relative">
              <div 
                className={`p-3.5 rounded-lg border transition-all h-full flex flex-col justify-between ${
                  isCompleted 
                    ? 'bg-[#0f1f3d] border-blue-600/60 glow-blue' 
                    : isCurrent
                    ? 'bg-[#152a52] border-cyan-400 glow-cyan'
                    : 'bg-[#091120] border-[#152642] opacity-50'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-mono-code font-bold text-cyan-400">
                      AGENT 0{agent.id}
                    </span>
                    {isCompleted ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    ) : isCurrent ? (
                      <Loader2 className="w-3.5 h-3.5 text-cyan-400 animate-spin" />
                    ) : (
                      <span className="w-2 h-2 rounded-full bg-slate-700"></span>
                    )}
                  </div>

                  <div className="flex items-center space-x-2 mb-1.5">
                    <div className="p-1.5 rounded bg-blue-950 border border-blue-800/60 text-cyan-400">
                      <Icon className="w-4 h-4" />
                    </div>
                    <h4 className="font-tech text-xs font-bold text-slate-100 leading-tight">
                      {agent.shortName}
                    </h4>
                  </div>

                  <p className="text-[10px] font-mono-code text-blue-300 font-semibold mb-1">
                    {agent.role}
                  </p>
                  <p className="text-[11px] text-slate-400 leading-tight">
                    {agent.tactic}
                  </p>
                </div>

                {log && (
                  <div className="mt-3 pt-2 border-t border-[#1a2f55] text-[10px] font-mono-code text-emerald-400 flex items-center justify-between">
                    <span>{log.duration_ms}ms</span>
                    <span className="text-slate-400">Db2 Verified</span>
                  </div>
                )}
              </div>

              {/* Arrow Connector between steps */}
              {index < agents.length - 1 && (
                <div className="hidden md:block absolute -right-2 top-1/2 -translate-y-1/2 z-10 text-blue-500">
                  <ArrowRight className="w-3.5 h-3.5" />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

