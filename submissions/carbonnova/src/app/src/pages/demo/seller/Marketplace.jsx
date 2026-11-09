import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../../../lib/api';
import { useAuthStore } from '../../../stores/authStore';
import { Page, Card, Table, Badge, Btn, Field, Input, Select, toneForStatus } from '../Shared';

export default function SellerMarketplace() {
  const { user } = useAuthStore(); const actor = { actor_role:'seller', actor_id:user?.id };
  const qc = useQueryClient();
  const projectsQ = useQuery({ queryKey:['cprojects',actor.actor_id], queryFn:()=>api.listCarbonProjects(actor) });
  const listQ = useQuery({ queryKey:['mlist',actor.actor_id], queryFn:()=>api.listMarketplaceListings(actor) });
  const [f,setF]=useState({ carbon_project_id:'', quantity:'', price_per_credit:'18' });
  const create = useMutation({ mutationFn:(payload)=>api.createMarketplaceListing({ ...payload, actor_id:actor.actor_id, actor_role:'seller' }), onSuccess:()=>{ qc.invalidateQueries({queryKey:['mlist']}); setF(s=>({...s,quantity:''})); }});
  const approved = (projectsQ.data?.carbon_projects||[]).filter(p=>['approved','verified'].includes(p.admin_status));
  return <Page title="Seller Marketplace" subtitle="Manage carbon-credit listings. Only admin-approved projects can be listed; only approved listings can be purchased.">
    <div className="grid lg:grid-cols-3 gap-5">
      <Card className="lg:col-span-1">
        <h2 className="font-bold text-[#10271E] mb-3">Add listing</h2>
        <div className="space-y-3">
          <Field label="Approved carbon project"><Select value={f.carbon_project_id} onChange={e=>setF({...f,carbon_project_id:e.target.value})}><option value="">Select project</option>{approved.map(p=><option key={p.id} value={p.id}>{p.project_name}</option>)}</Select></Field>
          <Field label="Credit quantity"><Input type="number" min="1" step="1" value={f.quantity} onChange={e=>setF({...f,quantity:e.target.value})}/></Field>
          <Field label="Price per credit (USD)"><Input type="number" min="0" step="0.01" value={f.price_per_credit} onChange={e=>setF({...f,price_per_credit:e.target.value})}/></Field>
          {create.error && <p className="text-sm text-red-600">{create.error.message}</p>}
          <Btn disabled={create.isPending||!f.carbon_project_id||!f.quantity} onClick={()=>create.mutate({ carbon_project_id:f.carbon_project_id, quantity:Number(f.quantity), price_per_credit:Number(f.price_per_credit) })}>{create.isPending?'Submitting…':'Submit listing for review'}</Btn>
          {!approved.length && <p className="text-xs text-amber-700 bg-amber-50 rounded-xl p-2">No admin-approved projects yet. Submit a land project and wait for admin approval.</p>}
        </div>
      </Card>
      <Card className="lg:col-span-2">
        <h2 className="font-bold text-[#10271E] mb-3">My listings</h2>
        <Table cols={['Project','Location','Qty avail/total','Price','Market status']} rows={(listQ.data?.listings||[]).map(l=>[<div><div className="font-semibold">{l.project_name}</div><div className="text-xs text-[#6A8576]">{l.project_type} · {l.verification_status}</div></div>, `${l.state}, ${l.country}`, `${l.quantity_available} / ${l.quantity_total}`, `$${l.price_per_credit}`, <Badge tone={toneForStatus(l.market_status)}>{l.market_status}/{l.listing_status||''}</Badge>])} />
      </Card>
    </div>
  </Page>;
}
