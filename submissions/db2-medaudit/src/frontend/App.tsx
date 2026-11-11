import React, { useState } from 'react';
import { Header } from './components/Header';
import { AuditWorkspace } from './components/AuditWorkspace';
import { KickbackMatrix } from './components/KickbackMatrix';
import { DB2Studio } from './components/DB2Studio';
import { SetupGuide } from './components/SetupGuide';
import { ShieldCheck, Database, Stethoscope, Github } from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState<'audit' | 'matrix' | 'db2' | 'setup'>('audit');

  const handleQuickAudit = () => {
    setActiveTab('audit');
    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans text-slate-900 selection:bg-sky-100 selection:text-sky-900">
      
      {/* Top Bar Navigation */}
      <Header
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        onQuickAuditClick={handleQuickAudit}
      />

      {/* Main View Area */}
      <main className="flex-1">
        {activeTab === 'audit' && (
          <AuditWorkspace onOpenDB2={() => setActiveTab('db2')} />
        )}

        {activeTab === 'matrix' && (
          <KickbackMatrix />
        )}

        {activeTab === 'db2' && (
          <DB2Studio />
        )}

        {activeTab === 'setup' && (
          <SetupGuide />
        )}
      </main>

      {/* Footer conforming to Design Constitution */}
      <footer className="mt-16 bg-white border-t border-slate-200 py-8 text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-sky-600" />
            <span className="font-semibold text-slate-700">DB2 MedAudit</span>
            <span>·</span>
            <span>Protecting Patients through Clinical Transparency & IBM DB2 Intelligence</span>
          </div>

          <div className="flex items-center gap-6">
            <button
              onClick={() => setActiveTab('setup')}
              className="hover:text-slate-800 transition-colors"
            >
              Setup Blueprint
            </button>
            <button
              onClick={() => setActiveTab('db2')}
              className="hover:text-slate-800 transition-colors"
            >
              DB2 DDL Schema
            </button>
            <button
              onClick={() => setActiveTab('matrix')}
              className="hover:text-slate-800 transition-colors"
            >
              Kickback Registry
            </button>
          </div>
        </div>
      </footer>

    </div>
  );
}
