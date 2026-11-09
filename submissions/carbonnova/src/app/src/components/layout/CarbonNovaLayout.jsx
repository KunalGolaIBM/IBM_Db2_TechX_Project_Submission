import React, { useState } from 'react';
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';
import CarbonNovaLogo from '../common/CarbonNovaLogo';
import AiAssistantDrawer from '../common/AiAssistantDrawer';
import {
  Home,
  Globe2,
  TrendingUp,
  Radar,
  Layers,
  Award,
  FileText,
  Settings,
  Search,
  Bell,
  Sparkles,
  ChevronDown,
  Menu,
  X,
  Calendar,
  LogOut,
  User,
  ShieldCheck,
  Leaf
} from 'lucide-react';

const navItems = [
  { path: '/', label: 'Home', icon: Home, exact: true },
  { path: '/land-analysis', label: 'Land Analysis', icon: Globe2 },
  { path: '/carbon-estimates', label: 'Carbon Estimates', icon: TrendingUp },
  { path: '/monitoring', label: 'Monitoring', icon: Radar },
  { path: '/projects', label: 'Carbon Projects', icon: Layers },
  { path: '/carbon-credits', label: 'Carbon Credits', icon: Award },
  { path: '/reports', label: 'Reports', icon: FileText },
  { path: '/settings', label: 'Settings', icon: Settings },
];

