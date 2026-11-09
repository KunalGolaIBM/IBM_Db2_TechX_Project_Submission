import React, { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import api from '../../../lib/api';
import { useAuthStore } from '../../../stores/authStore';
import { Page, Card, Btn, Field, Select, Badge } from '../Shared';

export default function DocumentVerification() {
  const { user } = useAuthStore();
  const [projectId,setProjectId]=useState('');
  const listingsQ = useQuery({ queryKey:['market',{actor_role:'buyer',actor_id:user?.id}], queryFn:()=>api.listMarketplaceListings({ actor_role:'buyer', actor_id:user?.id }) });
  const docsQ = useQuery({ queryKey:['docs',projectId], queryFn:()=>api.listProjectDocuments(projectId), enabled:!!projectId });
  const review = useMutation({ mutationFn:()=>api.reviewProjectDocuments({ carbon_project_id: projectId }) });
  const projects = [...new Map((listingsQ.data?.listings||[]).filter(l=>l.carbon_project_id).map(l=>[l.carbon_project_id, { id:l.carbon_project_id, name:l.project_name }])).values()];
  return <Page title="Document Verification" subtitle="Inspect project documents and run an AI-assisted consistency review. AI review is not official certification.">
    <Card><div className="grid sm:grid-cols-[1fr_auto] gap-3 items-end"><Field label="Project"><Select value={projectId} onChange={e=>setProjectId(e.target.value)}><option value="">Select project</option>{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</Select></Field><Btn disabled={!projectId||review.isPending} onClick={()=>review.mutate()}>{review.isPending?'Reviewing…':'Run AI-assisted review'}</Btn></div></Card>
    <div className="grid lg:grid-cols-2 gap-5">
      <Card><h2 className="font-bold mb-3">Documents</h2>{(docsQ.data?.documents||[]).map(d=><div key={d.id} className="border border-[#EEF3EF] rounded-xl p-3 mb-2 text-sm"><div className="font-semibold">{d.name}</div><div className="text-xs text-[#6A8576]">{d.doc_type} · {d.status}</div></div>)}{!!projectId && !(docsQ.data?.documents||[]).length && <p className="text-sm text-[#6A8576]">No documents found for this project.</p>}</Card>
      <Card><h2 className="font-bold mb-3">Verification summary</h2>
        {review.data ? <div className="space-y-3 text-sm"><div className="flex flex-wrap gap-2">{(review.data.findings||[]).map((f,i)=><Badge key={i} tone={f.severity==='high'?'red':f.severity==='medium'?'amber':'neutral'}>{f.message}</Badge>)}</div>{review.data.ai_summary && <div className="bg-[#FAFCFA] border border-[#E6EEE8] rounded-xl p-3 whitespace-pre-wrap text-xs">{review.data.ai_summary}</div>}<p className="text-[11px] text-amber-800 bg-amber-50 rounded-xl p-2">{review.data.disclaimer}</p></div> : <p className="text-sm text-[#6A8576]">Select a project and run a review. Findings identify missing/inconsistent/unsupported claims from available metadata.</p>}
        {review.error && <p className="text-sm text-red-600 mt-2">{review.error.message}</p>}
      </Card>
    </div>
  </Page>;
}
