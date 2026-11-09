import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../../../lib/api';
import { useAuthStore } from '../../../stores/authStore';

const Input = (p) => <input {...p} className={`w-full border border-[#D8E2D9] rounded-xl px-3 py-2 text-sm bg-[#FBFCFA] ${p.className||''}`} />;
const Label = ({children}) => <label className="block text-xs font-semibold text-[#355848] mb-1">{children}</label>;
export default function LandRegistration() {
  const { user } = useAuthStore(); const actor = { actor_role:'seller', actor_id:user?.id };
  const qc = useQueryClient();
  const listQ = useQuery({ queryKey:['land',actor.actor_id], queryFn:()=>api.listLandRegistrations(actor) });
  const [f,setF]=useState({ seller_name:user?.full_name||'', country:'India', state:'Maharashtra', district:'', village:'', land_area:'', area_unit:'acres', soil_type:'', soil_health:'', soil_moisture:'', current_crop:'', previous_crop:'', farming_practices:'', irrigation:'', supporting_documents_text:'land-record-demo.pdf' });
  const set=(k,v)=>setF(s=>({...s,[k]:v}));
  const create = useMutation({ mutationFn:(payload)=>api.createLandRegistration({ ...payload, actor_id:actor.actor_id, actor_role:'seller' }), onSuccess:()=>{ qc.invalidateQueries({queryKey:['land']}); }});
  const submit = (e)=>{ e.preventDefault(); create.mutate({ ...f, land_area:Number(f.land_area), supporting_documents: f.supporting_documents_text ? [{name:f.supporting_documents_text,type:'supporting_evidence',status:'uploaded_demo'}]:[] }); };
  const submitProject = useMutation({ mutationFn:(land_registration_id)=>api.createCarbonProject({ actor_id:actor.actor_id, actor_role:'seller', land_registration_id }), onSuccess:()=>{ qc.invalidateQueries({queryKey:['cprojects']}); qc.invalidateQueries({queryKey:['land']}); }});
  return <div className="space-y-6 max-w-7xl mx-auto">
    <div><h1 className="text-2xl font-extrabold text-[#10271E]">My Land & Carbon Assessment</h1><p className="text-sm text-[#617E6F]">Register agricultural land, upload supporting evidence metadata (demo), and generate an estimated carbon-potential assessment. Estimates are not certified carbon credits.</p></div>
    <div className="grid lg:grid-cols-2 gap-6">
      <form onSubmit={submit} className="bg-white border border-[#DCE6DE] rounded-2xl p-5 space-y-3">
        <div className="grid sm:grid-cols-2 gap-3">
          <div><Label>Farmer/seller name</Label><Input value={f.seller_name} onChange={e=>set('seller_name',e.target.value)} required/></div>
          <div><Label>Country</Label><Input value={f.country} onChange={e=>set('country',e.target.value)} required/></div>
          <div><Label>State</Label><Input value={f.state} onChange={e=>set('state',e.target.value)} required/></div>
          <div><Label>District</Label><Input value={f.district} onChange={e=>set('district',e.target.value)}/></div>
          <div><Label>Village/location</Label><Input value={f.village} onChange={e=>set('village',e.target.value)}/></div>
          <div><Label>Total land area</Label><div className="flex gap-2"><Input type="number" step="any" value={f.land_area} onChange={e=>set('land_area',e.target.value)} required/><select value={f.area_unit} onChange={e=>set('area_unit',e.target.value)} className="border border-[#D8E2D9] rounded-xl px-2 text-sm"><option>acres</option><option>hectares</option></select></div></div>
          <div><Label>Soil type</Label><Input value={f.soil_type} onChange={e=>set('soil_type',e.target.value)}/></div>
          <div><Label>Soil health</Label><Input value={f.soil_health} onChange={e=>set('soil_health',e.target.value)} placeholder="e.g. good / moderate (demo)"/></div>
          <div><Label>Soil moisture</Label><Input value={f.soil_moisture} onChange={e=>set('soil_moisture',e.target.value)} placeholder="e.g. moderate (demo)"/></div>
          <div><Label>Current crop</Label><Input value={f.current_crop} onChange={e=>set('current_crop',e.target.value)}/></div>
          <div><Label>Previous crop</Label><Input value={f.previous_crop} onChange={e=>set('previous_crop',e.target.value)}/></div>
          <div><Label>Irrigation</Label><Input value={f.irrigation} onChange={e=>set('irrigation',e.target.value)}/></div>
        </div>
        <div><Label>Farming practices</Label><textarea value={f.farming_practices} onChange={e=>set('farming_practices',e.target.value)} className="w-full border border-[#D8E2D9] rounded-xl px-3 py-2 text-sm min-h-[70px]"/></div>
        <div><Label>Supporting document names (demo metadata; no file contents stored)</Label><Input value={f.supporting_documents_text} onChange={e=>set('supporting_documents_text',e.target.value)} placeholder="land-record.pdf, soil-test.pdf"/></div>
        {create.error && <p className="text-sm text-red-600">{create.error.message}</p>}
        <button disabled={create.isPending} className="bg-[#0C3327] text-white font-semibold px-4 py-2.5 rounded-xl text-sm">{create.isPending?'Saving…':'Save & generate estimated assessment'}</button>
      </form>
      <div className="space-y-4">
        {(listQ.data?.land_registrations||[]).map(r=>(
          <div key={r.id} className="bg-white border border-[#DCE6DE] rounded-2xl p-5">
            <div className="flex items-start justify-between gap-3"><div><h3 className="font-bold text-[#10271E]">{r.village||r.district||r.state}, {r.country}</h3><p className="text-xs text-[#6A8576]">{r.land_area} {r.area_unit} · {r.current_crop||'Crop not set'} · Status: {r.status}</p></div><span className="text-[11px] font-bold px-2 py-1 rounded-full bg-[#F3F7F4]">{r.linked_carbon_project_id?'Project submitted':'Assessment ready'}</span></div>
            {r.ai_assessment && <div className="mt-3 border border-[#E6EEE8] rounded-xl p-3 bg-[#FAFCFA]"><p className="text-xs font-bold text-emerald-800 mb-1">{r.ai_assessment.label}</p><div className="grid grid-cols-2 gap-2 text-xs"><div>Land health: <b>{r.ai_assessment.land_health_score}/100</b></div><div>Total potential: <b>{r.ai_assessment.estimated_total_potential_tco2e} tCO₂e</b></div><div>Soil carbon: <b>{r.ai_assessment.estimated_soil_carbon_tco2e}</b></div><div>Biomass carbon: <b>{r.ai_assessment.estimated_biomass_carbon_tco2e}</b></div></div><p className="text-[11px] text-[#617E6F] mt-2">{r.ai_assessment.note}</p></div>}
            {!r.linked_carbon_project_id && <button onClick={()=>submitProject.mutate(r.id)} disabled={submitProject.isPending} className="mt-3 text-sm font-semibold px-3 py-2 rounded-xl border border-[#CFE3D6] bg-[#F3FAF6] text-[#0C3327]">Submit project for verification</button>}
          </div>
        ))}
        {!listQ.data?.land_registrations?.length && <div className="bg-white border border-dashed border-[#CFE3D6] rounded-2xl p-6 text-sm text-[#617E6F]">No land registrations yet. Use the form to create one.</div>}
      </div>
    </div>
  </div>;
}
