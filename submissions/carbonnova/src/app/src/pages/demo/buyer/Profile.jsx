import React from 'react';
import { Link } from 'react-router-dom';
import { useAuthStore } from '../../../stores/authStore';
import { Page, Card } from '../Shared';
export default function BuyerProfile(){ const {user,clearDemoRole}=useAuthStore(); return <Page title="Profile" subtitle="Demonstration role profile (no authentication)."><Card><div className="text-sm space-y-1"><div><b>Name:</b> {user?.full_name}</div><div><b>Organization:</b> {user?.organization}</div><div><b>Role:</b> {user?.role}</div></div><div className="mt-4 flex gap-2"><Link to="/role-select" onClick={clearDemoRole} className="text-sm font-semibold px-3 py-2 rounded-xl border border-[#CFE3D6] bg-[#F3FAF6]">Switch role</Link><Link to="/" className="text-sm font-semibold px-3 py-2 rounded-xl bg-[#0C3327] text-white">Homepage</Link></div></Card></Page>; }
