import React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../../../lib/api';
import { useAuthStore } from '../../../stores/authStore';
import { Page, Card, Table, Badge, Btn, toneForStatus } from '../Shared';

export default function AdminLandProjects() {
  const { user } = useAuthStore(); const actor = { actor_role:'admin', actor_id:user?.id };
  const qc = useQueryClient();
  const projectsQ = useQuery({ queryKey:['cprojects','admin'], queryFn:()=>api.listCarbonProjects({ actor_role:'admin', actor_id:actor.actor_id }) });
  const landsQ = useQuery({ queryKey:['lands','admin'], queryFn:()=>api.adminLandRegistrations(actor) });
  const review = useMutation({ mutationFn:({id,decision})=>api.reviewCarbonProject(id,{ actor_role:'admin', actor_id:actor.actor_id, decision, reason:`Admin ${decision} (demo)` }), onSuccess:()=>{qc.invalidateQueries({queryKey:['cprojects']}); qc.invalidateQueries({queryKey:['overview']});} });
  const rows = (projectsQ.data?.carbon_projects||[]).map(p=>[<div><div className="font-semibold">{p.project_name}</div><div className="text-xs text-[#6A8576]">{p.location}, {p.country}</div></div>, p.seller_id, `${p.estimated_carbon_potential_tco2e} tCO₂e (demo)`, <Badge tone={toneForStatus(p.admin_status)}>{p.admin_status}</Badge>, <div className="flex flex-wrap gap-1"><Btn onClick={()=>review.mutate({id:p.id,decision:'approved'})}>Approve</Btn><Btn variant="secondary" onClick={()=>review.mutate({id:p.id,decision:'suspended'})}>Suspend</Btn><Btn variant="danger" onClick={()=>review.mutate({id:p.id,decision:'rejected'})}>Reject</Btn></div>]);
  return <Page title="Land Projects & Verification" subtitle="Inspect submitted land/project records and approve, reject, suspend, or request info. Approval affects marketplace eligibility.">
    <Card className="mb-5"><h2 className="font-bold mb-3">Land registrations ({(landsQ.data?.land_registrations||[]).length})</h2><Table cols={['Seller','Location','Area','Status']} rows={(landsQ.data?.land_registrations||[]).map(r=>[r.seller_name, `${r.village||r.district}, ${r.state}, ${r.country}`, `${r.land_area} ${r.area_unit}`, <Badge tone={toneForStatus(r.status)}>{r.status}</Badge>])} /></Card>
    <Card><h2 className="font-bold mb-3">Carbon project review</h2><Table cols={['Project','Seller','Potential','Status','Actions']} rows={rows} /></Card>
  </Page>;
}
