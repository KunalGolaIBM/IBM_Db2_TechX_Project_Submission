import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { MapPinned, Sprout, BadgeDollarSign, ArrowLeftRight, FileCheck2 } from 'lucide-react';
import api from '../../../lib/api';
import { useAuthStore } from '../../../stores/authStore';

const Card = ({ children }) => <div className="bg-white border border-[#DCE6DE] rounded-2xl p-5 shadow-sm">{children}</div>;
export default function SellerDashboard() {
  const { user } = useAuthStore();
  const actor = { actor_role:'seller', actor_id:user?.id };
  const landQ = useQuery({ queryKey:['land', actor.actor_id], queryFn:()=>api.listLandRegistrations(actor) });
  const projQ = useQuery({ queryKey:['cprojects', actor.actor_id], queryFn:()=>api.listCarbonProjects(actor) });
  const listQ = useQuery({ queryKey:['mlist', actor.actor_id], queryFn:()=>api.listMarketplaceListings(actor) });
  const txQ = useQuery({ queryKey:['tx', actor.actor_id], queryFn:()=>api.listTransactions(actor) });
  const balQ = useQuery({ queryKey:['bal', actor.actor_id], queryFn:()=>api.listBalances(actor) });
  const lands = landQ.data?.land_registrations||[]; const projects = projQ.data?.carbon_projects||[]; const listings = listQ.data?.listings||[]; const txs = txQ.data?.transactions||[]; const bal = balQ.data?.balance;
  const stats = [
    { label:'Registered lands', value:lands.length, icon:MapPinned, to:'/demo/seller/land-registration' },
    { label:'Carbon projects', value:projects.length, icon:Sprout, to:'/demo/seller/projects' },
    { label:'Listings', value:listings.length, icon:BadgeDollarSign, to:'/demo/seller/marketplace' },
    { label:'Available credits', value:bal?.available_credits ?? 0, icon:FileCheck2, to:'/demo/seller/credits' },
    { label:'Transactions', value:txs.length, icon:ArrowLeftRight, to:'/demo/seller/transactions' },
  ];
  return <div className="space-y-6 max-w-7xl mx-auto">
    <div><h1 className="text-2xl font-extrabold text-[#10271E]">Seller dashboard</h1><p className="text-sm text-[#617E6F]">Manage land registration, carbon potential assessments, listings, and credit transactions. Estimates are not certified credits.</p></div>
    <div className="grid sm:grid-cols-2 xl:grid-cols-5 gap-4">{stats.map(s=>{const I=s.icon; return <Link key={s.label} to={s.to}><Card><div className="flex items-center justify-between"><span className="text-xs font-semibold uppercase tracking-wide text-[#5B7767]">{s.label}</span><div className="w-9 h-9 rounded-xl bg-[#E8F7F0] text-[#0A7B4E] flex items-center justify-center"><I size={18}/></div></div><div className="text-3xl font-extrabold text-[#10271E] mt-2">{s.value}</div></Card></Link>;})}</div>
    <div className="grid lg:grid-cols-2 gap-5">
      <Card><h2 className="font-bold text-[#10271E] mb-3">Recent carbon projects</h2><div className="space-y-2">{projects.slice(0,5).map(p=><div key={p.id} className="flex items-center justify-between border border-[#EDF2EE] rounded-xl p-3"><div><div className="font-semibold text-sm">{p.project_name}</div><div className="text-xs text-[#6A8576]">{p.country}, {p.state} · est. {p.estimated_carbon_potential_tco2e} tCO₂e (demo)</div></div><span className="text-[11px] font-bold px-2 py-1 rounded-full bg-[#F3F7F4] text-[#355848]">{p.admin_status}</span></div>)}{!projects.length&&<p className="text-sm text-[#6A8576]">No projects yet. Register land and submit a project for verification.</p>}</div></Card>
      <Card><h2 className="font-bold text-[#10271E] mb-3">Quick actions</h2><div className="grid sm:grid-cols-2 gap-3">{[['/demo/seller/land-registration','Register land & assessment'],['/demo/seller/land-intelligence','Open Land Intelligence'],['/demo/seller/marketplace','Manage marketplace listings'],['/demo/seller/transactions','View transactions']].map(([to,l])=><Link key={to} to={to} className="border border-[#DCE6DE] rounded-xl p-3 text-sm font-semibold hover:border-emerald-300 hover:bg-[#F7FBF8]">{l}</Link>)}</div><p className="text-[11px] text-[#6A8576] mt-4">Demonstration data only. Credit sales require admin-approved projects/listings.</p></Card>
    </div>
  </div>;
}
