import React from 'react';
import { 
  LayoutDashboard, 
  Eye, 
  Flame, 
  ShieldCheck, 
  FileText, 
  Sliders, 
  AlertTriangle,
  PlayCircle
} from 'lucide-react';

export default function Sidebar({ currentTab, setTab, pendingCount, onTriggerSimulation }) {
  const navItems = [
    { id: 'dashboard', label: 'SOC Dashboard', icon: LayoutDashboard },
    { id: 'monitoring', label: 'Live Telemetry', icon: Eye },
    { id: 'incidents', label: 'Incidents & AI', icon: Flame },
    { 
      id: 'approvals', 
      label: 'Human Approvals', 
      icon: ShieldCheck, 
      badge: pendingCount > 0 ? pendingCount : null,
      badgeColor: 'bg-amber-500'
    },
    { id: 'reports', label: 'Security Reports', icon: FileText },
    { id: 'system', label: 'Db2 & watsonx', icon: Sliders }
  ];

  return (
    <aside className="w-64 bg-[#070d18] border-r border-[#1a2f55] flex flex-col justify-between p-4 min-h-[calc(100vh-4rem)]">
      <div>
        {/* Navigation Section */}
        <div className="mb-6">
          <p className="text-[10px] font-mono-code font-semibold text-slate-500 uppercase tracking-wider mb-2 px-3">
            DEFENCE OPERATIONS
          </p>
          <nav className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = currentTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setTab(item.id)}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/40 border border-blue-400/40'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-[#0f1d36]'
                  }`}
                >
                  <div className="flex items-center space-x-3">
                    <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-slate-400'}`} />
                    <span>{item.label}</span>
                  </div>
                  {item.badge && (
                    <span className="px-1.5 py-0.5 text-[10px] font-mono-code font-bold rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/40">
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Attack Simulator Box */}
        <div className="p-3.5 rounded-lg bg-gradient-to-b from-[#111e38] to-[#0d1628] border border-crimson-900/50 relative overflow-hidden">
          <div className="flex items-center space-x-2 mb-2 text-rose-400">
            <AlertTriangle className="w-4 h-4" />
            <span className="text-xs font-bold uppercase tracking-wide">Attack Simulator</span>
          </div>
          <p className="text-[11px] text-slate-400 mb-3 leading-relaxed">
            Generate the Section 8 Attack Scenario: 15 failed logins + unfamiliar device + classified warplan access.
          </p>
          <button
            onClick={onTriggerSimulation}
            className="w-full flex items-center justify-center space-x-2 px-3 py-2 rounded bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/40 text-xs font-semibold transition-all hover:scale-[1.02]"
          >
            <PlayCircle className="w-3.5 h-3.5 text-rose-400" />
            <span>Simulate Attack</span>
          </button>
        </div>
      </div>

      {/* Footer Classification Notice */}
      <div className="pt-4 border-t border-[#1a2f55] text-[10px] text-slate-500 font-mono-code">
        <p className="text-center">RESTRICTED DEFENCE NETWORK</p>
        <p className="text-center text-slate-600">UNAUTHORIZED ACCESS PROHIBITED</p>
      </div>
    </aside>
  );
}

