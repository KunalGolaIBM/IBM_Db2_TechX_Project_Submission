import React, { useState, useEffect } from 'react';
import { ShieldAlert, Database, Cpu, Activity, UserCheck, Clock } from 'lucide-react';

export default function Navbar({ systemStatus }) {
  const [time, setTime] = useState(new Date().toUTCString().slice(17, 25) + ' UTC');

  useEffect(() => {
    const timer = setInterval(() => {
      setTime(new Date().toUTCString().slice(17, 25) + ' UTC');
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const dbActive = systemStatus?.database?.is_db2_active;
  const dbEngine = systemStatus?.database?.engine || 'IBM Db2';
  const aiEngine = systemStatus?.ai_engine?.model_id || 'IBM watsonx.ai Granite';

  return (
    <header className="h-16 bg-[#070d18] border-b border-[#1a2f55] px-6 flex items-center justify-between sticky top-0 z-50">
      {/* Brand & Tagline */}
      <div className="flex items-center space-x-4">
        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-600 via-indigo-600 to-cyan-500 p-0.5 flex items-center justify-center glow-blue">
          <div className="w-full h-full bg-[#070d18] rounded-[7px] flex items-center justify-center">
            <ShieldAlert className="w-5 h-5 text-cyan-400" />
          </div>
        </div>
        <div>
          <div className="flex items-center space-x-2">
            <span className="font-tech text-xl font-bold tracking-wider text-white">SENTINEL AI</span>
            <span className="text-[10px] font-mono-code px-1.5 py-0.5 rounded bg-blue-950/80 text-blue-400 border border-blue-800/60 uppercase">
              MIL-SPEC DEFENCE v1.0
            </span>
          </div>
          <p className="text-[11px] text-slate-400 font-medium">Detect Early. Analyse Smartly. Defend Strongly.</p>
        </div>
      </div>

      {/* System Telemetry Badges */}
      <div className="hidden lg:flex items-center space-x-3 text-xs">
        {/* IBM Db2 Badge */}
        <div className="flex items-center space-x-2 px-3 py-1.5 rounded-md bg-[#0b1528] border border-[#1a2f55]">
          <Database className={`w-3.5 h-3.5 ${dbActive ? 'text-emerald-400' : 'text-cyan-400'}`} />
          <div>
            <span className="text-slate-400 text-[10px] block leading-none">CENTRAL DB</span>
            <span className="font-mono-code text-[11px] font-semibold text-slate-200">
              {dbActive ? 'IBM Db2 (Live)' : 'IBM Db2 (Ready)'}
            </span>
          </div>
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
        </div>

        {/* IBM watsonx.ai Badge */}
        <div className="flex items-center space-x-2 px-3 py-1.5 rounded-md bg-[#0b1528] border border-[#1a2f55]">
          <Cpu className="w-3.5 h-3.5 text-blue-400" />
          <div>
            <span className="text-slate-400 text-[10px] block leading-none">AI REASONING</span>
            <span className="font-mono-code text-[11px] font-semibold text-slate-200">
              watsonx.ai (Granite)
            </span>
          </div>
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
        </div>

        {/* LangGraph Orchestrator */}
        <div className="flex items-center space-x-2 px-3 py-1.5 rounded-md bg-[#0b1528] border border-[#1a2f55]">
          <Activity className="w-3.5 h-3.5 text-purple-400" />
          <div>
            <span className="text-slate-400 text-[10px] block leading-none">ORCHESTRATOR</span>
            <span className="font-mono-code text-[11px] font-semibold text-slate-200">LangGraph (5 Agents)</span>
          </div>
          <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
        </div>
      </div>

      {/* Military Clock & Operator Profile */}
      <div className="flex items-center space-x-4">
        <div className="hidden sm:flex items-center space-x-1.5 text-xs font-mono-code text-cyan-300 bg-cyan-950/40 px-2.5 py-1 rounded border border-cyan-800/40">
          <Clock className="w-3.5 h-3.5 text-cyan-400" />
          <span>{time}</span>
        </div>

        <div className="flex items-center space-x-2.5 pl-3 border-l border-[#1a2f55]">
          <div className="w-8 h-8 rounded-full bg-blue-900/60 border border-blue-600 flex items-center justify-center text-xs font-bold text-blue-300">
            CISO
          </div>
          <div className="hidden md:block text-left text-xs">
            <p className="font-semibold text-slate-200 leading-tight">Cyber Commander</p>
            <p className="text-[10px] text-emerald-400 font-mono-code">TOP SECRET // SCI</p>
          </div>
        </div>
      </div>
    </header>
  );
}

