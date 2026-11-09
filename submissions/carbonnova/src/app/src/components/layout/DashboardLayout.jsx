import React, { useState } from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';
import { 
  LayoutDashboard, 
  MapPin, 
  Cpu, 
  Activity, 
  Wallet, 
  Users, 
  Flag,
  FileBadge,
  LogOut,
  Bell,
  Menu,
  X
} from 'lucide-react';
import { useNotificationStore } from '../../stores/notificationStore';

const DashboardLayout = ({ role }) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const { notifications } = useNotificationStore();

  const unreadCount = notifications.filter(n => !n.read).length;

  const roleLinks = {
    seller: [
      { path: '/seller/dashboard', label: 'Dashboard', icon: LayoutDashboard },
      { path: '/seller/projects', label: 'My Projects', icon: MapPin },
      { path: '/seller/devices', label: 'IoT Devices', icon: Cpu },
      { path: '/seller/listings', label: 'Listings', icon: Activity },
      { path: '/seller/earnings', label: 'Earnings', icon: Wallet },
    ],
    buyer: [
      { path: '/buyer/dashboard', label: 'Portfolio', icon: LayoutDashboard },
      { path: '/buyer/certificates', label: 'Certificates', icon: FileBadge },
      { path: '/buyer/watchlist', label: 'Watchlist', icon: Activity },
    ],
    admin: [
      { path: '/admin/dashboard', label: 'Overview', icon: LayoutDashboard },
      { path: '/admin/users', label: 'Users', icon: Users },
      { path: '/admin/devices', label: 'Device Map', icon: Cpu },
      { path: '/admin/flagged', label: 'Flagged Listings', icon: Flag },
      { path: '/admin/verifications', label: 'Verifications', icon: FileBadge },
    ],
    verifier: [
      { path: '/verifier/projects', label: 'Pending Audits', icon: FileBadge },
    ]
  };

  const links = roleLinks[role] || [];

  return (
    <div className="flex h-screen overflow-hidden bg-dark-900">
      {/* Mobile Sidebar Overlay */}
      {mobileMenuOpen && (
        <div 
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`fixed inset-y-0 left-0 z-50 w-64 bg-dark-800 border-r border-carbon-800/40 transform transition-transform duration-300 ease-in-out lg:static lg:translate-x-0 flex flex-col ${mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        
        {/* Logo */}
        <div className="h-16 flex items-center justify-between px-6 border-b border-carbon-800/40">
          <Link to="/" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-carbon-500 to-emerald-400 flex items-center justify-center">
              <span className="text-dark-900 font-bold text-lg">C</span>
            </div>
            <span className="text-xl font-bold tracking-tight">CarbonChain</span>
          </Link>
          <button onClick={() => setMobileMenuOpen(false)} className="lg:hidden text-gray-400 hover:text-white">
            <X size={20} />
          </button>
        </div>

        {/* User Info */}
        <div className="p-4 border-b border-carbon-800/40">
          <div className="flex items-center gap-3">
             <div className="w-10 h-10 rounded-full bg-carbon-800 flex items-center justify-center text-carbon-400 font-bold">
                {user?.full_name.charAt(0).toUpperCase()}
             </div>
             <div>
                <p className="text-sm font-semibold text-gray-100 truncate w-36">{user?.full_name}</p>
                <p className="text-xs text-gray-500 capitalize">{user?.role}</p>
             </div>
          </div>
        </div>

        {/* Nav Links */}
        <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
          <p className="px-3 text-xs font-semibold text-carbon-600 uppercase tracking-wider mb-2">Menu</p>
          {links.map((link) => {
            const Icon = link.icon;
            const isActive = location.pathname.startsWith(link.path);
            return (
              <Link
                key={link.path}
                to={link.path}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 ${
                  isActive 
                    ? 'bg-carbon-900/50 text-carbon-400 border border-carbon-800/50 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]' 
                    : 'text-gray-400 hover:text-gray-100 hover:bg-white/5'
                }`}
                onClick={() => setMobileMenuOpen(false)}
              >
                <Icon size={18} className={isActive ? 'text-carbon-400' : 'text-gray-500'} />
                {link.label}
              </Link>
            )
          })}
        </nav>

        {/* Bottom Actions */}
        <div className="p-4 border-t border-carbon-800/40">
           <button 
             onClick={logout}
             className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-red-400 hover:bg-red-400/10 transition-colors"
           >
             <LogOut size={18} />
             Sign Out
           </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Header */}
        <header className="h-16 flex items-center justify-between px-4 lg:px-8 border-b border-carbon-800/40 bg-dark-800/50 backdrop-blur-md z-10">
          <button 
            onClick={() => setMobileMenuOpen(true)}
            className="lg:hidden p-2 text-gray-400 hover:text-white rounded-lg hover:bg-white/5"
          >
            <Menu size={24} />
          </button>

          <div className="flex items-center gap-4 ml-auto">
            <Link to="/marketplace" className="text-sm font-medium text-gray-400 hover:text-carbon-400 hidden sm:block">
              Go to Marketplace
            </Link>
            
            <div className="relative">
              <button className="p-2 text-gray-400 hover:text-white rounded-full hover:bg-white/5 relative">
                <Bell size={20} />
                {unreadCount > 0 && (
                  <span className="absolute top-1.5 right-1.5 w-2.5 h-2.5 bg-red-500 rounded-full border-2 border-dark-800"></span>
                )}
              </button>
              {/* Add notification dropdown here if needed later */}
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-x-hidden overflow-y-auto bg-dark-900 p-4 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default DashboardLayout;
