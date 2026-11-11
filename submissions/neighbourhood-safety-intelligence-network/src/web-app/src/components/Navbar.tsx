import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { ShieldAlert, Shield, LogOut, Menu, X, Smartphone, Activity, UserCheck } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const Navbar: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/');
    setMobileMenuOpen(false);
  };

  const isActive = (path: string) => location.pathname === path;

  return (
    <header className="sticky top-0 z-50 bg-slate-900/95 backdrop-blur border-b border-slate-800 text-slate-100 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        
        {/* Brand */}
        <Link to="/" className="flex items-center gap-2.5 group">
          <div className="w-10 h-10 rounded-xl bg-teal-600/30 border border-teal-500/40 p-2 flex items-center justify-center group-hover:bg-teal-600/40 transition">
            <Shield className="w-6 h-6 text-teal-400" />
          </div>
          <div>
            <span className="font-bold text-lg tracking-tight text-white flex items-center gap-1.5">
              Neighbourhood Safety
              <span className="text-[10px] font-semibold bg-teal-500/20 text-teal-300 border border-teal-500/30 px-1.5 py-0.5 rounded">
                INTEL
              </span>
            </span>
            <span className="text-[11px] text-slate-400 block -mt-1">Civic Assistance Network</span>
          </div>
        </Link>

        {/* Desktop Nav Links */}
        <nav className="hidden lg:flex items-center gap-1 text-sm font-medium">
          {user ? (
            <>
              {user.role === 'resident' && (
                <>
                  <Link 
                    to="/dashboard" 
                    className={`px-3 py-1.5 rounded-lg transition ${isActive('/dashboard') ? 'bg-slate-800 text-teal-400 font-semibold' : 'text-slate-300 hover:text-white hover:bg-slate-800/60'}`}
                  >
                    Resident Home
                  </Link>
                  <Link 
                    to="/sos" 
                    className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition ${isActive('/sos') ? 'bg-red-950/80 text-red-400 font-semibold' : 'text-red-400 hover:bg-red-950/40'}`}
                  >
                    <ShieldAlert className="w-4 h-4" />
                    SOS Distress
                  </Link>
                  <Link 
                    to="/contacts" 
                    className={`px-3 py-1.5 rounded-lg transition ${isActive('/contacts') ? 'bg-slate-800 text-teal-400' : 'text-slate-300 hover:text-white hover:bg-slate-800/60'}`}
                  >
                    Contacts
                  </Link>
                  <Link 
                    to="/child-safety" 
                    className={`px-3 py-1.5 rounded-lg transition ${isActive('/child-safety') ? 'bg-slate-800 text-teal-400' : 'text-slate-300 hover:text-white hover:bg-slate-800/60'}`}
                  >
                    Child Safe Transit
                  </Link>
                  <Link 
                    to="/elder-care" 
                    className={`px-3 py-1.5 rounded-lg transition ${isActive('/elder-care') ? 'bg-slate-800 text-teal-400' : 'text-slate-300 hover:text-white hover:bg-slate-800/60'}`}
                  >
                    Elder Care
                  </Link>
                </>
              )}

              {user.role === 'responder' && (
                <>
                  <Link 
                    to="/responder" 
                    className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition ${isActive('/responder') ? 'bg-slate-800 text-teal-400 font-semibold' : 'text-slate-300 hover:text-white hover:bg-slate-800/60'}`}
                  >
                    <Activity className="w-4 h-4 text-teal-400" />
                    Responder Command
                  </Link>
                  <Link 
                    to="/community" 
                    className={`px-3 py-1.5 rounded-lg transition ${isActive('/community') ? 'bg-slate-800 text-teal-400' : 'text-slate-300 hover:text-white hover:bg-slate-800/60'}`}
                  >
                    Civic Hazards
                  </Link>
                </>
              )}

              {user.role === 'admin' && (
                <>
                  <Link 
                    to="/admin" 
                    className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition ${isActive('/admin') ? 'bg-slate-800 text-teal-400 font-semibold' : 'text-slate-300 hover:text-white hover:bg-slate-800/60'}`}
                  >
                    <UserCheck className="w-4 h-4 text-teal-400" />
                    Admin Oversight
                  </Link>
                  <Link 
                    to="/community" 
                    className={`px-3 py-1.5 rounded-lg transition ${isActive('/community') ? 'bg-slate-800 text-teal-400' : 'text-slate-300 hover:text-white hover:bg-slate-800/60'}`}
                  >
                    Community Insights
                  </Link>
                </>
              )}

              <Link 
                to="/community" 
                className={`px-3 py-1.5 rounded-lg transition ${isActive('/community') ? 'bg-slate-800 text-teal-400' : 'text-slate-300 hover:text-white hover:bg-slate-800/60'}`}
              >
                Community Map
              </Link>
            </>
          ) : (
            <>
              <a href="#how-it-works" className="px-3 py-1.5 text-slate-300 hover:text-white transition">How It Works</a>
              <a href="#safety-pillars" className="px-3 py-1.5 text-slate-300 hover:text-white transition">Safety Pillars</a>
              <a href="#download-android-app" className="px-3 py-1.5 text-teal-300 hover:text-teal-200 flex items-center gap-1.5 transition">
                <Smartphone className="w-4 h-4" />
                Android App
              </a>
              <a href="#helplines" className="px-3 py-1.5 text-slate-300 hover:text-white transition">Emergency Helplines</a>
            </>
          )}
        </nav>

        {/* User / Auth Actions */}
        <div className="hidden sm:flex items-center gap-3">
          {user ? (
            <div className="flex items-center gap-3">
              <div className="text-right">
                <span className="text-sm font-semibold text-white block leading-tight">{user.full_name}</span>
                <span className="text-[11px] uppercase tracking-wider text-teal-400 font-medium">{user.role}</span>
              </div>
              <button
                onClick={handleLogout}
                className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition border border-slate-700/60"
                title="Sign Out"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Link
                to="/auth?mode=login"
                className="text-sm font-medium text-slate-300 hover:text-white px-3 py-2 rounded-xl hover:bg-slate-800 transition"
              >
                Sign In
              </Link>
              <Link
                to="/auth?mode=register"
                className="text-sm font-semibold bg-teal-500 hover:bg-teal-400 text-slate-950 px-4 py-2 rounded-xl shadow-md transition"
              >
                Join Network
              </Link>
            </div>
          )}
        </div>

        {/* Mobile menu trigger */}
        <div className="flex sm:hidden">
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-2 text-slate-300 hover:text-white rounded-lg hover:bg-slate-800"
          >
            {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>

      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="sm:hidden bg-slate-900 border-b border-slate-800 px-4 pt-3 pb-6 space-y-3">
          {user ? (
            <div className="space-y-2">
              <div className="pb-2 border-b border-slate-800">
                <span className="text-sm font-bold text-white block">{user.full_name}</span>
                <span className="text-xs text-teal-400 uppercase">{user.role}</span>
              </div>
              {user.role === 'resident' && (
                <>
                  <Link to="/dashboard" onClick={() => setMobileMenuOpen(false)} className="block py-2 text-slate-200">Resident Dashboard</Link>
                  <Link to="/sos" onClick={() => setMobileMenuOpen(false)} className="block py-2 text-red-400 font-semibold">🚨 Trigger Emergency SOS</Link>
                  <Link to="/contacts" onClick={() => setMobileMenuOpen(false)} className="block py-2 text-slate-200">Trusted Contacts</Link>
                  <Link to="/child-safety" onClick={() => setMobileMenuOpen(false)} className="block py-2 text-slate-200">Child Safe Transit</Link>
                  <Link to="/elder-care" onClick={() => setMobileMenuOpen(false)} className="block py-2 text-slate-200">Elder Care</Link>
                </>
              )}
              {user.role === 'responder' && (
                <Link to="/responder" onClick={() => setMobileMenuOpen(false)} className="block py-2 text-teal-400 font-semibold">Responder Command Center</Link>
              )}
              {user.role === 'admin' && (
                <Link to="/admin" onClick={() => setMobileMenuOpen(false)} className="block py-2 text-teal-400 font-semibold">Admin Oversight</Link>
              )}
              <Link to="/community" onClick={() => setMobileMenuOpen(false)} className="block py-2 text-slate-200">Community Map & Hazards</Link>
              <button onClick={handleLogout} className="w-full text-left py-2 text-red-400 font-medium">Sign Out</button>
            </div>
          ) : (
            <div className="space-y-3 pt-2">
              <Link to="/auth?mode=login" onClick={() => setMobileMenuOpen(false)} className="block text-center py-2 text-slate-300 bg-slate-800 rounded-xl">Sign In</Link>
              <Link to="/auth?mode=register" onClick={() => setMobileMenuOpen(false)} className="block text-center py-2 bg-teal-500 text-slate-950 font-semibold rounded-xl">Join Network</Link>
            </div>
          )}
        </div>
      )}
    </header>
  );
};