export const CarbonNovaLayout = () => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);
  const [aiDrawerOpen, setAiDrawerOpen] = useState(false);
  const [dateRange, setDateRange] = useState('Last 12 Months');
  const [searchQuery, setSearchQuery] = useState('');
  const [sidebarVisible, setSidebarVisible] = useState(false);

  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();

  const isHome = location.pathname === '/' || location.pathname === '/home';
  const [prevPath, setPrevPath] = useState(location.pathname);

  // Restore initial landing state (hidden sidebar) when returning to the landing homepage
  if (location.pathname !== prevPath) {
    setPrevPath(location.pathname);
    if (isHome) {
      setSidebarVisible(false);
    }
  }

  const isSidebarActive = !isHome || sidebarVisible;

  const revealSidebar = () => {
    setSidebarVisible(true);
    if (window.innerWidth < 1024) {
      setMobileOpen(true);
    }
  };

  const getPageMeta = () => {
    const p = location.pathname;
    if (p === '/' || p === '/home') {
      return {
        title: 'Home',
        subtitle: "Overview of your registered land, carbon stock and climate projects.",
        showDateRange: false,
      };
    }
    if (p.startsWith('/land-analysis')) {
      return {
        title: 'Land Analysis',
        subtitle: "Explore your land's carbon potential with AI-powered insights.",
        showDateRange: false,
      };
    }
    if (p.startsWith('/carbon-estimates')) {
      return {
        title: 'Carbon Estimates',
        subtitle: "AI-driven analysis of your land's carbon storage potential.",
        showDateRange: true,
      };
    }
    if (p.startsWith('/monitoring')) {
      return {
        title: 'Monitoring',
        subtitle: 'Track changes in your land and carbon over time.',
        showDateRange: true,
      };
    }
    if (p.startsWith('/projects')) {
      return {
        title: 'Carbon Projects',
        subtitle: 'Develop and manage land-based carbon reduction & removal initiatives.',
        showDateRange: false,
      };
    }
    if (p.startsWith('/carbon-credits')) {
      return {
        title: 'Carbon Credits & dMRV',
        subtitle: 'Digital Measurement, Reporting & Verification (dMRV) readiness and registry tracking.',
        showDateRange: false,
      };
    }
    if (p.startsWith('/reports')) {
      return {
        title: 'Reports & Audits',
        subtitle: 'Exportable land summaries, carbon accounting data, and verification records.',
        showDateRange: true,
      };
    }
    if (p.startsWith('/settings')) {
      return {
        title: 'Settings',
        subtitle: 'System configuration, units, API connectivity and organization profiles.',
        showDateRange: false,
      };
    }
    return {
      title: 'CarbonNova',
      subtitle: 'AI-Powered Carbon Intelligence Platform',
      showDateRange: false,
    };
  };

  const pageMeta = getPageMeta();

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    navigate(`/land-analysis?q=${encodeURIComponent(searchQuery.trim())}`);
  };

  return (
    <div className="flex h-screen overflow-hidden bg-[#F4F6F4] text-[#142A20]">
      {/* Mobile Drawer Backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-xs lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* LEFT SIDEBAR (Deep Forest Green) */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 bg-[#0A291E] border-r border-[#082219] flex flex-col justify-between transition-all duration-300 ease-in-out lg:static shrink-0 ${
          isSidebarActive
            ? 'w-64 translate-x-0 opacity-100'
            : 'w-0 -translate-x-full lg:translate-x-0 opacity-0 overflow-hidden border-none pointer-events-none'
        } ${mobileOpen ? '!w-64 !translate-x-0 !opacity-100 !pointer-events-auto' : ''}`}
      >
        <div className="w-64 flex flex-col flex-1 min-h-0">
          {/* Logo Header */}
          <div className="h-20 flex items-center justify-between px-6 border-b border-[#143B2E]/60">
            <Link to="/" onClick={() => setMobileOpen(false)}>
              <CarbonNovaLogo light={true} size="md" />
            </Link>
            <button
              onClick={() => setMobileOpen(false)}
              className="lg:hidden text-[#92B5A2] hover:text-white p-1 rounded-lg"
            >
              <X size={20} />
            </button>
          </div>

          {/* Navigation Links */}
          <nav className="flex-1 overflow-y-auto px-3 py-6 space-y-1.5 styled-scrollbar">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = item.exact
                ? location.pathname === '/' || location.pathname === '/home'
                : location.pathname.startsWith(item.path);

              return (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setMobileOpen(false)}
                  className={`group flex items-center justify-between px-3.5 py-3 rounded-xl text-sm font-medium transition-all duration-150 ${
                    isActive
                      ? 'bg-[#16513E] text-white shadow-sm font-semibold'
                      : 'text-[#96B3A4] hover:text-white hover:bg-white/5'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <Icon
                      size={19}
                      className={isActive ? 'text-[#34D399]' : 'text-[#85A695] group-hover:text-white transition-colors'}
                    />
                    <span>{item.label}</span>
                  </div>

                  {isActive && (
                    <span className="w-1.5 h-1.5 rounded-full bg-[#34D399] shadow-glow" />
                  )}
                </Link>
              );
            })}
          </nav>
        </div>


      </aside>

      {/* MAIN VIEWPORT */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* TOP HEADER */}
        <header className="h-20 shrink-0 bg-white border-b border-[#E3E9E3] px-5 lg:px-8 flex items-center justify-between z-20 shadow-xs">
          {/* Mobile hamburger + Page Title */}
          <div className="flex items-center gap-3 min-w-0">
            <button
              onClick={() => {
                if (window.innerWidth < 1024) {
                  setMobileOpen(true);
                } else {
                  setSidebarVisible((prev) => !prev);
                }
              }}
              className={`p-2 text-[#2D5A44] hover:bg-[#F2F7F4] rounded-lg transition-colors ${
                !isSidebarActive ? 'block' : 'lg:hidden'
              }`}
              aria-label="Toggle navigation"
            >
              <Menu size={22} />
            </button>

            <div className="min-w-0">
              <h1 className="text-xl lg:text-2xl font-bold text-[#0E2018] tracking-tight truncate">
                {pageMeta.title}
              </h1>
              <p className="text-xs text-[#5D7367] hidden sm:block truncate mt-0.5">
                {pageMeta.subtitle}
              </p>
            </div>
          </div>

          {/* Right Header Controls */}
          <div className="flex items-center gap-3 lg:gap-4 shrink-0">
            {/* Optional Date Selector on analytics pages */}
            {pageMeta.showDateRange && (
              <div className="hidden md:flex items-center gap-1.5 bg-[#F6F8F6] border border-[#D8E2D9] rounded-xl px-3 py-1.5 text-xs text-[#1F3D2E] font-medium">
                <Calendar size={14} className="text-[#557563]" />
                <select
                  value={dateRange}
                  onChange={(e) => setDateRange(e.target.value)}
                  className="bg-transparent border-none outline-none cursor-pointer pr-1"
                >
                  <option value="Last 30 Days">Last 30 Days</option>
                  <option value="Last 90 Days">Last 90 Days</option>
                  <option value="Last 12 Months">Last 12 Months</option>
                  <option value="All Time">All Time</option>
                </select>
              </div>
            )}

            {/* Global Search Bar */}
            <form onSubmit={handleSearchSubmit} className="hidden sm:block relative w-48 lg:w-64">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#7F9A8A]" />
              <input
                type="text"
                placeholder="Search location or farm..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-[#F6F8F6] border border-[#D8E2D9] rounded-full pl-9 pr-3.5 py-1.5 text-xs text-[#142A20] placeholder-[#7F9A8A] focus:bg-white focus:outline-none focus:border-[#10B981] transition-all"
              />
            </form>

            {/* AI Assistant Button */}
            <button
              onClick={() => setAiDrawerOpen(true)}
              className="inline-flex items-center gap-1.5 bg-[#E8F7F0] hover:bg-[#D5F2E3] text-[#0A7B4E] border border-[#BDE6D3] text-xs font-semibold px-3 py-1.5 rounded-full transition-all active:scale-95"
              title="Open AI Carbon Intelligence (NVIDIA Nemotron)"
            >
              <Sparkles size={14} className="text-[#10B981]" />
              <span className="hidden sm:inline">AI Intelligence</span>
            </button>

            {/* Notifications */}
            <button
              className="p-2 text-[#567464] hover:text-[#0C3327] hover:bg-[#F4F7F4] rounded-full relative transition-colors"
              title="Notifications"
            >
              <Bell size={18} />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-emerald-500 rounded-full" />
            </button>

            {/* User Profile */}
            <div className="relative">
              <button
                onClick={() => setUserDropdownOpen(!userDropdownOpen)}
                className="flex items-center gap-2 pl-1 pr-2 py-1 rounded-full hover:bg-[#F2F7F4] border border-transparent hover:border-[#DCE6DE] transition-all"
              >
                <img
                  src={user?.avatar || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=128'}
                  alt={user?.full_name || 'Alex Carter'}
                  className="w-8 h-8 rounded-full object-cover border border-[#B7D1C2]"
                />
                <span className="text-xs font-semibold text-[#142A20] hidden md:inline">
                  {user?.full_name || 'Alex Carter'}
                </span>
                <ChevronDown size={14} className="text-[#728F7F]" />
              </button>

              {/* User Dropdown */}
              {userDropdownOpen && (
                <div
                  className="absolute right-0 mt-2 w-56 bg-white rounded-2xl shadow-xl border border-[#E3E9E3] py-2 z-50 animate-in fade-in duration-100"
                  onClick={() => setUserDropdownOpen(false)}
                >
                  <div className="px-4 py-2 border-b border-[#EDF2EE]">
                    <p className="text-xs font-bold text-[#10271E]">{user?.full_name || 'Alex Carter'}</p>
                    <p className="text-[11px] text-[#698475] truncate">{user?.email || 'alex.carter@carbonnova.earth'}</p>
                    <span className="inline-block mt-1 text-[10px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full">
                      Agricultural Manager
                    </span>
                  </div>

                  <Link
                    to="/settings"
                    className="flex items-center gap-2 px-4 py-2 text-xs text-[#2A4839] hover:bg-[#F6F8F6]"
                  >
                    <Settings size={14} /> Profile & Settings
                  </Link>
                  <Link
                    to="/projects"
                    className="flex items-center gap-2 px-4 py-2 text-xs text-[#2A4839] hover:bg-[#F6F8F6]"
                  >
                    <Layers size={14} /> My Land Portfolios
                  </Link>

                  <div className="border-t border-[#EDF2EE] mt-1 pt-1">
                    <button
                      onClick={() => logout()}
                      className="w-full flex items-center gap-2 px-4 py-2 text-xs text-red-600 hover:bg-red-50 text-left"
                    >
                      <LogOut size={14} /> Sign Out
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* PAGE CONTENT CONTAINER */}
        <main className="flex-1 overflow-x-hidden overflow-y-auto p-4 sm:p-6 lg:p-8 bg-[#F4F6F4]">
          <Outlet context={{ sidebarVisible: isSidebarActive, setSidebarVisible, revealSidebar }} />
        </main>
      </div>

      {/* Persistent AI Assistant Drawer */}
      <AiAssistantDrawer
        isOpen={aiDrawerOpen}
        onClose={() => setAiDrawerOpen(false)}
      />
    </div>
  );
};

export default CarbonNovaLayout;
