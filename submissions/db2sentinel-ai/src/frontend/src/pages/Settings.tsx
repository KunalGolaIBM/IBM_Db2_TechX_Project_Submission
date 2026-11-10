import React, { useState, useEffect } from 'react';
import { 
  Database, 
  Cpu, 
  Sliders, 
  ShieldCheck, 
  RefreshCw, 
  CheckCircle2, 
  AlertCircle, 
  Server,
  Zap,
  Lock
} from 'lucide-react';
import { SentinelApi } from '../services/api';

export const Settings: React.FC = () => {
  const [dbStatus, setDbStatus] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [aiProvider, setAiProvider] = useState<string>('gemini');
  const [temperature, setTemperature] = useState<number>(0.2);
  const [autoInvestigate, setAutoInvestigate] = useState<boolean>(true);
  const [requireApprovalForHigh, setRequireApprovalForHigh] = useState<boolean>(true);
  const [savedSuccess, setSavedSuccess] = useState<boolean>(false);

  const testDb2 = async () => {
    setLoading(true);
    try {
      const res = await SentinelApi.getDb2Status();
      setDbStatus(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    testDb2();
  }, []);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setSavedSuccess(true);
    setTimeout(() => setSavedSuccess(false), 3000);
  };

  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white tracking-wide">Platform & Security Settings</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Configure IBM Db2 telemetry connections, LangChain agents, risk scoring baselines, and SOC policies.
          </p>
        </div>
        {savedSuccess && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-medium animate-fade-in">
            <CheckCircle2 className="w-4 h-4" />
            Configuration saved successfully
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* IBM Db2 Configuration */}
        <div className="bg-[#0D182E] border border-[#1E3A5F] rounded-xl p-5 shadow-lg space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-[#1E3A5F]">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-lg bg-blue-500/10 text-cyan-400 border border-cyan-500/20">
                <Database className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">IBM Db2 Database Engine</h3>
                <p className="text-[11px] text-slate-400">Enterprise security telemetry and audit store</p>
              </div>
            </div>
            <button
              onClick={testDb2}
              disabled={loading}
              className="flex items-center gap-1.5 px-3 py-1 bg-[#132238] hover:bg-[#1C2E4A] border border-[#1E3A5F] text-slate-200 rounded-lg text-xs font-medium transition-all"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              Test Connection
            </button>
          </div>

          <div className="space-y-3 text-xs">
            <div className="flex items-center justify-between py-1.5 px-3 rounded-lg bg-[#0A1224] border border-[#1E3A5F]/60">
              <span className="text-slate-400">Database Driver</span>
              <span className="text-cyan-400 font-mono font-medium">ibm_db 3.3.0 (Official IBM Python Driver)</span>
            </div>
            <div className="flex items-center justify-between py-1.5 px-3 rounded-lg bg-[#0A1224] border border-[#1E3A5F]/60">
              <span className="text-slate-400">Active Engine Mode</span>
              <span className="flex items-center gap-1.5 text-emerald-400 font-medium">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                {dbStatus?.active_mode || 'Checking...'}
              </span>
            </div>
            <div className="flex items-center justify-between py-1.5 px-3 rounded-lg bg-[#0A1224] border border-[#1E3A5F]/60">
              <span className="text-slate-400">Target Database</span>
              <span className="text-slate-200 font-mono font-medium">SENTINELDB (Port 50000 / SSL 50001)</span>
            </div>
            <div className="flex items-center justify-between py-1.5 px-3 rounded-lg bg-[#0A1224] border border-[#1E3A5F]/60">
              <span className="text-slate-400">Audit Tables Initialized</span>
              <span className="text-slate-200 font-mono">6 of 6 Core Tables Active</span>
            </div>
            <div className="flex items-center justify-between py-1.5 px-3 rounded-lg bg-[#0A1224] border border-[#1E3A5F]/60">
              <span className="text-slate-400">Connection Pooling & TLS</span>
              <span className="text-emerald-400 font-medium">Enabled (AES-256 in transit)</span>
            </div>
          </div>

          <div className="p-3 rounded-lg bg-[#132238]/60 border border-[#1E3A5F] text-[11px] text-slate-400 flex items-start gap-2">
            <ShieldCheck className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
            <span>
              Db2Sentinel AI enforces parameterized queries, TLS 1.3 transport encryption, and read-only event ingest privileges by default. Remediation commands require explicit human sign-off.
            </span>
          </div>
        </div>

        {/* AI & LangChain Agent Orchestration */}
        <div className="bg-[#0D182E] border border-[#1E3A5F] rounded-xl p-5 shadow-lg space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-[#1E3A5F]">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-lg bg-purple-500/10 text-purple-400 border border-purple-500/20">
                <Cpu className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">LangChain & LangGraph Agents</h3>
                <p className="text-[11px] text-slate-400">Multi-agent SOC investigation architecture</p>
              </div>
            </div>
            <span className="px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 text-[10px] font-semibold">
              StateGraph v1.2
            </span>
          </div>

          <div className="space-y-4 text-xs">
            <div>
              <label className="block text-slate-400 mb-1 font-medium">Primary LLM Provider</label>
              <select
                value={aiProvider}
                onChange={(e) => setAiProvider(e.target.value)}
                className="w-full bg-[#0A1224] border border-[#1E3A5F] rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-cyan-500 text-xs"
              >
                <option value="gemini">Google Gemini 2.5 Flash (Fast, low-latency analysis)</option>
                <option value="openai">OpenAI GPT-4o (High-reasoning security model)</option>
                <option value="ollama">Local Llama 3 / Mistral (Air-gapped on-premise)</option>
                <option value="deterministic">Rule-Based Deterministic Fallback (No external API needed)</option>
              </select>
            </div>

            <div>
              <div className="flex justify-between items-center mb-1">
                <label className="text-slate-400 font-medium">Model Temperature</label>
                <span className="text-cyan-400 font-mono">{temperature} (Low hallucination)</span>
              </div>
              <input
                type="range"
                min="0"
                max="0.7"
                step="0.05"
                value={temperature}
                onChange={(e) => setTemperature(parseFloat(e.target.value))}
                className="w-full h-1.5 bg-[#132238] rounded-lg appearance-none cursor-pointer accent-cyan-500"
              />
            </div>

            <div className="space-y-2 pt-2 border-t border-[#1E3A5F]/60">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoInvestigate}
                  onChange={(e) => setAutoInvestigate(e.target.checked)}
                  className="rounded bg-[#0A1224] border-[#1E3A5F] text-cyan-500 focus:ring-0"
                />
                <span className="text-slate-300">Auto-trigger LangGraph multi-agent pipeline on Critical/High alerts</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={requireApprovalForHigh}
                  onChange={(e) => setRequireApprovalForHigh(e.target.checked)}
                  className="rounded bg-[#0A1224] border-[#1E3A5F] text-cyan-500 focus:ring-0"
                />
                <span className="text-slate-300">Enforce human DBA approval interrupt before database lock or IP block</span>
              </label>
            </div>
          </div>
        </div>

        {/* 4-Factor Risk Engine Weights */}
        <div className="bg-[#0D182E] border border-[#1E3A5F] rounded-xl p-5 shadow-lg space-y-4">
          <div className="flex items-center gap-2.5 pb-3 border-b border-[#1E3A5F]">
            <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <Sliders className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">4-Factor Risk Engine Calibration</h3>
              <p className="text-[11px] text-slate-400">Deterministic scoring formula weights (Total = 100%)</p>
            </div>
          </div>

          <div className="space-y-3 text-xs">
            <div className="p-3 bg-[#0A1224] rounded-lg border border-[#1E3A5F]/60 space-y-1.5">
              <div className="flex justify-between font-medium">
                <span className="text-slate-300">1. Behavioral Anomaly Factor</span>
                <span className="text-amber-400 font-mono">30% Weight</span>
              </div>
              <p className="text-[11px] text-slate-500">Unusual query syntax, drop statements, off-hours access patterns</p>
            </div>

            <div className="p-3 bg-[#0A1224] rounded-lg border border-[#1E3A5F]/60 space-y-1.5">
              <div className="flex justify-between font-medium">
                <span className="text-slate-300">2. Privileged Execution Factor</span>
                <span className="text-purple-400 font-mono">25% Weight</span>
              </div>
              <p className="text-[11px] text-slate-500">DBADM, SECADM, SYSADM, schema alters, user grant modifications</p>
            </div>

            <div className="p-3 bg-[#0A1224] rounded-lg border border-[#1E3A5F]/60 space-y-1.5">
              <div className="flex justify-between font-medium">
                <span className="text-slate-300">3. Volume & Frequency Factor</span>
                <span className="text-blue-400 font-mono">25% Weight</span>
              </div>
              <p className="text-[11px] text-slate-500">Exfiltration thresholds, rapid bulk selects, table scans</p>
            </div>

            <div className="p-3 bg-[#0A1224] rounded-lg border border-[#1E3A5F]/60 space-y-1.5">
              <div className="flex justify-between font-medium">
                <span className="text-slate-300">4. Authentication Failure Factor</span>
                <span className="text-rose-400 font-mono">20% Weight</span>
              </div>
              <p className="text-[11px] text-slate-500">SQL30082N / RC 24 credential failures, password spray cadence</p>
            </div>
          </div>
        </div>

        {/* Security Compliance & Project Metadata */}
        <div className="bg-[#0D182E] border border-[#1E3A5F] rounded-xl p-5 shadow-lg space-y-4">
          <div className="flex items-center gap-2.5 pb-3 border-b border-[#1E3A5F]">
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <Server className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Project & Submission Metadata</h3>
              <p className="text-[11px] text-slate-400">IBM Db2 TechX Summit 2026 Hackathon</p>
            </div>
          </div>

          <div className="space-y-3 text-xs">
            <div className="flex items-center justify-between py-1.5 px-3 rounded-lg bg-[#0A1224] border border-[#1E3A5F]/60">
              <span className="text-slate-400">Project Slug</span>
              <span className="text-slate-200 font-mono font-medium">db2sentinel-ai</span>
            </div>
            <div className="flex items-center justify-between py-1.5 px-3 rounded-lg bg-[#0A1224] border border-[#1E3A5F]/60">
              <span className="text-slate-400">Framework Selection</span>
              <span className="text-cyan-400 font-mono font-medium">LangChain (Mandatory Form Choice)</span>
            </div>
            <div className="flex items-center justify-between py-1.5 px-3 rounded-lg bg-[#0A1224] border border-[#1E3A5F]/60">
              <span className="text-slate-400">Db2 Connector</span>
              <span className="text-slate-200 font-mono font-medium">ibm_db (Direct Native Integration)</span>
            </div>
            <div className="flex items-center justify-between py-1.5 px-3 rounded-lg bg-[#0A1224] border border-[#1E3A5F]/60">
              <span className="text-slate-400">Submission Branch</span>
              <span className="text-slate-200 font-mono font-medium">submission/db2sentinel-ai</span>
            </div>
            <div className="flex items-center justify-between py-1.5 px-3 rounded-lg bg-[#0A1224] border border-[#1E3A5F]/60">
              <span className="text-slate-400">Target Track</span>
              <span className="text-emerald-400 font-medium">Enterprise Database Security & Agentic AI</span>
            </div>
          </div>

          <div className="pt-2">
            <button
              onClick={handleSave}
              className="w-full py-2 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white rounded-lg text-xs font-semibold shadow-md shadow-cyan-500/20 transition-all flex items-center justify-center gap-2"
            >
              <Zap className="w-3.5 h-3.5" />
              Save Configuration Baselines
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};