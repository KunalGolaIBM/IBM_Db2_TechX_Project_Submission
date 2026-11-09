import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../../lib/api';
import { useAuthStore } from '../../../stores/authStore';
import { Page, Card, Table, Badge, toneForStatus } from '../Shared';
import { Link } from 'react-router-dom';

export default function SellerProjects() {
  const { user } = useAuthStore(); const actor = { actor_role:'seller', actor_id:user?.id };
  const q = useQuery({ queryKey:['cprojects',actor.actor_id], queryFn:()=>api.listCarbonProjects(actor) });
  const rows = (q.data?.carbon_projects||[]).map(p=>[<div><div className="font-semibold">{p.project_name}</div><div className="text-xs text-[#6A8576]">{p.location}, {p.country}</div></div>, `${p.land_area} ${p.land_type}`, `${p.estimated_carbon_potential_tco2e} tCO₂e (demo est.)`, <Badge tone={toneForStatus(p.admin_status)}>{p.admin_status}</Badge>, p.verification_status||'—']);
  return <Page title="My Carbon Projects" subtitle="Submitted projects and verification status. Estimated potential is not a certified credit." actions={<Link to="/demo/seller/land-registration" className="text-sm font-semibold px-3 py-2 rounded-xl bg-[#0C3327] text-white">Register land</Link>}>
    <Card><Table cols={['Project','Land','Estimated potential','Admin status','Verification']} rows={rows} empty="No carbon projects yet. Register land and submit for verification." /></Card>
  </Page>;
}
