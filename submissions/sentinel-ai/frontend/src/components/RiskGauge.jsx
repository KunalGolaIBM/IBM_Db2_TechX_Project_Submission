import React from 'react';
import { ShieldAlert, AlertTriangle, CheckCircle } from 'lucide-react';

export default function RiskGauge({ score = 0, severity = 'LOW' }) {
  const getSeverityConfig = (sev) => {
    switch (sev?.toUpperCase()) {
      case 'CRITICAL':
        return {
          textColor: 'text-rose-400',
          bgColor: 'bg-rose-950/60',
          borderColor: 'border-rose-600',
          barColor: 'bg-gradient-to-r from-orange-500 to-rose-600',
          glow: 'glow-crimson',
          label: 'CRITICAL THREAT'
        };
      case 'HIGH':
        return {
          textColor: 'text-orange-400',
          bgColor: 'bg-orange-950/60',
          borderColor: 'border-orange-600',
          barColor: 'bg-gradient-to-r from-amber-500 to-orange-500',
          glow: 'glow-amber',
          label: 'HIGH RISK'
        };
      case 'MEDIUM':
        return {
          textColor: 'text-amber-400',
          bgColor: 'bg-amber-950/60',
          borderColor: 'border-amber-600',
          barColor: 'bg-gradient-to-r from-yellow-500 to-amber-500',
          glow: 'glow-amber',
          label: 'ELEVATED RISK'
        };
      default:
        return {
          textColor: 'text-emerald-400',
          bgColor: 'bg-emerald-950/60',
          borderColor: 'border-emerald-600',
          barColor: 'bg-emerald-500',
          glow: 'glow-emerald',
          label: 'NOMINAL / LOW'
        };
    }
  };

  const config = getSeverityConfig(severity);

  return (
    <div className={`p-4 rounded-lg border ${config.borderColor} ${config.bgColor} ${config.glow}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-tech font-bold tracking-wider text-slate-300 uppercase">
          AI Risk Severity Assessment
        </span>
        <span className={`text-xs font-mono-code font-bold px-2 py-0.5 rounded border ${config.borderColor} ${config.textColor}`}>
          {config.label}
        </span>
      </div>

      <div className="flex items-baseline space-x-2 my-2">
        <span className={`text-4xl font-mono-code font-extrabold ${config.textColor}`}>
          {score}
        </span>
        <span className="text-sm font-mono-code text-slate-400">/ 100</span>
      </div>

      {/* Progress Bar */}
      <div className="w-full h-2.5 rounded-full bg-slate-900 border border-slate-700/60 overflow-hidden mt-2">
        <div 
          className={`h-full ${config.barColor} transition-all duration-700`}
          style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
        ></div>
      </div>

      <div className="flex justify-between text-[10px] font-mono-code text-slate-500 mt-1">
        <span>0 LOW</span>
        <span>40 MEDIUM</span>
        <span>70 HIGH</span>
        <span>90+ CRITICAL</span>
      </div>
    </div>
  );
}

