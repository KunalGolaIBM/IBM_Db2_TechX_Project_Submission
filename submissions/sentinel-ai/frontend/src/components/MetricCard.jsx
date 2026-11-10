import React from 'react';

export default function MetricCard({ title, value, subtitle, icon: Icon, color = 'blue', trend }) {
  const colorMap = {
    blue: {
      border: 'border-blue-900/60',
      text: 'text-blue-400',
      bgIcon: 'bg-blue-950/60 text-blue-400 border border-blue-800/40',
      glow: 'glow-blue'
    },
    cyan: {
      border: 'border-cyan-900/60',
      text: 'text-cyan-400',
      bgIcon: 'bg-cyan-950/60 text-cyan-400 border border-cyan-800/40',
      glow: 'glow-cyan'
    },
    rose: {
      border: 'border-rose-900/60',
      text: 'text-rose-400',
      bgIcon: 'bg-rose-950/60 text-rose-400 border border-rose-800/40',
      glow: 'glow-crimson'
    },
    amber: {
      border: 'border-amber-900/60',
      text: 'text-amber-400',
      bgIcon: 'bg-amber-950/60 text-amber-400 border border-amber-800/40',
      glow: 'glow-amber'
    },
    emerald: {
      border: 'border-emerald-900/60',
      text: 'text-emerald-400',
      bgIcon: 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/40',
      glow: 'glow-emerald'
    }
  };

  const scheme = colorMap[color] || colorMap.blue;

  return (
    <div className={`cyber-card p-4 bg-[#0b1528] border ${scheme.border} relative overflow-hidden group`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-slate-400 tracking-wide uppercase font-tech">{title}</p>
          <div className="flex items-baseline space-x-2 mt-1">
            <span className="text-2xl lg:text-3xl font-bold font-mono-code text-white tracking-tight">{value}</span>
            {trend && (
              <span className={`text-[11px] font-mono-code font-semibold ${scheme.text}`}>
                {trend}
              </span>
            )}
          </div>
          {subtitle && (
            <p className="text-[11px] text-slate-400 mt-1 font-mono-code">{subtitle}</p>
          )}
        </div>
        <div className={`p-2.5 rounded-lg ${scheme.bgIcon}`}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
      <div className={`absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-transparent via-${color}-500 to-transparent opacity-40 group-hover:opacity-100 transition-opacity`}></div>
    </div>
  );
}

