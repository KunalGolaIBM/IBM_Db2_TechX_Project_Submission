import React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../../../lib/api';
import { useAuthStore } from '../../../stores/authStore';
import { Page, Card, Table, Badge, Btn, toneForStatus } from '../Shared';

export default function AdminDashboard() {
  const { user } = useAuthStore(); const actor = { actor_role:'admin', actor_id:user?.id };
  const qc = useQueryClient();
  const q = useQuery({ queryKey:['overview'], queryFn:()=>api.platformOverview(actor) });
  const o = q.data?.overview || {};
  const reviewProject = useMutation({ mutationFn:({id,decision})=>api.reviewCarbonProject(id,{ actor_role:'admin', actor_id:actor.actor_id, decision, reason:`Admin ${decision} (demo)` }), onSuccess:()=>qc.invalidateQueries({queryKey:['overview']}) });
  const cards = [['Registered sellers',o.total_registered_sellers],['Registered buyers',o.total_registered_buyers],['Land projects',o.total_land_projects],['Submitted',o.total_submitted_projects],['Verified projects',o.total_verified_projects],['Rejected',o.total_rejected_projects],['Available credits',o.total_available_credits],['Sold credits',o.total_sold_credits],['Transactions',o.total_transactions],['Pending verifications',o.pending_verification_requests]];
  return <Page title="Admin dashboard" subtitle="Central governance for users, projects, listings, transactions, and audit history.">
    <div className="grid sm:grid-cols-2 xl:grid-cols-5 gap-4">{cards.map(([k,v])=><Card key={k}><div className="text-xs uppercase tracking-wide font-bold text-[#5B7767]">{k}</div><div className="text-3xl font-extrabold text-[#10271E] mt-1">{v ?? '—'}</div></Card>)}</div>
    <div className="grid lg:grid-cols-2 gap-5">
      <Card><h2 className="font-bold mb-3">Pending project reviews</h2>
        <div className="space-y-2">{(q.data?.pending_projects||[]).map(p=><div key={p.id} className="border border-[#EEF3EF] rounded-xl p-3"><div className="flex items-start justify-between gap-2"><div><div className="font-semibold text-sm">{p.project_name}</div><div className="text-xs text-[#6A8576]">{p.country}, {p.state} · est. {p.estimated_carbon_potential_tco2e} tCO₂e (demo)</div></div><Badge tone={toneForStatus(p.submission_status)}>{p.submission_status}</Badge></div><div className="mt-2 flex gap-2"><Btn onClick={()=>reviewProject.mutate({id:p.id,decision:'approved'})}>Approve</Btn><Btn variant="secondary" onClick={()=>reviewProject.mutate({id:p.id,decision:'needs_info'})}>Request info</Btn><Btn variant="danger" onClick={()=>reviewProject.mutate({id:p.id,decision:'rejected'})}>Reject</Btn></div></div>)}{!(q.data?.pending_projects||[]).length && <p className="text-sm text-[#6A8576]">No pending project reviews.</p>}</div></Card>
      <Card><h2 className="font-bold mb-3">Recent audit activity</h2><Table cols={['Action','Entity','Actor','Time']} rows={(q.data?.recent_audit||[]).slice(0,8).map(a=>[a.action, `${a.entity_type} ${a.entity_id||''}`, `${a.actor_role||''} ${a.actor_id||''}`, new Date(a.at).toLocaleString()])} /></Card>
    </div>
  </Page>;
}
