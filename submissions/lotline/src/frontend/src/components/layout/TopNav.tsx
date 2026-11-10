import React, { useState } from 'react';
import { Database, Bell, ShieldCheck, RefreshCw, Menu, X, Activity } from 'lucide-react';

interface TopNavProps {
  dbStatus: 'connected' | 'connecting' | 'disconnected';
  onRefresh?: () => void;
  isRefreshing?: boolean;
  viewMode?: 'overview' | 'execution';
  onToggleView?: (mode: 'overview' | 'execution') => void;
}

export const TopNav: React.FC<TopNavProps> = ({
  dbStatus,
  onRefresh,
  isRefreshing,
  viewMode = 'overview',
  onToggleView,
}) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navLinks = [
    { label: 'Overview', active: true, href: '#overview' },
    { label: 'Incidents', active: false, href: '#active-incident' },
    { label: 'Traceability', active: false, href: '#traceability' },
    { label: 'Inventory', active: false, href: '#product-exposure' },
    { label: 'Shipments', active: false, href: '#shipments' },
    { label: 'Approvals', active: false, href: '#response-queue' },
    { label: 'Audit', active: false, href: '#audit-log' },
  ];

  return (
    <header className="w-full border-b border-white/[0.08] bg-[#0e1117]/92 backdrop-blur-md sticky top-0 z-40 transition-all">
      <div className="max-w-[1720px] mx-auto px-4 sm:px-6 h-16 lg:h-[70px] flex items-center justify-between">
        {/* Left: Brand Identity */}
        <div className="flex items-center space-x-3.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#23cad2] via-[#1a9ca4] to-[#0f5464] p-[1px] shadow-[0_0_20px_rgba(35,202,210,0.3)] flex items-center justify-center">
            <div className="w-full h-full bg-[#0a1622] rounded-[7px] flex items-center justify-center">
              <div className="w-2.5 h-2.5 rounded-sm bg-[#23cad2] animate-pulse shadow-[0_0_8px_#23cad2]" />
            </div>
          </div>
          <div className="flex items-baseline space-x-2.5">
            <span className="font-mono font-black text-[18px] tracking-tight text-white">LOTLINE</span>
            <span className="text-[11px] font-mono tracking-[0.14em] uppercase text-white/50 pl-2.5 border-l border-white/10 hidden sm:inline">
              RECALL INTELLIGENCE
            </span>
          </div>

          {/* VIEW SWITCHER: OVERVIEW vs RECALL EXECUTION CONTROL TOWER */}
          {onToggleView && (
            <div className="hidden md:flex items-center p-1 rounded-xl bg-white/[0.04] border border-white/10 text-xs font-mono">
              <button
                onClick={() => onToggleView('overview')}
                className={`px-3 py-1.5 rounded-lg font-bold transition-all cursor-pointer ${
                  viewMode === 'overview'
                    ? 'bg-[#23cad2] text-[#061826] shadow-[0_0_12px_rgba(35,202,210,0.3)]'
                    : 'text-white/60 hover:text-white hover:bg-white/[0.04]'
                }`}
              >
                OVERVIEW
              </button>
              <button
                onClick={() => onToggleView('execution')}
                className={`px-3 py-1.5 rounded-lg font-bold transition-all cursor-pointer flex items-center gap-1.5 ${
                  viewMode === 'execution'
                    ? 'bg-[#23cad2] text-[#061826] shadow-[0_0_12px_rgba(35,202,210,0.3)]'
                    : 'text-white/60 hover:text-white hover:bg-white/[0.04]'
                }`}
              >
                <span>RECALL CONTROL TOWER</span>
                <span className={`w-1.5 h-1.5 rounded-full ${viewMode === 'execution' ? 'bg-[#061826]' : 'bg-amber-400'} animate-pulse`} />
              </button>
            </div>
          )}
        </div>

        {/* Center: Desktop Navigation Links (Visible on desktop: 1280px+) */}
        <nav className="hidden xl:flex items-center space-x-1.5" aria-label="Main Navigation">
          {navLinks.map((item) => (
            <a
              key={item.label}
              href={item.href}
              className={`px-3.5 py-1.5 text-[13.5px] font-medium rounded-lg transition-all duration-150 ${
                item.active
                  ? 'text-white bg-white/[0.09] shadow-[inset_0_1px_0_rgba(255,255,255,0.14)] border border-white/10 font-semibold'
                  : 'text-white/60 hover:text-white hover:bg-white/[0.04]'
              }`}
            >
              {item.label}
            </a>
          ))}
        </nav>

        {/* Right: Operational Status, Alerts & Operator Profile */}
        <div className="flex items-center space-x-3 sm:space-x-3.5">
          {/* Refresh / Re-sync Trigger */}
          {onRefresh && (
            <button
              onClick={onRefresh}
              title="Re-synchronize with IBM Db2"
              className="p-2 rounded-lg text-white/60 hover:text-white hover:bg-white/[0.06] transition-all cursor-pointer active:scale-95"
              aria-label="Refresh Database Connection"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-[#23cad2]' : ''}`} />
            </button>
          )}

          {/* Db2 Connection Status Indicator */}
          <div className="flex items-center space-x-2 px-3 py-1.5 rounded-full bg-white/[0.04] border border-white/10">
            <span className="relative flex h-2 w-2">
              <span
                className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                  dbStatus === 'connected' ? 'bg-[#23cad2]' : 'bg-amber-400'
                }`}
              />
              <span
                className={`relative inline-flex rounded-full h-2 w-2 ${
                  dbStatus === 'connected' ? 'bg-[#23cad2]' : 'bg-amber-500'
                }`}
              />
            </span>
            <span className="font-mono text-[11px] uppercase font-bold tracking-wider text-white/90 flex items-center gap-1.5">
              <Database className="w-3 h-3 text-[#23cad2]" />
              <span className="hidden md:inline text-white/60">DB2 LOCAL /</span>
              <span>{dbStatus === 'connected' ? 'CONNECTED' : 'STANDBY'}</span>
            </span>
          </div>

          {/* Notification Indicator */}
          <button
            title="System Notifications (1 active incident)"
            className="relative p-2 rounded-lg text-white/60 hover:text-white hover:bg-white/[0.06] transition-all cursor-pointer"
            aria-label="Notifications"
          >
            <Bell className="w-4 h-4" />
            <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-[#23cad2] ring-2 ring-[#0e1117]" />
          </button>

          {/* Vertical Separator */}
          <div className="hidden sm:block w-[1px] h-6 bg-white/10" aria-hidden="true" />

          {/* Operator Profile Identity */}
          <div className="hidden sm:flex items-center space-x-2.5">
            <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-[#171717] to-[#23cad2]/25 border border-white/15 flex items-center justify-center text-xs font-semibold text-white">
              <ShieldCheck className="w-3.5 h-3.5 text-[#23cad2]" />
            </div>
            <div className="flex flex-col text-left">
              <span className="text-[12px] font-semibold text-white leading-tight">Sec-Ops Lead</span>
              <span className="text-[10px] text-white/40 leading-tight font-mono">LOTLINE_APP</span>
            </div>
          </div>

          {/* Mobile & Tablet Hamburger Menu Toggle (< 1280px) */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="xl:hidden p-2 rounded-lg bg-white/[0.05] hover:bg-white/[0.09] border border-white/10 text-white cursor-pointer active:scale-95"
            aria-label="Toggle Navigation Menu"
          >
            {mobileMenuOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Mobile & Tablet Drawer Menu (< 1280px) */}
      {mobileMenuOpen && (
        <div className="xl:hidden border-t border-white/10 bg-[#0e1117]/98 backdrop-blur-2xl px-4 py-4 space-y-3 animate-in slide-in-from-top-2 duration-150 shadow-2xl">
          {/* Mobile View Switcher */}
          {onToggleView && (
            <div className="grid grid-cols-2 gap-2 p-1 rounded-xl bg-white/[0.04] border border-white/10 text-xs font-mono">
              <button
                onClick={() => {
                  onToggleView('overview');
                  setMobileMenuOpen(false);
                }}
                className={`py-2 px-3 rounded-lg font-bold text-center transition-all ${
                  viewMode === 'overview'
                    ? 'bg-[#23cad2] text-[#061826]'
                    : 'text-white/70 hover:text-white'
                }`}
              >
                OVERVIEW
              </button>
              <button
                onClick={() => {
                  onToggleView('execution');
                  setMobileMenuOpen(false);
                }}
                className={`py-2 px-3 rounded-lg font-bold text-center transition-all flex items-center justify-center gap-1.5 ${
                  viewMode === 'execution'
                    ? 'bg-[#23cad2] text-[#061826]'
                    : 'text-white/70 hover:text-white'
                }`}
              >
                <span>CONTROL TOWER</span>
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
              </button>
            </div>
          )}

          <div className="grid grid-cols-2 gap-2">
            {navLinks.map((item) => (
              <a
                key={item.label}
                href={item.href}
                onClick={() => setMobileMenuOpen(false)}
                className={`px-3.5 py-2.5 text-xs font-medium rounded-lg text-center transition-colors ${
                  item.active
                    ? 'text-white bg-[#23cad2]/15 border border-[#23cad2]/40 font-bold'
                    : 'text-white/70 hover:text-white bg-white/[0.04]'
                }`}
              >
                {item.label}
              </a>
            ))}
          </div>

          <div className="pt-3 border-t border-white/10 flex items-center justify-between text-xs text-white/50 font-mono">
            <div className="flex items-center gap-1.5">
              <Activity className="w-3.5 h-3.5 text-[#23cad2]" />
              <span>OPERATOR: Sec-Ops Lead</span>
            </div>
            <span className="text-[#23cad2]">SCHEMA: LOTLINE_APP</span>
          </div>
        </div>
      )}
    </header>
  );
};
