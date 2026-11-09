import React, { useState } from 'react';
import { 
  BarChart3, 
  Receipt, 
  Bot, 
  Search,
  AlertTriangle,
  UploadCloud,
  LogOut, 
  Sun, 
  Moon, 
  Menu, 
  X, 
  Loader2,
  TrendingUp,
  User as UserIcon,
  ShieldCheck,
  LineChart,
  RefreshCw
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useTheme } from '../../context/ThemeContext';

export interface DashboardNavProps {
  currentTab: 'dashboard' | 'transactions' | 'insights' | 'assistant' | 'search' | 'anomalies' | 'import';
  onTabChange: (tab: 'dashboard' | 'transactions' | 'insights' | 'assistant' | 'search' | 'anomalies' | 'import') => void;
  onLogout: () => Promise<void>;
  isLoggingOut: boolean;
  onRefresh?: () => void;
  isLoading?: boolean;
  lastRefreshed?: string;
}

export const DashboardNav: React.FC<DashboardNavProps> = ({
  currentTab,
  onTabChange,
  onLogout,
  isLoggingOut,
  onRefresh,
  isLoading = false,
  lastRefreshed,
}) => {
  const { user } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navItems = [
    {
      id: 'dashboard' as const,
      label: 'Command Center',
      icon: BarChart3,
      badge: null,
    },
    {
      id: 'transactions' as const,
      label: 'Transactions Ledger',
      icon: Receipt,
      badge: null,
    },
    {
      id: 'insights' as const,
      label: 'Insights & Reports',
      icon: LineChart,
      badge: 'Db2',
      badgeColor: 'gold',
    },
    {
      id: 'assistant' as const,
      label: 'AI Assistant',
      icon: Bot,
      badge: 'Live',
      badgeColor: 'cream',
    },
    {
      id: 'search' as const,
      label: 'Semantic Search',
      icon: Search,
      badge: 'Vector',
      badgeColor: 'sage',
    },
    {
      id: 'anomalies' as const,
      label: 'Anomaly Intel',
      icon: AlertTriangle,
      badge: 'Alerts',
      badgeColor: 'gold',
    },
    {
      id: 'import' as const,
      label: 'Import CSV',
      icon: UploadCloud,
      badge: 'Db2',
      badgeColor: 'cream',
    },
  ];

  const currentTabLabel = navItems.find((item) => item.id === currentTab)?.label || 'Command Center';

  return (
    <>
      {/* =========================================================================
          DESKTOP SIDEBAR — FOREST GREEN (#15370D) WITH MUTED GOLD (#E5CD82) ACCENTS
          ========================================================================= */}
      <aside
        aria-label="FinSight Navigation Sidebar"
        className="hidden lg:flex fixed inset-y-0 left-0 w-64 flex-col bg-[#15370D] border-r border-[#244c18] text-[#FFF2B4] z-30 shadow-2xl select-none"
      >
        {/* Brand Header */}
        <div className="p-6 border-b border-[#244c18]/80">
          <button
            onClick={() => onTabChange('dashboard')}
            className="flex items-center space-x-3 group focus:outline-hidden text-left w-full"
          >
            <div className="w-10 h-10 rounded-xl bg-[#1c4412] text-[#E5CD82] border border-[#E5CD82]/40 flex items-center justify-center font-bold shadow-md group-hover:scale-105 transition-transform">
              <TrendingUp className="w-5 h-5 text-[#E5CD82]" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center space-x-1.5">
                <span className="text-base font-extrabold tracking-tight text-white group-hover:text-[#FFF2B4] transition-colors">
                  FinSight AI
                </span>
                <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-[#244f19] text-[#E5CD82] border border-[#E5CD82]/30">
                  Db2
                </span>
              </div>
              <div className="text-[10px] font-medium tracking-wider text-[#728E6D] uppercase mt-0.5">
                Financial Command
              </div>
            </div>
          </button>
        </div>

        {/* Navigation Links */}
        <div className="flex-1 px-3 py-6 space-y-1.5 overflow-y-auto">
          <div className="px-3 pb-2 text-[10px] font-bold tracking-widest uppercase text-[#728E6D]">
            Navigation
          </div>

          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentTab === item.id;

            return (
              <button
                key={item.id}
                onClick={() => onTabChange(item.id)}
                className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all group ${
                  isActive
                    ? 'bg-[#1e4614] text-[#FFF2B4] shadow-sm border-l-4 border-[#E5CD82]'
                    : 'text-[#9cb598] hover:text-white hover:bg-[#1a3d13]/80'
                }`}
              >
                <div className="flex items-center space-x-3">
                  <Icon
                    className={`w-4 h-4 transition-colors ${
                      isActive ? 'text-[#E5CD82]' : 'text-[#728E6D] group-hover:text-[#E5CD82]'
                    }`}
                  />
                  <span>{item.label}</span>
                </div>

                {item.badge && (
                  <span
                    className={`text-[9px] uppercase tracking-wider font-bold px-1.5 py-0.5 rounded ${
                      item.badgeColor === 'gold'
                        ? 'bg-[#E5CD82]/20 text-[#E5CD82] border border-[#E5CD82]/40'
                        : item.badgeColor === 'cream'
                        ? 'bg-[#FFF2B4] text-[#15370D] font-extrabold'
                        : 'bg-[#728E6D]/30 text-[#FFF2B4] border border-[#728E6D]/50'
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* User Card & Bottom Controls */}
        <div className="p-4 border-t border-[#244c18]/80 bg-[#122e0b]/60 space-y-3">
          {/* User Profile Pill */}
          <div className="flex items-center space-x-3 p-2.5 rounded-xl bg-[#1a3d13] border border-[#2b581e]">
            <div className="w-8 h-8 rounded-lg bg-[#244f19] border border-[#E5CD82]/30 flex items-center justify-center text-[#E5CD82] font-bold text-xs shrink-0">
              {user?.full_name ? user.full_name.charAt(0).toUpperCase() : <UserIcon className="w-4 h-4" />}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-bold text-white truncate">
                {user?.full_name || 'FinSight User'}
              </div>
              <div className="text-[10px] text-[#728E6D] truncate">
                {user?.email || 'Authenticated User'}
              </div>
            </div>
            <span title="Authenticated via IBM Db2 Session">
              <ShieldCheck className="w-4 h-4 text-[#E5CD82] shrink-0" />
            </span>
          </div>

          {/* Action Row: Theme Toggle + Sign Out */}
          <div className="flex items-center space-x-2">
            <button
              onClick={toggleTheme}
              aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
              className="flex-1 flex items-center justify-center space-x-1.5 py-2 px-3 rounded-lg bg-[#1a3d13] hover:bg-[#224b17] border border-[#2b581e] text-xs font-medium text-[#FFF2B4] transition-colors"
            >
              {theme === 'dark' ? (
                <>
                  <Sun className="w-3.5 h-3.5 text-[#E5CD82]" />
                  <span className="text-[11px]">Light</span>
                </>
              ) : (
                <>
                  <Moon className="w-3.5 h-3.5 text-[#E5CD82]" />
                  <span className="text-[11px]">Dark</span>
                </>
              )}
            </button>

            <button
              onClick={onLogout}
              disabled={isLoggingOut}
              className="flex-1 flex items-center justify-center space-x-1.5 py-2 px-3 rounded-lg bg-[#2a1b18]/60 hover:bg-[#3d1f1a] border border-[#5a2c27]/60 text-xs font-semibold text-[#f8b4ab] hover:text-white transition-colors disabled:opacity-50"
            >
              {isLoggingOut ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span className="text-[11px]">Signing Out...</span>
                </>
              ) : (
                <>
                  <LogOut className="w-3.5 h-3.5" />
                  <span className="text-[11px]">Sign Out</span>
                </>
              )}
            </button>
          </div>
        </div>
      </aside>

      {/* =========================================================================
          TOP HEADER BAR — INTEGRATED BREADCRUMB, LIVE STATUS & ACTIONS
          ========================================================================= */}
      <header className="lg:pl-64 sticky top-0 z-20 w-full border-b border-[#E6E2D8] dark:border-[#1c3619] bg-[#FAF8F3]/90 dark:bg-[#0b160a]/90 backdrop-blur-md transition-colors">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Left: Mobile Toggle & Page Title */}
            <div className="flex items-center space-x-3">
              <button
                onClick={() => setMobileMenuOpen(true)}
                aria-label="Open mobile navigation"
                className="lg:hidden p-2 rounded-lg text-[#15370D] dark:text-[#FFF2B4] hover:bg-[#E6E2D8]/60 dark:hover:bg-[#1a3d13] transition-colors"
              >
                <Menu className="w-5 h-5" />
              </button>

              <div className="flex items-center space-x-2">
                <div className="text-sm sm:text-base font-extrabold tracking-tight text-[#152912] dark:text-[#F5F7F2]">
                  {currentTabLabel}
                </div>
                <span className="hidden sm:inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#FFF2B4] dark:bg-[#1c3e16] text-[#15370D] dark:text-[#E5CD82] border border-[#E5CD82]/60">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#15370D] dark:bg-[#E5CD82] animate-pulse mr-0.5"></span>
                  IBM Db2 12.1 Verified
                </span>
              </div>
            </div>

            {/* Right: Telemetry, Theme Toggle & Refresh */}
            <div className="flex items-center space-x-3">
              {lastRefreshed && (
                <span className="text-[11px] font-mono text-[#5C6C58] dark:text-[#95A890] hidden md:inline">
                  Updated {lastRefreshed}
                </span>
              )}

              {onRefresh && (
                <button
                  onClick={onRefresh}
                  disabled={isLoading}
                  className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-xl border border-[#D8D2C4] dark:border-[#244220] bg-white dark:bg-[#10210e] hover:bg-[#FAF8F3] dark:hover:bg-[#172e14] text-xs font-semibold text-[#15370D] dark:text-[#E5CD82] shadow-2xs transition-colors disabled:opacity-50"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-[#728E6D]' : 'text-[#728E6D] dark:text-[#E5CD82]'}`} />
                  <span className="hidden sm:inline">Refresh</span>
                </button>
              )}

              {/* Theme Toggle (Visible on all viewports) */}
              <button
                onClick={toggleTheme}
                aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
                className="p-2 rounded-xl border border-[#D8D2C4] dark:border-[#244220] bg-white dark:bg-[#10210e] text-[#15370D] dark:text-[#FFF2B4] hover:bg-[#FAF8F3] dark:hover:bg-[#172e14] transition-colors shadow-2xs"
              >
                {theme === 'dark' ? <Sun className="w-4 h-4 text-[#E5CD82]" /> : <Moon className="w-4 h-4 text-[#15370D]" />}
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* =========================================================================
          MOBILE SLIDE-OVER DRAWER — COMPLETE FOREST GREEN SIDEBAR OVERLAY
          ========================================================================= */}
      {mobileMenuOpen && (
        <div className="lg:hidden fixed inset-0 z-50 flex">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-xs transition-opacity"
            onClick={() => setMobileMenuOpen(false)}
          />

          {/* Off-canvas panel */}
          <div className="relative w-4/5 max-w-xs bg-[#15370D] text-[#FFF2B4] flex flex-col justify-between p-5 shadow-2xl z-10 border-r border-[#244c18]">
            <div className="space-y-6">
              {/* Drawer Top */}
              <div className="flex items-center justify-between border-b border-[#244c18] pb-4">
                <div className="flex items-center space-x-2.5">
                  <div className="w-9 h-9 rounded-xl bg-[#1c4412] text-[#E5CD82] border border-[#E5CD82]/40 flex items-center justify-center font-bold">
                    <TrendingUp className="w-4 h-4 text-[#E5CD82]" />
                  </div>
                  <div>
                    <span className="text-sm font-extrabold text-white">FinSight AI</span>
                    <div className="text-[10px] text-[#728E6D] uppercase">IBM Db2 Command</div>
                  </div>
                </div>

                <button
                  onClick={() => setMobileMenuOpen(false)}
                  className="p-1.5 rounded-lg text-[#9cb598] hover:text-white hover:bg-[#1a3d13]"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Drawer Navigation Links */}
              <nav className="space-y-1">
                {navItems.map((item) => {
                  const Icon = item.icon;
                  const isActive = currentTab === item.id;

                  return (
                    <button
                      key={item.id}
                      onClick={() => {
                        onTabChange(item.id);
                        setMobileMenuOpen(false);
                      }}
                      className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all ${
                        isActive
                          ? 'bg-[#1e4614] text-[#FFF2B4] border-l-4 border-[#E5CD82]'
                          : 'text-[#9cb598] hover:text-white hover:bg-[#1a3d13]'
                      }`}
                    >
                      <div className="flex items-center space-x-3">
                        <Icon className={`w-4 h-4 ${isActive ? 'text-[#E5CD82]' : 'text-[#728E6D]'}`} />
                        <span>{item.label}</span>
                      </div>

                      {item.badge && (
                        <span
                          className={`text-[9px] uppercase font-bold px-1.5 py-0.5 rounded ${
                            item.badgeColor === 'gold'
                              ? 'bg-[#E5CD82]/20 text-[#E5CD82]'
                              : 'bg-[#FFF2B4] text-[#15370D] font-extrabold'
                          }`}
                        >
                          {item.badge}
                        </span>
                      )}
                    </button>
                  );
                })}
              </nav>
            </div>

            {/* Drawer User & Logout */}
            <div className="pt-4 border-t border-[#244c18] space-y-3">
              <div className="flex items-center space-x-2.5 p-2 rounded-xl bg-[#1a3d13]">
                <div className="w-8 h-8 rounded-lg bg-[#244f19] text-[#E5CD82] flex items-center justify-center font-bold text-xs">
                  {user?.full_name ? user.full_name.charAt(0).toUpperCase() : <UserIcon className="w-3.5 h-3.5" />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-bold text-white truncate">{user?.full_name}</div>
                  <div className="text-[10px] text-[#728E6D] truncate">{user?.email}</div>
                </div>
              </div>

              <button
                onClick={() => {
                  setMobileMenuOpen(false);
                  onLogout();
                }}
                disabled={isLoggingOut}
                className="w-full flex items-center justify-center space-x-2 py-2 px-3 rounded-lg bg-[#2a1b18] text-[#f8b4ab] text-xs font-semibold border border-[#5a2c27]/60"
              >
                <LogOut className="w-3.5 h-3.5" />
                <span>{isLoggingOut ? 'Signing Out...' : 'Sign Out'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
