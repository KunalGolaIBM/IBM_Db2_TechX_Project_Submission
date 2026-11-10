import React from 'react';
import { NavLink } from 'react-router-dom';
import { 
  ShieldAlert, 
  LayoutDashboard, 
  Database, 
  AlertTriangle, 
  FileSearch, 
  Workflow, 
  CheckCircle2, 
  Settings 
} from 'lucide-react';

const navItems = [
  { name: 'Overview', path: '/', icon: LayoutDashboard },
  { name: 'Database Events', path: '/events', icon: Database },
  { name: 'Security Alerts', path: '/alerts', icon: AlertTriangle },
  { name: 'Incidents', path: '/incidents', icon: FileSearch },
  { name: 'AI Investigation', path: '/investigation', icon: Workflow },
  { name: 'Human Approvals', path: '/approvals', icon: CheckCircle2 },
  { name: 'Settings', path: '/settings', icon: Settings },
];

export const Sidebar: React.FC = () => {
  return (
    <aside className="w-64 bg-[#0D182E] border-r border-[#1E3A5F] flex flex-col justify-between shrink-0 h-screen sticky top-0">
      <div>
        {/* Brand */}
        <div className="h-16 flex items-center px-6 border-b border-[#1E3A5F] gap-3">
          <div className="p-2 bg-gradient-to-tr from-blue-600 to-cyan-500 rounded-lg text-white shadow-md shadow-cyan-500/20">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <h1 className="font-bold text-white tracking-wide text-base leading-none">Db2Sentinel AI</h1>
            <span className="text-[10px] text-cyan-400 font-semibold uppercase tracking-wider">Enterprise SOC</span>
          </div>
        </div>

        {/* Navigation */}
        <nav className="p-4 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-blue-600 text-white font-semibold shadow-md shadow-blue-500/20'
                    : 'text-slate-400 hover:text-slate-100 hover:bg-[#132238]'
                }`
              }
            >
              <item.icon className="w-4 h-4" />
              {item.name}
            </NavLink>
          ))}
        </nav>
      </div>

      {/* Footer Info */}
      <div className="p-4 border-t border-[#1E3A5F] bg-[#0A1224]">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span className="text-xs text-slate-300 font-medium">IBM Db2 Engine Active</span>
        </div>
        <p className="text-[11px] text-slate-500 mt-1">Db2Hack 2026 Submission</p>
      </div>
    </aside>
  );
};
