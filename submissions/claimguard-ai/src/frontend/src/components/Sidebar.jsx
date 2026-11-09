import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  FilePlus,
  Files,
  ShieldAlert,
  Sparkles,
  BookOpen,
  History,
  Settings,
  ShieldCheck,
  Cpu
} from 'lucide-react';

const navItems = [
  { name: 'Dashboard', path: '/', icon: LayoutDashboard },
  { name: 'Submit New Claim', path: '/submit-claim', icon: FilePlus },
  { name: 'Claims Management', path: '/claims', icon: Files },
  { name: 'Fraud Detection', path: '/fraud-detection', icon: ShieldAlert },
  { name: 'AI Verification Reports', path: '/reports', icon: Sparkles },
  { name: 'Policy Management', path: '/policies', icon: BookOpen },
  { name: 'Audit Logs', path: '/audit-logs', icon: History },
  { name: 'System Settings', path: '/settings', icon: Settings },
];

export default function Sidebar() {
  return (
    <aside className="w-60 bg-white border-r border-[#E0E0E0] flex flex-col justify-between shrink-0 h-[calc(100vh-3rem)]">
      <div className="py-4">
        <div className="px-4 pb-3 mb-2 border-b border-gray-100">
          <p className="text-[11px] font-semibold tracking-wider text-gray-400 uppercase font-mono">
            Navigation
          </p>
        </div>

        <nav className="space-y-0.5 px-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  `flex items-center space-x-3 px-3 py-2 text-xs font-medium rounded-sm transition-colors ${
                    isActive
                      ? 'bg-[#EBF1FF] text-[#0F62FE] border-l-4 border-[#0F62FE] font-semibold'
                      : 'text-[#525252] hover:bg-gray-100 hover:text-[#161616]'
                  }`
                }
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span>{item.name}</span>
              </NavLink>
            );
          })}
        </nav>
      </div>

      {/* Footer Info Box */}
      <div className="p-4 border-t border-[#E0E0E0] bg-[#F4F4F4]">
        <div className="flex items-center space-x-2 text-xs text-[#525252]">
          <Cpu className="w-3.5 h-3.5 text-[#0F62FE]" />
          <span className="font-semibold text-gray-800">IBM Db2 & LangGraph</span>
        </div>
        <p className="text-[11px] text-gray-500 mt-1">
          Agentic Insurance Adjudication System
        </p>
      </div>
    </aside>
  );
}
