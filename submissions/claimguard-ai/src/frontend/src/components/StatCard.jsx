import React from 'react';

export default function StatCard({ title, value, subtitle, icon: Icon, color = 'blue' }) {
  const colorMap = {
    blue: 'text-[#0F62FE] bg-[#EDF5FF]',
    green: 'text-[#198038] bg-[#DEFBE6]',
    amber: 'text-[#B28600] bg-[#FDF3D8]',
    red: 'text-[#DA1E28] bg-[#FFF1F1]',
    purple: 'text-[#8A3FFC] bg-[#F6F2FF]',
  };

  return (
    <div className="bg-white border border-[#E0E0E0] p-4 rounded-sm shadow-sm hover:shadow transition-shadow">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-[#525252] uppercase tracking-wide font-mono">
          {title}
        </p>
        {Icon && (
          <div className={`p-1.5 rounded ${colorMap[color] || colorMap.blue}`}>
            <Icon className="w-4 h-4" />
          </div>
        )}
      </div>

      <div className="mt-2">
        <h3 className="text-2xl font-bold text-[#161616] tracking-tight">{value}</h3>
        {subtitle && (
          <p className="text-[11px] text-[#525252] mt-1 flex items-center space-x-1">
            <span>{subtitle}</span>
          </p>
        )}
      </div>
    </div>
  );
}
