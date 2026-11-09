import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../../lib/api';
import { useAuthStore } from '../../../stores/authStore';
import { Page, Card, Field, Select } from '../Shared';

const dims = [['additionality','Would reductions/removals have happened without the project? Not independently tested in demo.'],['permanence','Risk that stored carbon is reversed.'],['leakage_risk','Risk that emissions increase elsewhere.'],['monitoring_methodology','How project monitors and reports outcomes.'],['verification_standard','Third-party standard/certifier status. "Not independently verified" when unavailable.'],['transparency','Availability of project data and documentation.'],['documentation','Presence and consistency of supporting evidence.'],['vintage_year','Year associated with credited/claimed mitigation period.'],['project_location','Where project activities occur.'],['co_benefits','Social/environmental co-benefits (reported).']];
export default function Quality() {
  const { user } = useAuthStore();
  const q = useQuery({ queryKey:['market',{actor_role:'buyer',actor_id:user?.id}], queryFn:()=>api.listMarketplaceListings({ actor_role:'buyer', actor_id:user?.id }) });
  const [id,setId]=useState('');
  const l = (q.data?.listings||[]).find(x=>x.id===id);
  return <Page title="Carbon-Credit Quality Assessment" subtitle="Compare projects using assessment dimensions. Displayed values are demo/project metadata unless independently verified.">
    <Card><Field label="Select project"><Select value={id} onChange={e=>setId(e.target.value)}><option value="">Choose</option>{(q.data?.listings||[]).map(x=><option key={x.id} value={x.id}>{x.project_name} — {x.country}</option>)}</Select></Field></Card>
    <div className="grid lg:grid-cols-2 gap-5">
      <Card><h2 className="font-bold mb-3">Assessment dimensions</h2><div className="space-y-2">{dims.map(([k,d])=><div key={k} className="border border-[#EEF3EF] rounded-xl p-3"><div className="font-semibold text-sm">{k.replace(/_/g,' ')}</div><div className="text-xs text-[#617E6F]">{d}</div>{l && <div className="text-sm mt-1"><b>Project:</b> {String((l.quality_assessment||{})[k] ?? 'Not provided')}</div>}</div>)}</div></Card>
      <Card><h2 className="font-bold mb-3">Selected project</h2>{l ? <pre className="text-xs bg-[#FAFCFA] border rounded-xl p-3 overflow-auto">{JSON.stringify({ project:l.project_name,country:l.country,state:l.state,verification_status:l.verification_status,quality_tier:l.quality_tier,quality_assessment:l.quality_assessment },null,2)}</pre> : <p className="text-sm text-[#6A8576]">Select a project to view its quality assessment details.</p>}</Card>
    </div>
  </Page>;
}
