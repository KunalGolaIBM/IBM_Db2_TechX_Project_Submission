import React, { useState, useEffect } from 'react';
import {
  Building2,
  Bell,
  Shield,
  UserCheck,
  LogOut,
  LogIn,
  ChevronDown,
  Layers,
  Sparkles,
  CheckCircle2,
  ExternalLink,
  RefreshCw
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { UserRole, NotificationItem } from '../types';
import { fetchUserNotifications, markNotificationAsRead } from '../services/complaintService';

interface NavbarProps {
  onOpenNotifications: () => void;
  onSelectComplaint?: (complaintId: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({ onOpenNotifications, onSelectComplaint }) => {
  const {
    currentUser,
    userProfile,
    activeRole,
    activeDepartment,
    setActiveRole,
    setActiveDepartment,
    loginWithGoogle,
    loginAsDemoPersona,
    logout
  } = useAuth();

  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [showRoleMenu, setShowRoleMenu] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [showNotifPreview, setShowNotifPreview] = useState(false);
  const [loadingNotifs, setLoadingNotifs] = useState(false);

  const loadNotifs = async () => {
    if (!userProfile?.uid) return;
    try {
      setLoadingNotifs(true);
      const items = await fetchUserNotifications(userProfile.uid);
      setNotifications(items || []);
    } catch (err) {
      console.warn('Could not load notifications:', err);
    } finally {
      setLoadingNotifs(false);
    }
  };

  useEffect(() => {
    loadNotifs();
    const interval = setInterval(loadNotifs, 15000);
    return () => clearInterval(interval);
  }, [userProfile?.uid]);

  const unreadCount = notifications.filter(n => !n.read).length;

  const handleRoleChange = async (role: UserRole, dept = 'Public Works Department') => {
    setActiveRole(role);
    if (role === 'staff') {
      setActiveDepartment(dept);
    }
    // Also update demo persona profile if using demo or guest mode
    if (!currentUser) {
      await loginAsDemoPersona(role, dept);
    }
    setShowRoleMenu(false);
  };

  return (
    <header className="sticky top-0 z-40 bg-slate-900 border-b border-slate-800 text-white shadow-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Civic Branding */}
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-teal-600/90 text-white shadow-inner">
              <Building2 className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-lg tracking-tight text-white">CivicConnect</span>
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-teal-500/20 text-teal-300 border border-teal-500/30">
                  GovTech 2026
                </span>
              </div>
              <p className="text-xs text-slate-400 hidden sm:block">Smart Civic Grievance Redressal System</p>
            </div>
          </div>

          {/* Center: Interactive Role Switcher / Demo Explorer */}
          <div className="relative">
            <div className="flex items-center bg-slate-800/90 rounded-xl p-1 border border-slate-700">
              <button
                type="button"
                onClick={() => setShowRoleMenu(!showRoleMenu)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium hover:bg-slate-700/80 transition-colors"
                title="Switch active role view for demo evaluation"
              >
                <Layers className="w-4 h-4 text-teal-400" />
                <span className="text-slate-300">Active View:</span>
                <span className="font-semibold text-white capitalize bg-teal-600/30 text-teal-300 px-2 py-0.5 rounded border border-teal-500/40">
                  {activeRole === 'staff' ? `Staff (${activeDepartment.split(' ')[0]})` : activeRole}
                </span>
                <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
              </button>
            </div>

            {showRoleMenu && (
              <div className="absolute top-full mt-2 w-72 left-1/2 -translate-x-1/2 bg-slate-800 border border-slate-700 rounded-xl shadow-2xl py-2 z-50 text-slate-200">
                <div className="px-3 py-2 border-b border-slate-700">
                  <p className="text-xs font-semibold text-teal-400 uppercase tracking-wider">Test Role Switcher</p>
                  <p className="text-xs text-slate-400">Evaluate all 3 perspectives of the complaint lifecycle</p>
                </div>
                <div className="p-1 space-y-1">
                  <button
                    type="button"
                    onClick={() => handleRoleChange('citizen')}
                    className={`w-full flex items-center justify-between px-3 py-2 text-xs sm:text-sm rounded-lg text-left transition ${
                      activeRole === 'citizen' ? 'bg-teal-600/20 text-teal-300 font-semibold' : 'hover:bg-slate-700/60'
                    }`}
                  >
                    <div>
                      <div className="font-medium text-white">1. Citizen View</div>
                      <div className="text-xs text-slate-400">Report problems, track status, give feedback</div>
                    </div>
                    {activeRole === 'citizen' && <CheckCircle2 className="w-4 h-4 text-teal-400" />}
                  </button>

                  <button
                    type="button"
                    onClick={() => handleRoleChange('admin')}
                    className={`w-full flex items-center justify-between px-3 py-2 text-xs sm:text-sm rounded-lg text-left transition ${
                      activeRole === 'admin' ? 'bg-teal-600/20 text-teal-300 font-semibold' : 'hover:bg-slate-700/60'
                    }`}
                  >
                    <div>
                      <div className="font-medium text-white">2. Administrator View</div>
                      <div className="text-xs text-slate-400">Assign complaints, analytics & departments</div>
                    </div>
                    {activeRole === 'admin' && <CheckCircle2 className="w-4 h-4 text-teal-400" />}
                  </button>

                  <button
                    type="button"
                    onClick={() => handleRoleChange('staff', 'Public Works Department')}
                    className={`w-full flex items-center justify-between px-3 py-2 text-xs sm:text-sm rounded-lg text-left transition ${
                      activeRole === 'staff' ? 'bg-teal-600/20 text-teal-300 font-semibold' : 'hover:bg-slate-700/60'
                    }`}
                  >
                    <div>
                      <div className="font-medium text-white">3. Department Staff View</div>
                      <div className="text-xs text-slate-400">Public Works Dept (In Progress & Resolve)</div>
                    </div>
                    {activeRole === 'staff' && <CheckCircle2 className="w-4 h-4 text-teal-400" />}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Right Header: Notifications & User Auth */}
          <div className="flex items-center gap-3">
            {/* Notifications Bell */}
            <div className="relative">
              <button
                type="button"
                onClick={() => {
                  setShowNotifPreview(!showNotifPreview);
                  if (unreadCount > 0) {
                    loadNotifs();
                  }
                }}
                className="relative p-2 rounded-xl text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
                title="Notifications"
              >
                <Bell className="w-5 h-5" />
                {unreadCount > 0 && (
                  <span className="absolute top-1 right-1 flex h-4 w-4 items-center justify-center rounded-full bg-teal-500 text-[10px] font-bold text-slate-950">
                    {unreadCount > 9 ? '9+' : unreadCount}
                  </span>
                )}
              </button>

              {/* Notification Dropdown preview */}
              {showNotifPreview && (
                <div className="absolute right-0 mt-2 w-80 sm:w-96 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-2xl py-2 z-50 text-slate-800 dark:text-slate-200">
                  <div className="flex items-center justify-between px-4 py-2 border-b border-slate-100 dark:border-slate-800">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-sm">Notifications</span>
                      {unreadCount > 0 && (
                        <span className="text-xs bg-teal-100 text-teal-800 dark:bg-teal-900/40 dark:text-teal-300 px-2 py-0.5 rounded-full font-medium">
                          {unreadCount} unread
                        </span>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setShowNotifPreview(false);
                        onOpenNotifications();
                      }}
                      className="text-xs text-teal-600 dark:text-teal-400 hover:underline font-medium"
                    >
                      View All
                    </button>
                  </div>

                  <div className="max-h-72 overflow-y-auto divide-y divide-slate-100 dark:divide-slate-800">
                    {notifications.length === 0 ? (
                      <div className="p-4 text-center text-xs text-slate-400">No notifications yet.</div>
                    ) : (
                      notifications.slice(0, 5).map(n => (
                        <div
                          key={n.id}
                          onClick={() => {
                            if (!n.read) markNotificationAsRead(n.id);
                            if (n.complaintId && onSelectComplaint) {
                              onSelectComplaint(n.complaintId);
                              setShowNotifPreview(false);
                            }
                          }}
                          className={`p-3 text-left hover:bg-slate-50 dark:hover:bg-slate-800/60 cursor-pointer transition ${
                            !n.read ? 'bg-teal-50/50 dark:bg-teal-950/20' : ''
                          }`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-medium text-xs text-slate-900 dark:text-white line-clamp-1">{n.title}</span>
                            <span className="text-[10px] text-slate-400">
                              {new Date(n.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </span>
                          </div>
                          <p className="text-xs text-slate-600 dark:text-slate-300 mt-1 line-clamp-2">{n.message}</p>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* User Account / Profile */}
            <div className="relative">
              {currentUser || userProfile ? (
                <div>
                  <button
                    type="button"
                    onClick={() => setShowUserMenu(!showUserMenu)}
                    className="flex items-center gap-2 pl-2 pr-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700/80 border border-slate-700 text-xs sm:text-sm font-medium transition"
                  >
                    <div className="w-7 h-7 rounded-lg bg-teal-600 flex items-center justify-center text-white font-bold text-xs">
                      {userProfile?.name?.charAt(0) || 'U'}
                    </div>
                    <span className="hidden md:inline max-w-[120px] truncate text-slate-200">
                      {userProfile?.name || 'Logged In'}
                    </span>
                    <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
                  </button>

                  {showUserMenu && (
                    <div className="absolute right-0 mt-2 w-64 bg-slate-800 border border-slate-700 rounded-xl shadow-2xl py-2 z-50 text-slate-200">
                      <div className="px-4 py-2 border-b border-slate-700">
                        <p className="text-xs font-medium text-slate-400">Signed in as</p>
                        <p className="text-sm font-semibold text-white truncate">{userProfile?.name}</p>
                        <p className="text-xs text-slate-400 truncate">{userProfile?.email}</p>
                        <span className="mt-1.5 inline-block text-[11px] font-semibold text-teal-300 bg-teal-900/40 px-2 py-0.5 rounded border border-teal-500/30 uppercase">
                          Role: {userProfile?.role}
                        </span>
                      </div>
                      <div className="p-1">
                        <button
                          type="button"
                          onClick={() => {
                            setShowUserMenu(false);
                            logout();
                          }}
                          className="w-full flex items-center gap-2 px-3 py-2 text-xs sm:text-sm text-red-400 hover:bg-slate-700/60 rounded-lg transition"
                        >
                          <LogOut className="w-4 h-4" />
                          Sign Out
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={loginWithGoogle}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-xs sm:text-sm font-medium shadow-sm transition"
                  >
                    <LogIn className="w-4 h-4" />
                    <span>Google Sign-In</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
