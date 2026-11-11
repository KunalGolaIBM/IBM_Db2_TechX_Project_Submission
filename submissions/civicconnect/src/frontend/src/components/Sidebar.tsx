import React from 'react';
import {
  LayoutDashboard,
  FilePlus2,
  FolderClock,
  Bell,
  User,
  LogOut,
  Building,
  Tag,
  BarChart3,
  Settings,
  HardHat,
  CheckCircle2,
  ClipboardList
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { UserRole } from '../types';

interface SidebarProps {
  currentTab: string;
  onSelectTab: (tabId: string) => void;
  unreadCount?: number;
}

interface NavItem {
  id: string;
  label: string;
  icon: React.ElementType;
  highlight?: boolean;
  badge?: number;
}

export const Sidebar: React.FC<SidebarProps> = ({ currentTab, onSelectTab, unreadCount = 0 }) => {
  const { activeRole, activeDepartment, userProfile, logout } = useAuth();

  const citizenNav: NavItem[] = [
    { id: 'citizen-overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'citizen-report', label: 'Report a Problem', icon: FilePlus2, highlight: true },
    { id: 'citizen-complaints', label: 'My Complaints', icon: FolderClock },
    { id: 'notifications', label: 'Notifications', icon: Bell, badge: unreadCount },
    { id: 'citizen-profile', label: 'My Profile', icon: User },
  ];

  const adminNav: NavItem[] = [
    { id: 'admin-dashboard', label: 'Admin Dashboard', icon: LayoutDashboard },
    { id: 'admin-complaints', label: 'All Complaints', icon: ClipboardList },
    { id: 'admin-departments', label: 'Departments', icon: Building },
    { id: 'admin-categories', label: 'Categories', icon: Tag },
    { id: 'admin-analytics', label: 'Analytics & SLA', icon: BarChart3 },
    { id: 'notifications', label: 'Notifications', icon: Bell, badge: unreadCount },
    { id: 'admin-settings', label: 'Settings & Audit', icon: Settings },
  ];

  const staffNav: NavItem[] = [
    { id: 'staff-dashboard', label: 'Dept Dashboard', icon: LayoutDashboard },
    { id: 'staff-complaints', label: 'Assigned Complaints', icon: HardHat },
    { id: 'staff-updates', label: 'Work Updates', icon: CheckCircle2 },
    { id: 'notifications', label: 'Notifications', icon: Bell, badge: unreadCount },
  ];

  const navItems = activeRole === 'admin' ? adminNav : activeRole === 'staff' ? staffNav : citizenNav;

  return (
    <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col justify-between shrink-0 min-h-[calc(100vh-4rem)]">
      <div className="p-4 space-y-6">
        {/* Role Identity Card */}
        <div className="p-3 rounded-xl bg-slate-800/80 border border-slate-700/80">
          <div className="flex items-center gap-2.5">
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center font-bold text-xs ${
              activeRole === 'admin'
                ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                : activeRole === 'staff'
                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                : 'bg-teal-500/20 text-teal-400 border border-teal-500/30'
            }`}>
              {activeRole === 'admin' ? 'ADM' : activeRole === 'staff' ? 'STF' : 'CTZ'}
            </div>
            <div className="overflow-hidden">
              <p className="text-xs font-semibold text-white capitalize">{activeRole} Portal</p>
              <p className="text-[11px] text-slate-400 truncate">
                {activeRole === 'staff' ? activeDepartment : userProfile?.name || 'Authorized Session'}
              </p>
            </div>
          </div>
        </div>

        {/* Navigation list */}
        <nav className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentTab === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onSelectTab(item.id)}
                className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs sm:text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-teal-600 text-white shadow-sm shadow-teal-600/30'
                    : item.highlight
                    ? 'bg-teal-500/10 text-teal-300 hover:bg-teal-500/20 border border-teal-500/30'
                    : 'text-slate-300 hover:bg-slate-800/80 hover:text-white'
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon className={`w-4 h-4 ${isActive ? 'text-white' : item.highlight ? 'text-teal-400' : 'text-slate-400'}`} />
                  <span>{item.label}</span>
                </div>
                {item.badge && item.badge > 0 ? (
                  <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${
                    isActive ? 'bg-white text-teal-700' : 'bg-teal-500 text-slate-950'
                  }`}>
                    {item.badge}
                  </span>
                ) : null}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Footer & Logout */}
      <div className="p-4 border-t border-slate-800">
        <button
          type="button"
          onClick={() => logout()}
          className="w-full flex items-center gap-3 px-3 py-2 text-xs font-medium text-slate-400 hover:text-red-400 hover:bg-slate-800/60 rounded-xl transition"
        >
          <LogOut className="w-4 h-4" />
          <span>Sign Out / Switch</span>
        </button>
      </div>
    </aside>
  );
};
