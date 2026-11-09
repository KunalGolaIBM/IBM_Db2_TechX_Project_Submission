import React from 'react';
import { ShieldCheck, User, LogOut, Bell, ExternalLink } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import Db2StatusBadge from './Db2StatusBadge';

export default function Navbar({ dbHealth }) {
  const { user, logout, isAuthenticated } = useAuth();

  return (
    <header className="h-12 bg-[#161616] text-white flex items-center justify-between px-4 z-30 border-b border-[#393939]">
      <div className="flex items-center space-x-3">
        <div className="flex items-center space-x-2">
          <div className="w-7 h-7 bg-[#0F62FE] flex items-center justify-center font-bold text-white text-sm rounded-sm">
            <ShieldCheck className="w-4 h-4" />
          </div>
          <div className="flex flex-col">
            <div className="flex items-center space-x-2">
              <span className="font-semibold text-sm tracking-wide">ClaimGuard AI</span>
              <span className="text-[10px] bg-[#393939] px-1.5 py-0.5 rounded text-gray-300 font-mono">IBM Db2Hack 2026</span>
            </div>
          </div>
        </div>
      </div>

      <div className="flex items-center space-x-4">
        {/* Db2 Connection Status Indicator */}
        <Db2StatusBadge dbHealth={dbHealth} />

        {/* User profile / Login status */}
        {isAuthenticated ? (
          <div className="flex items-center space-x-3 pl-3 border-l border-[#393939]">
            <div className="flex items-center space-x-1.5 text-xs text-gray-300">
              <User className="w-3.5 h-3.5 text-[#0F62FE]" />
              <span className="font-medium text-white">{user?.full_name || user?.username}</span>
              <span className="text-[10px] bg-[#001D6C] text-[#78A9FF] px-1 py-0.2 rounded font-mono">
                {user?.role || 'REVIEWER'}
              </span>
            </div>
            <button
              onClick={logout}
              title="Log out"
              className="text-gray-400 hover:text-white p-1 transition-colors"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          <a
            href="/login"
            className="text-xs bg-[#0F62FE] hover:bg-[#0353E9] text-white px-3 py-1 font-medium transition-colors"
          >
            Examiner Login
          </a>
        )}
      </div>
    </header>
  );
}
