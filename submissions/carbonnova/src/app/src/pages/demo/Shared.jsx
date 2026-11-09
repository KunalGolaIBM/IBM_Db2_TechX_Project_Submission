import React from 'react';
export const Page = ({ title, subtitle, children, actions }) => (
  <div className="space-y-5 max-w-7xl mx-auto">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h1 className="text-2xl font-extrabold text-[#10271E]">{title}</h1>{subtitle && <p className="text-sm text-[#617E6F] mt-1">{subtitle}</p>}</div>{actions}</div>
    {children}
  </div>
);
export const Card = ({ children, className='' }) => <div className={`bg-white border border-[#DCE6DE] rounded-2xl p-5 shadow-sm ${className}`}>{children}</div>;
export const Badge = ({ children, tone='neutral' }) => {
  const tones = { neutral:'bg-[#F3F7F4] text-[#355848]', green:'bg-emerald-50 text-emerald-800', amber:'bg-amber-50 text-amber-800', red:'bg-red-50 text-red-700', blue:'bg-blue-50 text-blue-800' };
  return <span className={`inline-flex items-center text-[11px] font-bold px-2 py-1 rounded-full ${tones[tone]||tones.neutral}`}>{children}</span>;
};
export const Table = ({ cols, rows, empty='No records found.' }) => (
  <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b border-[#E6EEE8]">{cols.map(c=><th key={c} className="text-left text-[11px] uppercase tracking-wide text-[#5B7767] font-bold py-2 pr-3">{c}</th>)}</tr></thead><tbody>{rows.length?rows.map((r,i)=><tr key={i} className="border-b border-[#F0F4F1] align-top">{r.map((cell,j)=><td key={j} className="py-2.5 pr-3">{cell}</td>)}</tr>):<tr><td colSpan={cols.length} className="py-6 text-center text-[#6A8576]">{empty}</td></tr>}</tbody></table></div>
);
export const Btn = ({ children, variant='primary', ...p }) => {
  const v = { primary:'bg-[#0C3327] text-white hover:bg-[#124C3A]', secondary:'bg-[#F3FAF6] text-[#0C3327] border border-[#CFE3D6] hover:bg-[#E8F5EE]', danger:'bg-red-50 text-red-700 border border-red-200 hover:bg-red-100' };
  return <button {...p} className={`text-sm font-semibold px-3 py-2 rounded-xl transition-colors disabled:opacity-50 ${v[variant]||v.primary} ${p.className||''}`}>{children}</button>;
};
export const Field = ({ label, children }) => <label className="block"><span className="block text-xs font-semibold text-[#355848] mb-1">{label}</span>{children}</label>;
export const Input = (p) => <input {...p} className={`w-full border border-[#D8E2D9] rounded-xl px-3 py-2 text-sm bg-[#FBFCFA] ${p.className||''}`} />;
export const Select = (p) => <select {...p} className={`w-full border border-[#D8E2D9] rounded-xl px-3 py-2 text-sm bg-[#FBFCFA] ${p.className||''}`} />;
export function toneForStatus(s='') { const v=String(s).toLowerCase(); if(['approved','verified','completed','active'].some(x=>v.includes(x))) return 'green'; if(['pending','submitted','under_review','review','needs'].some(x=>v.includes(x))) return 'amber'; if(['reject','suspend','ban','sold_out'].some(x=>v.includes(x))) return 'red'; return 'neutral'; }
