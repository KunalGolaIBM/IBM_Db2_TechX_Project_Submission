import React from 'react';
import { LucideIcon } from 'lucide-react';

interface Props {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  color?: string;
}

export const MetricCard: React.FC<Props> = ({ title, value, subtitle, icon: Icon, color = 'text-cyan-400' }) => {
  return (
    <div className="bg-[#132238] border border-[#1E3A5F] rounded-xl p-5 hover:border-cyan-500/40 transition-all shadow-lg">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{title}</span>
        <div className={`p-2 rounded-lg bg-[#1C2E4A] ${color}`}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
      <div className="mt-3">
        <div className="text-2xl font-bold text-white tracking-tight">{value}</div>
        {subtitle && <p className="text-xs text-slate-400 mt-1">{subtitle}</p>}
      </div>
    </div>
  );
};
