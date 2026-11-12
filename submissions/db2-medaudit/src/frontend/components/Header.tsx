import React, { useEffect, useState } from 'react';
import { ShieldAlert, Database, Stethoscope, FileCode2, Network, Download, Activity } from 'lucide-react';

interface HeaderProps {
  activeTab: 'audit' | 'matrix' | 'db2' | 'setup';
  onSelectTab: (tab: 'audit' | 'matrix' | 'db2' | 'setup') => void;
  onQuickAuditClick: () => void;
}

export const Header: React.FC<HeaderProps> = ({ activeTab, onSelectTab, onQuickAuditClick }) => {
  const [stats, setStats] = useState<{ guidelinesCount: number; doctorsMonitored: number; flaggedKickbackContracts: number; highRiskDoctors: number; avgCommissionRate: number; auditsRunThisSession: number } | null>(null);

  useEffect(() => {
    fetch('/api/db2/stats')
      .then(r => r.json())
      .then(setStats)
      .catch(() => null);
  }, []);

  return (
    <header className="sticky top-0 z-40 bg-white/95 backdrop-blur border-b border-slate-200">
      {/* DB2 Live Stats Ribbon */}
      {stats && (
        <div className="bg-slate-900 text-slate-300 text-[10px] font-mono border-b border-slate-700">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-7 flex items-center gap-6 overflow-x-auto">
            <span className="flex items-center gap-1.5 text-sky-400 font-semibold whitespace-nowrap shrink-0">
              <Activity className="w-3 h-3" />
              IBM DB2 LIVE
            </span>
            <span className="whitespace-nowrap shrink-0">Guidelines: <span className="text-white font-bold">{stats.guidelinesCount}</span></span>
            <span className="whitespace-nowrap shrink-0">Doctors Monitored: <span className="text-white font-bold">{stats.doctorsMonitored}</span></span>
            <span className="whitespace-nowrap shrink-0">High-Risk Physicians: <span className="text-red-400 font-bold">{stats.highRiskDoctors}</span></span>
            <span className="whitespace-nowrap shrink-0">Kickback Contracts: <span className="text-rose-400 font-bold">{stats.flaggedKickbackContracts}</span></span>
            <span className="whitespace-nowrap shrink-0">Avg Commission: <span className="text-orange-400 font-bold">{stats.avgCommissionRate}%</span></span>
            <span className="whitespace-nowrap shrink-0">Audits This Session: <span className="text-emerald-400 font-bold">{stats.auditsRunThisSession}</span></span>
          </div>
        </div>
      )}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-8">
        
        {/* Zone 1: Single text element wordmark with icon */}
        <div 
          onClick={() => onSelectTab('audit')} 
          className="flex items-center gap-2.5 cursor-pointer whitespace-nowrap shrink-0 group"
        >
          <div className="w-9 h-9 rounded-lg bg-sky-600 flex items-center justify-center text-white shadow-xs group-hover:bg-sky-700 transition-colors">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div>
            <span className="text-lg font-bold tracking-tight text-slate-900 block leading-tight">
              DB2 MedAudit
            </span>
            <span className="text-[11px] font-medium text-slate-500 block leading-none">
              Clinical Test & Kickback Verifier
            </span>
          </div>
        </div>

        {/* Zone 2: 4 clean single-line text navigation links */}
        <nav className="hidden md:flex items-center gap-8 text-sm font-medium text-slate-600">
          <button
            onClick={() => onSelectTab('audit')}
            className={`flex items-center gap-2 pb-1 border-b-2 transition-colors whitespace-nowrap shrink-0 ${
              activeTab === 'audit'
                ? 'border-sky-600 text-sky-700 font-semibold'
                : 'border-transparent hover:text-slate-900 hover:border-slate-300'
            }`}
          >
            <Stethoscope className="w-4 h-4" />
            Audit Prescription
          </button>

          <button
            onClick={() => onSelectTab('matrix')}
            className={`flex items-center gap-2 pb-1 border-b-2 transition-colors whitespace-nowrap shrink-0 ${
              activeTab === 'matrix'
                ? 'border-sky-600 text-sky-700 font-semibold'
                : 'border-transparent hover:text-slate-900 hover:border-slate-300'
            }`}
          >
            <Network className="w-4 h-4" />
            Kickback Matrix
          </button>

          <button
            onClick={() => onSelectTab('db2')}
            className={`flex items-center gap-2 pb-1 border-b-2 transition-colors whitespace-nowrap shrink-0 ${
              activeTab === 'db2'
                ? 'border-sky-600 text-sky-700 font-semibold'
                : 'border-transparent hover:text-slate-900 hover:border-slate-300'
            }`}
          >
            <Database className="w-4 h-4" />
            IBM DB2 Studio
          </button>

          <button
            onClick={() => onSelectTab('setup')}
            className={`flex items-center gap-2 pb-1 border-b-2 transition-colors whitespace-nowrap shrink-0 ${
              activeTab === 'setup'
                ? 'border-sky-600 text-sky-700 font-semibold'
                : 'border-transparent hover:text-slate-900 hover:border-slate-300'
            }`}
          >
            <FileCode2 className="w-4 h-4" />
            Package & Setup Guide
          </button>
        </nav>

        {/* Zone 3: Primary action & ZIP download */}
        <div className="flex items-center gap-2.5 shrink-0">
          <a
            href="/db2-medaudit-solution.zip"
            download="db2-medaudit-solution.zip"
            className="px-3 py-1.5 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 active:scale-98 transition-all rounded-lg flex items-center gap-1.5 whitespace-nowrap shrink-0 border border-slate-200"
            title="Download full project ZIP archive"
          >
            <Download className="w-3.5 h-3.5 text-slate-600" />
            <span>Download ZIP</span>
          </a>

          <button
            onClick={onQuickAuditClick}
            className="px-3.5 py-1.5 text-xs font-semibold text-white bg-sky-700 rounded-lg hover:bg-sky-800 active:scale-98 transition-all shadow-xs flex items-center gap-1.5 whitespace-nowrap shrink-0"
          >
            <Stethoscope className="w-3.5 h-3.5" />
            <span>Load Sample Case</span>
          </button>
        </div>

      </div>

      {/* Mobile subnav */}
      <div className="md:hidden flex overflow-x-auto px-4 py-2 gap-4 border-t border-slate-100 bg-slate-50 text-xs font-medium">
        <button
          onClick={() => onSelectTab('audit')}
          className={`whitespace-nowrap px-2.5 py-1 rounded-md ${activeTab === 'audit' ? 'bg-sky-600 text-white' : 'text-slate-600'}`}
        >
          Prescription Audit
        </button>
        <button
          onClick={() => onSelectTab('matrix')}
          className={`whitespace-nowrap px-2.5 py-1 rounded-md ${activeTab === 'matrix' ? 'bg-sky-600 text-white' : 'text-slate-600'}`}
        >
          Kickback Matrix
        </button>
        <button
          onClick={() => onSelectTab('db2')}
          className={`whitespace-nowrap px-2.5 py-1 rounded-md ${activeTab === 'db2' ? 'bg-sky-600 text-white' : 'text-slate-600'}`}
        >
          IBM DB2 Studio
        </button>
        <button
          onClick={() => onSelectTab('setup')}
          className={`whitespace-nowrap px-2.5 py-1 rounded-md ${activeTab === 'setup' ? 'bg-sky-600 text-white' : 'text-slate-600'}`}
        >
          Package Setup
        </button>
      </div>
    </header>
  );
};
