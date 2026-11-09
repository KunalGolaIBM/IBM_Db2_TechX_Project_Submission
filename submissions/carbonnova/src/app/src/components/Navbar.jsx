import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Leaf, Menu, X, ArrowRight } from 'lucide-react';
import { useAuthStore } from '../stores/authStore';

const Navbar = () => {
  const [isScrolled, setIsScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { isAuthenticated, user } = useAuthStore();
  const location = useLocation();

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 10);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const navLinks = [
    { name: 'Marketplace', path: '/marketplace' },
    { name: 'For Sellers', path: '/#sellers' },
    { name: 'For Buyers', path: '/#buyers' },
    { name: 'Technology', path: '/#tech' },
  ];

  const getDashboardLink = () => {
    if (!user) return '/auth/login';
    if (user.role === 'seller') return '/seller/dashboard';
    if (user.role === 'buyer') return '/buyer/dashboard';
    if (user.role === 'admin') return '/admin/dashboard';
    return '/verifier/projects';
  };

  return (
    <nav className={`fixed w-full z-50 transition-all duration-300 ${isScrolled ? 'bg-dark-900/80 backdrop-blur-md border-b border-carbon-800/30 shadow-lg py-3' : 'bg-transparent py-5'}`}>
      <div className="max-w-7xl mx-auto px-6 flex items-center justify-between">
        
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2 group">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-carbon-500 to-emerald-400 flex items-center justify-center shadow-lg shadow-carbon-500/20 group-hover:shadow-carbon-500/40 transition-all">
            <Leaf className="w-5 h-5 text-dark-900" />
          </div>
          <span className="text-xl font-bold tracking-tight text-white group-hover:text-transparent group-hover:bg-clip-text group-hover:bg-gradient-to-r group-hover:from-carbon-400 group-hover:to-white transition-all">
            CarbonChain
          </span>
        </Link>

        {/* Desktop Links */}
        <div className="hidden md:flex items-center gap-8">
          {navLinks.map(link => (
            <Link 
              key={link.name} 
              to={link.path}
              className={`text-sm font-medium transition-colors hover:text-carbon-400 ${location.pathname === link.path ? 'text-carbon-400' : 'text-gray-300'}`}
            >
              {link.name}
            </Link>
          ))}
        </div>

        {/* Actions */}
        <div className="hidden md:flex items-center gap-4">
          {isAuthenticated ? (
            <Link to={getDashboardLink()} className="btn-primary py-2 px-5 flex items-center gap-2 text-sm">
              Dashboard <ArrowRight size={16} />
            </Link>
          ) : (
            <>
              <Link to="/auth/login" className="text-sm font-medium text-gray-300 hover:text-white transition-colors">
                Log in
              </Link>
              <Link to="/auth/signup" className="btn-primary py-2 px-5 text-sm">
                Get Started
              </Link>
            </>
          )}
        </div>

        {/* Mobile menu button */}
        <button 
          className="md:hidden p-2 text-gray-300 hover:text-white"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
        >
          {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>

      {/* Mobile Menu Dropdown */}
      {mobileMenuOpen && (
        <div className="absolute top-full left-0 w-full bg-dark-800 border-b border-carbon-800/40 shadow-xl md:hidden py-4 px-6 flex flex-col gap-4 z-40">
          {navLinks.map(link => (
            <Link 
              key={link.name} 
              to={link.path}
              onClick={() => setMobileMenuOpen(false)}
              className="text-gray-300 hover:text-carbon-400 font-medium py-2 border-b border-dark-700"
            >
              {link.name}
            </Link>
          ))}
          <div className="pt-4 flex flex-col gap-3">
            {isAuthenticated ? (
               <Link to={getDashboardLink()} className="btn-primary text-center py-3">
                 Go to Dashboard
               </Link>
            ) : (
              <>
                <Link to="/auth/login" className="btn-secondary text-center py-3">
                  Log in
                </Link>
                <Link to="/auth/signup" className="btn-primary text-center py-3">
                  Get Started
                </Link>
              </>
            )}
          </div>
        </div>
      )}
    </nav>
  );
};

export default Navbar;
