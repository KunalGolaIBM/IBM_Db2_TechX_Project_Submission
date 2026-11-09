import React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../../../lib/api';
import { useAuthStore } from '../../../stores/authStore';
import { Page, Card, Table, Badge, Btn, toneForStatus } from '../Shared';

export default function AdminCreditVerification() {
  const { user } = useAuthStore(); const actor = { actor_role:'admin', actor_id:user?.id };
  const qc = useQueryClient();
  const q = useQuery({ queryKey:['mlist','admin'], queryFn:()=>api.listMarketplaceListings({ actor_role:'admin', actor_id:actor.actor_id }) });
  const review = useMutation({ mutationFn:({id,decision})=>api.reviewMarketplaceListing(id,{ actor_role:'admin', actor_id:actor.actor_id, decision, reason:`Admin ${decision} (demo)` }), onSuccess:()=>{qc.invalidateQueries({queryKey:['mlist']}); qc.invalidateQueries({queryKey:['overview']});} });
  const rows = (q.data?.listings||[]).map(l=>[<div><div className="font-semibold">{l.project_name}</div><div className="text-xs text-[#6A8576]">{l.country}, {l.state}</div></div>, `${l.quantity_available}/${l.quantity_total}`, `$${l.price_per_credit}`, <Badge tone={toneForStatus(l.market_status)}>{l.market_status}</Badge>, l.verification_status, <div className="flex flex-wrap gap-1"><Btn onClick={()=>review.mutate({id:l.id,decision:'approved'})}>Approve</Btn><Btn variant="secondary" onClick={()=>review.mutate({id:l.id,decision:'suspended'})}>Suspend</Btn><Btn variant="danger" onClick={()=>review.mutate({id:l.id,decision:'rejected'})}>Reject</Btn></div>]);
  return <Page title="Credit Verification & Marketplace Management" subtitle="Approve eligible listings, reject unsupported listings, suspend suspicious listings. Approved+available listings become purchasable.">
    <Card><Table cols={['Listing','Qty avail/total','Price','Market','Verification','Actions']} rows={rows} /></Card>
  </Page>;
}
