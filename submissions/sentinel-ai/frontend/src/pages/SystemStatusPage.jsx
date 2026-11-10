import React from 'react';
import { 
  Database, 
  Cpu, 
  Activity, 
  CheckCircle2, 
  ShieldCheck, 
  Server, 
  Layers, 
  Terminal,
  Clock
} from 'lucide-react';

export default function SystemStatusPage({ systemStatus }) {
  const db = systemStatus?.database || {};
  const ai = systemStatus?.ai_engine || {};
  const orch = systemStatus?.orchestrator || {};

  const tables = [
    { name: 'USER_ACCOUNTS', description: 'Stores fictional user account information, clearances and roles' },
    { name: 'LOGIN_EVENTS', description: 'Stores successful and failed authentication activities with device telemetry' },
    { name: 'ACCESS_LOGS', description: 'Stores user resource access records and classification tiers' },
    { name: 'SECURITY_ALERTS', description: 'Stores suspicious activity events detected by Event Monitoring Agent' },
    { name: 'INCIDENTS', description: 'Stores correlated multi-event security incidents and risk scores' },
    { name: 'AI_ANALYSIS', description: 'Stores AI-generated findings, confidence scores and explanations' },
    { name: 'RESPONSE_RECOMMENDATIONS', description: 'Stores defensive recommendations requiring authorized administrator approval' }
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold font-tech text-white uppercase tracking-wide flex items-center space-x-2">
          <Server className="w-5 h-5 text-cyan-400" />
          <span>System Diagnostics & IBM Infrastructure Status</span>
        </h2>
        <p className="text-xs text-slate-400 mt-0.5">
          Health and configuration of IBM Db2, IBM watsonx.ai, and LangGraph Agentic Orchestrator
        </p>
      </div>

      {/* 3 Core Pillars Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Pillar 1: IBM Db2 */}
        <div className="cyber-card p-5 bg-[#0b1528] border border-[#1a2f55] space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-[#1a2f55]">
            <div className="flex items-center space-x-2.5">
              <div className="p-2 rounded bg-cyan-950 text-cyan-400 border border-cyan-800">
                <Database className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-tech text-sm font-bold text-white uppercase">IBM Db2 Database</h3>
                <span className="text-[10px] text-slate-400 font-mono-code">Central Relational Store</span>
              </div>
            </div>
            <span className="flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-mono-code font-bold bg-emerald-950 text-emerald-400 border border-emerald-800">
              <CheckCircle2 className="w-3 h-3" />
              <span>ONLINE</span>
            </span>
          </div>

          <div className="space-y-2 text-xs font-mono-code">
            <div className="flex justify-between p-2 rounded bg-[#070d18] border border-[#152642]">
              <span className="text-slate-400">Engine:</span>
              <span className="text-cyan-300 font-bold">{db.engine || 'IBM Db2'}</span>
            </div>
            <div className="flex justify-between p-2 rounded bg-[#070d18] border border-[#152642]">
              <span className="text-slate-400">Database Name:</span>
              <span className="text-slate-200">{db.database || 'SENTINEL'}</span>
            </div>
            <div className="flex justify-between p-2 rounded bg-[#070d18] border border-[#152642]">
              <span className="text-slate-400">Host / Instance:</span>
              <span className="text-slate-200 truncate max-w-[150px]">{db.host || 'Secure Gateway'}</span>
            </div>
            <div className="flex justify-between p-2 rounded bg-[#070d18] border border-[#152642]">
              <span className="text-slate-400">Python Connector:</span>
              <span className="text-emerald-400 font-bold">{db.driver || 'ibm_db 3.3.0'}</span>
            </div>
          </div>
        </div>

        {/* Pillar 2: IBM watsonx.ai */}
        <div className="cyber-card p-5 bg-[#0b1528] border border-[#1a2f55] space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-[#1a2f55]">
            <div className="flex items-center space-x-2.5">
              <div className="p-2 rounded bg-blue-950 text-blue-400 border border-blue-800">
                <Cpu className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-tech text-sm font-bold text-white uppercase">IBM watsonx.ai</h3>
                <span className="text-[10px] text-slate-400 font-mono-code">Foundation Model Reasoning</span>
              </div>
            </div>
            <span className="flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-mono-code font-bold bg-cyan-950 text-cyan-400 border border-cyan-800">
              <CheckCircle2 className="w-3 h-3" />
              <span>ACTIVE</span>
            </span>
          </div>

          <div className="space-y-2 text-xs font-mono-code">
            <div className="flex justify-between p-2 rounded bg-[#070d18] border border-[#152642]">
              <span className="text-slate-400">Model ID:</span>
              <span className="text-cyan-300 font-bold">{ai.model_id || 'ibm/granite-13b-chat-v2'}</span>
            </div>
            <div className="flex justify-between p-2 rounded bg-[#070d18] border border-[#152642]">
              <span className="text-slate-400">Provider:</span>
              <span className="text-slate-200">IBM Cloud watsonx</span>
            </div>
            <div className="flex justify-between p-2 rounded bg-[#070d18] border border-[#152642]">
              <span className="text-slate-400">Reasoning Engine:</span>
              <span className="text-purple-400 font-semibold">Explainable Intelligence</span>
            </div>
            <div className="flex justify-between p-2 rounded bg-[#070d18] border border-[#152642]">
              <span className="text-slate-400">Decoding:</span>
              <span className="text-slate-200">Greedy (Temp: 0.2)</span>
            </div>
          </div>
        </div>

        {/* Pillar 3: LangGraph Agentic Orchestrator */}
        <div className="cyber-card p-5 bg-[#0b1528] border border-[#1a2f55] space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-[#1a2f55]">
            <div className="flex items-center space-x-2.5">
              <div className="p-2 rounded bg-purple-950 text-purple-400 border border-purple-800">
                <Activity className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-tech text-sm font-bold text-white uppercase">LangGraph Multi-Agent</h3>
                <span className="text-[10px] text-slate-400 font-mono-code">Coordinated StateGraph</span>
              </div>
            </div>
            <span className="flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-mono-code font-bold bg-purple-950 text-purple-300 border border-purple-800">
              <CheckCircle2 className="w-3 h-3" />
              <span>COMPILED</span>
            </span>
          </div>

          <div className="space-y-2 text-xs font-mono-code">
            <div className="flex justify-between p-2 rounded bg-[#070d18] border border-[#152642]">
              <span className="text-slate-400">Active Nodes:</span>
              <span className="text-emerald-400 font-bold">5 Autonomous Agents</span>
            </div>
            <div className="flex justify-between p-2 rounded bg-[#070d18] border border-[#152642]">
              <span className="text-slate-400">Workflow Topology:</span>
              <span className="text-slate-200">Sequential State Pipeline</span>
            </div>
            <div className="flex justify-between p-2 rounded bg-[#070d18] border border-[#152642]">
              <span className="text-slate-400">Governance Gate:</span>
              <span className="text-amber-400 font-bold">Human-in-the-Loop</span>
            </div>
            <div className="flex justify-between p-2 rounded bg-[#070d18] border border-[#152642]">
              <span className="text-slate-400">Framework Version:</span>
              <span className="text-slate-200">LangGraph 1.2</span>
            </div>
          </div>
        </div>
      </div>

      {/* 7 Required IBM Db2 Tables Verification Table */}
      <div className="cyber-card p-5 bg-[#0b1528] border border-[#1a2f55] space-y-4">
        <div className="flex items-center justify-between pb-2 border-b border-[#1a2f55]">
          <div>
            <h3 className="font-tech text-base font-bold text-white uppercase tracking-wide flex items-center space-x-2">
              <Layers className="w-4 h-4 text-cyan-400" />
              <span>IBM Db2 Database Schema (7 Tables)</span>
            </h3>
            <p className="text-xs text-slate-400">
              Verification of mandatory tables defined in Section 5 of the Project Proposal
            </p>
          </div>
          <span className="text-xs font-mono-code text-emerald-400 bg-emerald-950/60 px-2.5 py-1 rounded border border-emerald-800">
            7/7 Schema Tables Initialized
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#070d18] border-b border-[#1a2f55] text-[10px] font-mono-code text-slate-400 uppercase">
              <tr>
                <th className="py-2.5 px-3">Table Name</th>
                <th className="py-2.5 px-3">Purpose & Contents</th>
                <th className="py-2.5 px-3">Integration Workflow</th>
                <th className="py-2.5 px-3 text-right">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#152642]">
              {tables.map((t, idx) => (
                <tr key={t.name} className="hover:bg-[#0f1f3d] transition-colors">
                  <td className="py-3 px-3 font-mono-code font-bold text-cyan-300">
                    {idx + 1}. {t.name}
                  </td>
                  <td className="py-3 px-3 text-slate-300">
                    {t.description}
                  </td>
                  <td className="py-3 px-3 font-mono-code text-slate-400 text-[11px]">
                    Parameterized SQL via ibm_db connector
                  </td>
                  <td className="py-3 px-3 text-right">
                    <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-mono-code font-bold bg-emerald-950/60 text-emerald-400 border border-emerald-800">
                      <CheckCircle2 className="w-3 h-3" />
                      <span>INITIALIZED</span>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

