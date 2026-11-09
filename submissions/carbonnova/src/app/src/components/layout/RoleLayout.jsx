import React, { useState } from 'react';
import { Outlet, Link, NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, Store, Globe2, FilePlus2, Layers, Award, ArrowLeftRight, User, Search, BadgeCheck, FileCheck2,
  Briefcase, Receipt, Users, Building2, ClipboardCheck, Settings, LogOut, Home, Menu, X, Shield, Leaf
} from 'lucide-react';
import CarbonNovaLogo from '../common/CarbonNovaLogo';
import { useAuthStore } from '../../stores/authStore';

const NAV = {
  seller: [
    { to: '/demo/seller/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/demo/seller/marketplace', label: 'Marketplace', icon: Store },
    { to: '/demo/seller/land-intelligence', label: 'Land Intelligence', icon: Globe2 },
    { to: '/demo/seller/land-registration', label: 'My Land Registration', icon: FilePlus2 },
    { to: '/demo/seller/projects', label: 'My Carbon Projects', icon: Layers },
    { to: '/demo/seller/credits', label: 'My Credits', icon: Award },
    { to: '/demo/seller/transactions', label: 'Transactions', icon: ArrowLeftRight },
    { to: '/demo/seller/profile', label: 'Profile', icon: User },
  ],
  buyer: [
    { to: '/demo/buyer/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/demo/buyer/marketplace', label: 'Global Marketplace', icon: Store },
    { to: '/demo/buyer/explore', label: 'Explore Projects', icon: Search },
    { to: '/demo/buyer/quality', label: 'Quality Assessment', icon: BadgeCheck },
    { to: '/demo/buyer/documents', label: 'Document Verification', icon: FileCheck2 },
    { to: '/demo/buyer/portfolio', label: 'My Portfolio', icon: Briefcase },
    { to: '/demo/buyer/transactions', label: 'Transactions', icon: Receipt },
    { to: '/demo/buyer/profile', label: 'Profile', icon: User },
  ],
  admin: [
    { to: '/demo/admin/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/demo/admin/users', label: 'User Management', icon: Users },
    { to: '/demo/admin/sellers', label: 'Seller Management', icon: Building2 },
    { to: '/demo/admin/buyers', label: 'Buyer Management', icon: User },
    { to: '/demo/admin/land-projects', label: 'Land Projects', icon: Layers },
    { to: '/demo/admin/credit-verification', label: 'Credit Verification', icon: ClipboardCheck },
    { to: '/demo/admin/marketplace', label: 'Marketplace Management', icon: Store },
    { to: '/demo/admin/transactions', label: 'Transactions', icon: ArrowLeftRight },
    { to: '/demo/admin/audit', label: 'Audit Logs', icon: Shield },
    { to: '/demo/admin/settings', label: 'Platform Settings', icon: Settings },
  ],
};

export default function RoleLayout({ role }) {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const { user, clearDemoRole } = useAuthStore();
  const items = NAV[role] || [];
  const roleLabel = role ? role.charAt(0).toUpperCase() + role.slice(1) : 'Demo';
  const navCls = ({ isActive }) => `flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-colors ${isActive ? 'bg-[#16513E] text-white' : 'text-[#96B3A4] hover:text-white hover:bg-white/5'}`;
  return (
    <div className="flex h-screen overflow-hidden bg-[#F4F6F4] text-[#142A20]">
      {open && <div className="fixed inset-0 z-40 bg-black/50 lg:hidden" onClick={() => setOpen(false)} />}
      <aside className={`fixed inset-y-0 left-0 z-50 w-64 bg-[#0A291E] border-r border-[#082219] flex flex-col transition-transform lg:static lg:translate-x-0 ${open ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="h-16 flex items-center justify-between px-5 border-b border-[#143B2E]/60">
          <Link to="/"><CarbonNovaLogo light size="sm" /></Link>
          <button className="lg:hidden text-[#92B5A2]" onClick={() => setOpen(false)}><X size={18}/></button>
        </div>
        <div className="px-4 py-3 border-b border-[#143B2E]/40">
          <p className="text-[10px] uppercase tracking-wider text-[#6FA58A] font-bold">{roleLabel} demo</p>
          <p className="text-sm font-semibold text-white truncate">{user?.full_name || 'Demo User'}</p>
          <p className="text-[11px] text-[#86A897] truncate">{user?.organization}</p>
        </div>
        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
          {items.map((it) => { const Icon = it.icon; return <NavLink key={it.to} to={it.to} onClick={() => setOpen(false)} className={navCls}><Icon size={17}/>{it.label}</NavLink>; })}
        </nav>
        <div className="p-3 border-t border-[#143B2E]/40 space-y-1">
          <button onClick={() => { clearDemoRole(); navigate('/role-select'); }} className="w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm text-[#96B3A4] hover:text-white hover:bg-white/5"><Leaf size={17}/> Switch role</button>
          <Link to="/" className="flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm text-[#96B3A4] hover:text-white hover:bg-white/5"><Home size={17}/> Homepage</Link>
        </div>
      </aside>
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-16 bg-white border-b border-[#E3E9E3] px-4 lg:px-7 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <button className="lg:hidden p-2 rounded-lg hover:bg-[#F2F7F4]" onClick={() => setOpen(true)}><Menu size={20}/></button>
            <div><p className="text-sm font-bold text-[#10271E]">{roleLabel} Dashboard</p><p className="text-[11px] text-[#6A8576]">Demonstration mode · shared backend data · simulated/estimated values labeled</p></div>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-7"><Outlet context={{ demoRole: role }} /></main>
      </div>
    </div>
  );
}
