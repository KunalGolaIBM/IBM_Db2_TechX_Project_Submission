import React, { useState } from 'react';
import {
  Compass,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Layers,
  HelpCircle
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { UserRole } from '../types';

interface DemoJourneyGuideProps {
  onNavigateTab: (tabId: string) => void;
  onOpenReportPotholePreset: () => void;
}

export const DemoJourneyGuide: React.FC<DemoJourneyGuideProps> = ({
  onNavigateTab,
  onOpenReportPotholePreset
}) => {
  const [collapsed, setCollapsed] = useState(false);
  const { activeRole, setActiveRole, setActiveDepartment, loginAsDemoPersona, currentUser } = useAuth();

  const switchTo = async (role: UserRole, dept = 'Public Works Department') => {
    setActiveRole(role);
    if (role === 'staff') {
      setActiveDepartment(dept);
    }
    if (!currentUser) {
      await loginAsDemoPersona(role, dept);
    }
  };

  const steps = [
    {
      num: 1,
      role: 'citizen' as UserRole,
      title: 'Report Pothole',
      desc: 'Citizen submits complaint with photo & AI assistant',
      actionText: 'Report Issue',
      action: () => {
        switchTo('citizen');
        onNavigateTab('citizen-report');
        onOpenReportPotholePreset();
      }
    },
    {
      num: 2,
      role: 'admin' as UserRole,
      title: 'Assign to PWD',
      desc: 'Admin reviews new complaint & assigns Public Works',
      actionText: 'Admin Dashboard',
      action: () => {
        switchTo('admin');
        onNavigateTab('admin-dashboard');
      }
    },
    {
      num: 3,
      role: 'staff' as UserRole,
      title: 'Work & Resolve',
      desc: 'PWD staff marks In Progress, adds resolution proof',
      actionText: 'Staff Portal',
      action: () => {
        switchTo('staff', 'Public Works Department');
        onNavigateTab('staff-dashboard');
      }
    },
    {
      num: 4,
      role: 'citizen' as UserRole,
      title: 'Audit & Feedback',
      desc: 'Citizen tracks timeline, reopens or rates service',
      actionText: 'Track Timeline',
      action: () => {
        switchTo('citizen');
        onNavigateTab('citizen-complaints');
      }
    }
  ];

  return (
    <div className="bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 border-b border-teal-500/30 text-white shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-teal-500/20 text-teal-400 border border-teal-500/30">
              <Compass className="w-4 h-4" />
            </div>
            <div>
              <span className="text-xs sm:text-sm font-semibold text-white">Full-Stack Demo Journey Walkthrough</span>
              <span className="hidden md:inline text-xs text-slate-400 ml-2">
                Evaluate all 9 steps: Citizen report &rarr; Admin assignment &rarr; Staff resolution &rarr; Live analytics
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setCollapsed(!collapsed)}
              className="text-xs flex items-center gap-1 text-slate-400 hover:text-white px-2 py-1 rounded hover:bg-slate-800 transition"
            >
              <span>{collapsed ? 'Show Journey Steps' : 'Hide'}</span>
              {collapsed ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronUp className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>

        {!collapsed && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5 mt-2.5 pt-2 border-t border-slate-700/60">
            {steps.map((st) => {
              const isCurrentRole = activeRole === st.role;
              return (
                <div
                  key={st.num}
                  className={`p-2.5 rounded-xl border transition-all ${
                    isCurrentRole
                      ? 'bg-teal-950/40 border-teal-500/50 shadow-sm'
                      : 'bg-slate-800/60 border-slate-700 hover:border-slate-600'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-teal-400">
                      Step {st.num} • {st.role}
                    </span>
                    {isCurrentRole && (
                      <span className="text-[10px] bg-teal-500/20 text-teal-300 px-1.5 py-0.2 rounded font-medium">
                        Active
                      </span>
                    )}
                  </div>
                  <h4 className="text-xs font-semibold text-white">{st.title}</h4>
                  <p className="text-[11px] text-slate-300 mt-0.5 line-clamp-1">{st.desc}</p>
                  <button
                    type="button"
                    onClick={st.action}
                    className="mt-2 w-full flex items-center justify-center gap-1.5 py-1 text-xs font-medium rounded-lg bg-slate-700 hover:bg-teal-600 text-slate-200 hover:text-white transition"
                  >
                    <span>{st.actionText}</span>
                    <ArrowRight className="w-3 h-3" />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
