import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import api from '../../../lib/api';
import { useAuthStore } from '../../../stores/authStore';
import { Page, Card, Btn, Field, Select, Badge } from '../Shared';

export default function SellerLandIntelligence() {
  const { user } = useAuthStore(); const actor = { actor_role:'seller', actor_id:user?.id };
  const landsQ = useQuery({ queryKey:['land',actor.actor_id], queryFn:()=>api.listLandRegistrations(actor) });
  const projectsQ = useQuery({ queryKey:['projects'], queryFn:()=>api.listProjects('user-1') }); // monitoring projects (demo)
  const [sel,setSel]=useState('');
  const [explain,setExplain]=useState(''); const [loading,setLoading]=useState(false);
  const land = (landsQ.data?.land_registrations||[]).find(l=>l.id===sel);
  const readingsQ = useQuery({ queryKey:['readings-any', projectsQ.data?.projects?.[0]?.id], queryFn:()=>api.getReadings(projectsQ.data.projects[0].id,{range:'7d'}), enabled:!!projectsQ.data?.projects?.[0]?.id });
  const ask = async () => {
    if (!land) return; setLoading(true); setExplain('');
    try {
      const pid = projectsQ.data?.projects?.[0]?.id;
      const q = `Explain this land's carbon potential and health in simple language. Use only provided context. Label estimates/simulated data clearly. Land: ${JSON.stringify({ location:`${land.village||''} ${land.state} ${land.country}`, area:`${land.land_area} ${land.area_unit}`, soil_type:land.soil_type, soil_health:land.soil_health, crop:land.current_crop, assessment:land.ai_assessment })}. Do not claim certified credits or fabricate satellite/sensor measurements.`;
      if (pid) { const r = await api.aiAsk(pid, q, []); setExplain(r.answer||r.content); } else { setExplain('AI explanation requires a configured AI provider and a project context. Assessment shown is a deterministic demonstration estimate with clearly labeled assumptions.'); }
    } catch (e) { setExplain(`AI explanation unavailable: ${e.message}`); } finally { setLoading(false); }
  };
  return <Page title="Land Intelligence" subtitle="Analyze registered land using saved map/location data and demonstration estimates. Satellite observations and sensor readings are shown only when explicitly available/sourced; estimates are not fabricated measurements.">
    <Card><Field label="Select registered land"><Select value={sel} onChange={e=>setSel(e.target.value)}><option value="">Choose land</option>{(landsQ.data?.land_registrations||[]).map(l=><option key={l.id} value={l.id}>{l.village||l.state}, {l.country} — {l.land_area} {l.area_unit}</option>)}</Select></Field></Card>
    {land && <div className="grid lg:grid-cols-2 gap-5">
      <Card><h2 className="font-bold mb-3">Map & location (declared/demo)</h2><div className="h-[260px] rounded-xl overflow-hidden border border-[#E6EEE8]"><MapContainer center={[Number(land.latitude||18.5), Number(land.longitude||73.8)]} zoom={10} style={{height:'100%',width:'100%'}}><TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"/><CircleMarker center={[Number(land.latitude||18.5), Number(land.longitude||73.8)]} radius={10} pathOptions={{color:'#0A7B4E'}}><Popup>{land.village||land.state}</Popup></CircleMarker></MapContainer></div><p className="text-xs text-[#6A8576] mt-2">Map marker uses declared GPS/demo coordinates. It is not a legal boundary verification.</p></Card>
      <Card><h2 className="font-bold mb-3">Assessment indicators</h2>
        <div className="grid grid-cols-2 gap-2 text-sm">{[['Land area',`${land.land_area} ${land.area_unit}`],['Soil health',land.soil_health||'Not provided'],['Soil moisture',land.soil_moisture||'Not provided'],['Crop',land.current_crop||'—'],['Land health score',`${land.ai_assessment?.land_health_score ?? '—'}/100 (demo est.)`],['Est. total carbon potential',`${land.ai_assessment?.estimated_total_potential_tco2e ?? '—'} tCO₂e (demo)`],['Soil carbon',`${land.ai_assessment?.estimated_soil_carbon_tco2e ?? '—'} (demo)`],['Biomass carbon',`${land.ai_assessment?.estimated_biomass_carbon_tco2e ?? '—'} (demo)`]].map(([k,v])=><div key={k} className="border border-[#EEF3EF] rounded-xl p-2"><div className="text-[11px] text-[#6A8576] font-semibold">{k}</div><div className="font-semibold">{v}</div></div>)}</div>
        <div className="mt-3"><Badge tone="amber">No satellite NDVI/sensor feed fabricated. Monitoring readings shown below only if available from connected demo project.</Badge></div>
        <div className="mt-3"><Btn onClick={ask} disabled={loading}>{loading?'Analyzing…':'Explain with AI (grounded)'}</Btn></div>
        {explain && <pre className="mt-3 whitespace-pre-wrap text-xs bg-[#FAFCFA] border border-[#E6EEE8] rounded-xl p-3">{explain}</pre>}
      </Card>
      <Card className="lg:col-span-2"><h2 className="font-bold mb-3">Environmental monitoring & recommendations</h2>
        <div className="grid md:grid-cols-2 gap-4 text-sm"><div><div className="font-semibold mb-1">Recommendations</div><ul className="list-disc pl-5 text-[#355848] space-y-1">{(land.ai_assessment?.recommendations||['Add soil test reports and field evidence.']).map((r,i)=><li key={i}>{r}</li>)}</ul></div>
        <div><div className="font-semibold mb-1">Available monitoring (demo)</div>{readingsQ.data?.readings?.length ? <div className="text-xs text-[#355848]">Latest SIMULATED reading available from monitoring project: {JSON.stringify(readingsQ.data.readings[readingsQ.data.readings.length-1]?.values||{}).slice(0,180)}… <Badge tone="amber">SIMULATED</Badge></div> : <div className="text-xs text-[#6A8576]">No connected live/simulated field reading in this view. Historical/current comparisons appear when time-series data exists.</div>}</div></div>
      </Card>
    </div>}
  </Page>;
}
