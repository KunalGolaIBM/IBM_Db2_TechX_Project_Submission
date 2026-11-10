import React, { useState } from 'react';
import { Sun, Moon, Menu, X, ArrowRight, LayoutDashboard, LogOut, User } from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';
import { useAuth } from '../../context/AuthContext';

interface NavbarProps {
  onNavigate: (route: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({ onNavigate }) => {
  const { theme, toggleTheme } = useTheme();
  const { user, isAuthenticated, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleLinkClick = (e: React.MouseEvent<HTMLAnchorElement>, href: string) => {
    e.preventDefault();
    setMobileMenuOpen(false);

    if (href.startsWith('#')) {
      const element = document.querySelector(href);
      if (element) {
        element.scrollIntoView({ behavior: 'smooth' });
      }
    } else {
      onNavigate(href);
    }
  };

  const handleLogout = async () => {
    setMobileMenuOpen(false);
    try {
      await logout();
      onNavigate('/');
    } catch {
      // Handled
    }
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b border-slate-200/80 dark:border-slate-800/80 bg-white/90 dark:bg-slate-950/90 backdrop-blur-md transition-colors">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center space-x-3 cursor-pointer" onClick={() => onNavigate('/')}>
          <div className="w-9 h-9 rounded-lg bg-slate-900 dark:bg-white flex items-center justify-center text-white dark:text-slate-950 font-semibold shadow-sm transition-transform hover:scale-105">
            <span className="text-base tracking-tight font-bold">F</span>
          </div>
          <div className="flex flex-col">
            <div className="flex items-center space-x-1.5">
              <span className="font-semibold text-lg tracking-tight text-slate-900 dark:text-white">FinSight</span>
              <span className="text-xs font-medium px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700">AI</span>
            </div>
          </div>
        </div>

        {/* Desktop Nav */}
        <nav className="hidden md:flex items-center space-x-8 text-sm font-medium text-slate-600 dark:text-slate-300">
          <a
            href="#product"
            onClick={(e) => handleLinkClick(e, '#product')}
            className="hover:text-slate-900 dark:hover:text-white transition-colors"
          >
            Product
          </a>
          <a
            href="#problem"
            onClick={(e) => handleLinkClick(e, '#problem')}
            className="hover:text-slate-900 dark:hover:text-white transition-colors"
          >
            The Problem
          </a>
          <a
            href="#features"
            onClick={(e) => handleLinkClick(e, '#features')}
            className="hover:text-slate-900 dark:hover:text-white transition-colors"
          >
            Features
          </a>
          <a
            href="#how-it-works"
            onClick={(e) => handleLinkClick(e, '#how-it-works')}
            className="hover:text-slate-900 dark:hover:text-white transition-colors"
          >
            How it Works
          </a>
          {isAuthenticated && (
            <button
              onClick={() => onNavigate('/dashboard')}
              className="text-sky-600 dark:text-sky-400 font-semibold hover:underline"
            >
              Dashboard
            </button>
          )}
        </nav>

        {/* Desktop Actions */}
        <div className="hidden md:flex items-center space-x-3">
          <button
            onClick={toggleTheme}
            aria-label="Toggle theme"
            className="p-2 rounded-lg text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800/60 transition-colors"
          >
            {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>

          {isAuthenticated ? (
            <div className="flex items-center space-x-3">
              <div className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 text-xs font-medium text-slate-800 dark:text-slate-200 max-w-[180px] truncate">
                <User className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                <span className="truncate">{user?.full_name || user?.email}</span>
              </div>
              <button
                onClick={() => onNavigate('/dashboard')}
                className="inline-flex items-center space-x-1.5 text-xs font-medium px-3.5 py-2 rounded-lg bg-slate-900 text-white dark:bg-white dark:text-slate-950 hover:bg-slate-800 dark:hover:bg-slate-100 shadow-xs transition-colors"
              >
                <LayoutDashboard className="w-3.5 h-3.5" />
                <span>Dashboard</span>
              </button>
              <button
                onClick={handleLogout}
                title="Sign Out"
                className="p-2 rounded-lg text-slate-500 hover:text-rose-600 dark:text-slate-400 dark:hover:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/30 transition-colors"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <>
              <button
                onClick={() => onNavigate('/login')}
                className="text-sm font-medium text-slate-700 dark:text-slate-200 hover:text-slate-900 dark:hover:text-white px-3.5 py-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800/60 transition-colors"
              >
                Sign In
              </button>

              <button
                onClick={() => onNavigate('/register')}
                className="inline-flex items-center space-x-2 text-sm font-medium px-4 py-2 rounded-lg bg-slate-900 text-white dark:bg-white dark:text-slate-950 hover:bg-slate-800 dark:hover:bg-slate-100 shadow-sm transition-all hover:shadow"
              >
                <span>Get Started</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </>
          )}
        </div>

        {/* Mobile controls */}
        <div className="flex md:hidden items-center space-x-2">
          <button
            onClick={toggleTheme}
            aria-label="Toggle theme"
            className="p-2 rounded-lg text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle mobile menu"
            className="p-2 rounded-lg text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 px-4 pt-3 pb-6 space-y-4">
          <div className="flex flex-col space-y-3 text-base font-medium">
            <a
              href="#product"
              onClick={(e) => handleLinkClick(e, '#product')}
              className="px-3 py-2 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-800 dark:text-slate-200"
            >
              Product
            </a>
            <a
              href="#problem"
              onClick={(e) => handleLinkClick(e, '#problem')}
              className="px-3 py-2 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-800 dark:text-slate-200"
            >
              The Problem
            </a>
            <a
              href="#features"
              onClick={(e) => handleLinkClick(e, '#features')}
              className="px-3 py-2 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-800 dark:text-slate-200"
            >
              Features
            </a>
            <a
              href="#how-it-works"
              onClick={(e) => handleLinkClick(e, '#how-it-works')}
              className="px-3 py-2 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-800 dark:text-slate-200"
            >
              How it Works
            </a>
            {isAuthenticated && (
              <button
                onClick={() => {
                  setMobileMenuOpen(false);
                  onNavigate('/dashboard');
                }}
                className="text-left px-3 py-2 rounded-md text-sky-600 dark:text-sky-400 font-semibold"
              >
                Dashboard
              </button>
            )}
          </div>

          <div className="pt-4 border-t border-slate-200 dark:border-slate-800 flex flex-col space-y-2.5">
            {isAuthenticated ? (
              <button
                onClick={handleLogout}
                className="w-full flex items-center justify-center space-x-2 py-2.5 px-4 rounded-lg border border-rose-300 dark:border-rose-900/60 font-medium text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/20"
              >
                <LogOut className="w-4 h-4" />
                <span>Sign Out</span>
              </button>
            ) : (
              <>
                <button
                  onClick={() => {
                    setMobileMenuOpen(false);
                    onNavigate('/login');
                  }}
                  className="w-full text-center py-2.5 px-4 rounded-lg border border-slate-300 dark:border-slate-700 font-medium text-slate-800 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800"
                >
                  Sign In
                </button>
                <button
                  onClick={() => {
                    setMobileMenuOpen(false);
                    onNavigate('/register');
                  }}
                  className="w-full flex items-center justify-center space-x-2 py-2.5 px-4 rounded-lg bg-slate-900 text-white dark:bg-white dark:text-slate-950 font-medium hover:bg-slate-800 dark:hover:bg-slate-100"
                >
                  <span>Get Started</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </header>
  );
};
