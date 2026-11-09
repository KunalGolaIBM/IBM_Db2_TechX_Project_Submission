import React, { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import api from '../../../lib/api';
import { useAuthStore } from '../../../stores/authStore';
import { Page, Card, Badge, Btn, Field, Input, Select, toneForStatus } from '../Shared';

export default function BuyerMarketplace() {
  const { user } = useAuthStore(); const actor = { actor_role:'buyer', actor_id:user?.id };
  const qc = useQueryClient();
  const [filters,setFilters]=useState({ actor_role:'buyer', actor_id:actor.actor_id, q:'', country:'', state:'', project_type:'', verification_status:'' });
  const [qty,setQty]=useState({});
  const [selected,setSelected]=useState(null);
  const q = useQuery({ queryKey:['market',filters], queryFn:()=>api.listMarketplaceListings(filters) });
  const buy = useMutation({ mutationFn:(payload)=>api.purchaseCredits({ ...payload, actor_role:'buyer', actor_id:actor.actor_id }), onSuccess:()=>{ qc.invalidateQueries({queryKey:['market']}); qc.invalidateQueries({queryKey:['tx']}); qc.invalidateQueries({queryKey:['bal']}); }});
  const listings = q.data?.listings||[];
  const countries = [...new Set(listings.map(l=>l.country).filter(Boolean))];
  const markers = listings.filter(l=>Number.isFinite(Number(l.project?.latitude || l.latitude)) || Number.isFinite(Number(l.project?.longitude || l.longitude)));
  return <Page title="Global Carbon Marketplace" subtitle="Explore approved demo listings by country/state. Only admin-approved, available listings can be purchased. Demonstration data; not independently certified.">
    <Card><div className="grid sm:grid-cols-2 lg:grid-cols-6 gap-3">
      <Field label="Search"><Input value={filters.q} onChange={e=>setFilters({...filters,q:e.target.value})} placeholder="Project, country, state"/></Field>
      <Field label="Country"><Input value={filters.country} onChange={e=>setFilters({...filters,country:e.target.value})} placeholder="e.g. India"/></Field>
      <Field label="State/region"><Input value={filters.state} onChange={e=>setFilters({...filters,state:e.target.value})}/></Field>
      <Field label="Project type"><Input value={filters.project_type} onChange={e=>setFilters({...filters,project_type:e.target.value})} placeholder="agroforestry"/></Field>
      <Field label="Verification"><Input value={filters.verification_status} onChange={e=>setFilters({...filters,verification_status:e.target.value})} placeholder="approved / not"/></Field>
      <div className="flex items-end"><Btn variant="secondary" onClick={()=>setFilters({ actor_role:'buyer', actor_id:actor.actor_id, q:'', country:'', state:'', project_type:'', verification_status:'' })}>Clear filters</Btn></div>
    </div></Card>
    <div className="grid xl:grid-cols-2 gap-5">
      <Card><h2 className="font-bold text-[#10271E] mb-3">Available projects ({listings.length})</h2>
        <div className="space-y-3 max-h-[520px] overflow-auto pr-1">{listings.map(l=>(
          <div key={l.id} className={`border rounded-2xl p-4 ${selected?.id===l.id?'border-emerald-400 bg-emerald-50/30':'border-[#E6EEE8]'}`}>
            <div className="flex items-start justify-between gap-3"><div><button onClick={()=>setSelected(l)} className="font-bold text-left text-[#10271E] hover:underline">{l.project_name}</button><div className="text-xs text-[#6A8576]">{l.location}, {l.state}, {l.country} · {l.project_type||l.land_type}</div></div><Badge tone={toneForStatus(l.market_status)}>{l.listing_status}</Badge></div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-3 text-xs"><div>Qty: <b>{l.quantity_available}</b></div><div>Price: <b>${l.price_per_credit}/credit</b></div><div>Quality: <b>{l.quality_tier}</b></div><div>Verification: <b className="break-words">{String(l.verification_status).slice(0,28)}</b></div></div>
            <div className="mt-3 flex flex-wrap items-center gap-2"><Input type="number" min="1" step="1" value={qty[l.id]||''} onChange={e=>setQty({...qty,[l.id]:e.target.value})} placeholder="Qty" className="!w-28" />
              <Btn disabled={buy.isPending||!l.purchasable} onClick={()=>buy.mutate({ listing_id:l.id, quantity:Number(qty[l.id]) })}>{l.purchasable?'Confirm demo purchase':'Not purchasable'}</Btn>
              <Btn variant="secondary" onClick={()=>setSelected(l)}>Inspect</Btn></div>
          </div>))}
          {!listings.length && <p className="text-sm text-[#6A8576]">No listings match the current filters.</p>}
          {buy.error && <p className="text-sm text-red-600">{buy.error.message}</p>}
        </div></Card>
      <div className="space-y-5">
        <Card><h2 className="font-bold text-[#10271E] mb-3">Geographical exploration (demo coordinates)</h2>
          <div className="h-[260px] rounded-xl overflow-hidden border border-[#E6EEE8]"><MapContainer center={[20,0]} zoom={2} style={{height:'100%',width:'100%'}} scrollWheelZoom={false}>
            <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
            {listings.map((l,idx)=>{ const lat = Number(l.project?.latitude ?? (18+idx*2)); const lng = Number(l.project?.longitude ?? (73+idx*11)); return <CircleMarker key={l.id} center={[lat,lng]} radius={8} pathOptions={{color:'#0A7B4E'}}><Popup>{l.project_name}<br/>{l.country}, {l.state}<br/>{l.quantity_available} available</Popup></CircleMarker>; })}
          </MapContainer></div></Card>
        <Card><h2 className="font-bold text-[#10271E] mb-3">Project inspection</h2>
          {selected ? <div className="text-sm space-y-2"><div className="font-semibold text-base">{selected.project_name}</div><div>{selected.state}, {selected.country} · {selected.land_type}</div><div>Quantity: {selected.quantity_available} available / {selected.quantity_total} total</div><div>Price: ${selected.price_per_credit} per credit · Total value: ${selected.price_per_credit * selected.quantity_available}</div><div>Verification: {selected.verification_status}</div><div className="text-xs text-[#617E6F] whitespace-pre-wrap">{selected.description}</div><div className="border-t pt-2 mt-2"><div className="font-semibold mb-1">Quality assessment (demo)</div><pre className="text-[11px] bg-[#FAFCFA] p-2 rounded-xl overflow-auto">{JSON.stringify(selected.quality_assessment,null,2)}</pre></div><div><div className="font-semibold mb-1">Documents</div>{(selected.documents||[]).length ? selected.documents.map(d=><div key={d.id} className="text-xs border border-[#EEF3EF] rounded-lg px-2 py-1 mb-1">{d.name} · {d.doc_type} · {d.status}</div>) : <div className="text-xs text-[#6A8576]">No document metadata.</div>}</div></div> : <p className="text-sm text-[#6A8576]">Select a project to inspect details, quality dimensions, and documents.</p>}
        </Card>
      </div>
    </div>
  </Page>;
}
