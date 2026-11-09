import React from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Sprout, ShoppingBag, Shield, ArrowRight, Home } from 'lucide-react';
import CarbonNovaLogo from '../components/common/CarbonNovaLogo';
import { useAuthStore } from '../stores/authStore';

const roles = [
  { key: 'seller', title: 'Continue as Seller', icon: Sprout, desc: 'Register land, analyze carbon potential, submit projects, and manage credit listings.', to: '/demo/seller/dashboard', accent: 'from-emerald-600 to-emerald-500' },
  { key: 'buyer', title: 'Continue as Buyer', icon: ShoppingBag, desc: 'Explore the global marketplace, assess quality, review documents, and complete demo purchases.', to: '/demo/buyer/dashboard', accent: 'from-teal-600 to-cyan-600' },
  { key: 'admin', title: 'Continue as Admin', icon: Shield, desc: 'Govern users, verify projects and listings, monitor transactions, and review audit logs.', to: '/demo/admin/dashboard', accent: 'from-slate-700 to-slate-600' },
];

export default function RoleSelect() {
  const navigate = useNavigate();
  const { selectDemoRole } = useAuthStore();
  return (
    <div className="min-h-screen bg-[#F4F6F4] text-[#142A20]">
      <div className="max-w-6xl mx-auto px-6 py-10">
        <div className="flex items-center justify-between mb-10">
          <CarbonNovaLogo />
          <Link to="/" className="inline-flex items-center gap-2 text-sm font-semibold text-[#1F5A40] hover:underline"><Home size={16}/> Back to homepage</Link>
        </div>
        <div className="max-w-3xl mb-8">
          <p className="text-xs font-bold uppercase tracking-wider text-emerald-700 mb-2">Hackathon demonstration</p>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-[#0E2018] tracking-tight">Choose a demonstration role</h1>
          <p className="text-[#5B7767] mt-3">These options are role selectors for the prototype demonstration, not authentication. No username or password is required.</p>
        </div>
        <div className="grid md:grid-cols-3 gap-5">
          {roles.map((r) => {
            const Icon = r.icon;
            return (
              <button key={r.key} onClick={() => { selectDemoRole(r.key); navigate(r.to); }}
                className="text-left bg-white border border-[#DCE6DE] rounded-2xl p-6 shadow-sm hover:shadow-lg hover:border-emerald-300 transition-all group">
                <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${r.accent} text-white flex items-center justify-center mb-4`}><Icon size={22}/></div>
                <h2 className="text-lg font-bold text-[#10271E] mb-2">{r.title}</h2>
                <p className="text-sm text-[#617E6F] leading-relaxed mb-5">{r.desc}</p>
                <span className="inline-flex items-center gap-2 text-sm font-semibold text-[#0C3327]">Open dashboard <ArrowRight size={16} className="group-hover:translate-x-0.5 transition-transform"/></span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
