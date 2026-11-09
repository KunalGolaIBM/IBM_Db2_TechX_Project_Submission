import React, { useMemo, useState } from 'react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip } from 'recharts';
import { Radar, Sparkles, Info, AlertTriangle } from 'lucide-react';
import { useProjects, useReadings } from '../hooks/useApi';
import AiAssistantDrawer from '../components/common/AiAssistantDrawer';

export default function MonitoringPage() {
  const projectsQ = useProjects();
  const projects = projectsQ.data?.projects || [];
  const [selectedId, setSelectedId] = useState('');
  const project = projects.find((item) => item.id === selectedId) || projects[0] || null;
  const readingsQ = useReadings(project?.id, { range: '30d', enabled: Boolean(project?.id) });
  const [isAiOpen, setIsAiOpen] = useState(false);
  const readings = readingsQ.data?.readings || [];
  const chartData = useMemo(() => (readingsQ.data?.readings || [])
    .filter((reading) => Number.isFinite(reading.values?.soil_moisture_pct))
    .map((reading) => ({ time: reading.recorded_at, moisture: reading.values.soil_moisture_pct }))
    .slice(-100), [readingsQ.data]);

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div><h2 className="text-xl font-bold text-[#0E2018]">Monitoring</h2><p className="text-sm text-[#638071]">Timestamped field observations are distinct from satellite indicators and carbon-stock change.</p></div>
        <label className="text-sm text-[#526F60]">Project <select className="cn-input mt-1 sm:ml-2 sm:mt-0 sm:inline-block" value={project?.id || ''} onChange={(event) => setSelectedId(event.target.value)} disabled={!projects.length}>{projects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      </header>

      {projectsQ.isLoading && <p role="status" className="cn-card p-5">Loading saved projects…</p>}
      {projectsQ.isError && <p role="alert" className="cn-card p-5 text-red-800">Could not load projects: {projectsQ.error.message}</p>}
      {!projectsQ.isLoading && !projects.length && <p className="cn-card p-5 text-[#638071]">No saved project is available. Map and save a parcel to begin.</p>}

      {project && <>
        <section className="cn-card p-6 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="font-bold text-lg text-[#0E2018]">Field sensor observations · {project.name}</h3><p className="text-xs text-[#638071]">Last 30 days · readings are observations, not carbon-stock measurements</p></div><button onClick={() => setIsAiOpen(true)} className="btn-outline-forest text-xs"><Sparkles size={14} />Explain observations</button></div>
          {readingsQ.isLoading && <p role="status" className="text-sm text-[#638071]">Loading dated readings…</p>}
          {readingsQ.isError && <p role="alert" className="text-sm text-red-800">Could not load field data: {readingsQ.error.message}</p>}
          {!readingsQ.isLoading && !readings.length && <div className="rounded-xl border border-dashed border-[#D5E0D7] bg-[#FAFBF9] p-6 text-sm text-[#638071]">No readings are available for this project in this period. Connect a field sensor using the authenticated device ingest endpoint. Seed/demo readings, when present, are explicitly marked synthetic.</div>}
          {chartData.length > 0 && <><div className="h-64" aria-label="Soil moisture readings over time"><ResponsiveContainer width="100%" height="100%"><LineChart data={chartData}><XAxis dataKey="time" tickFormatter={(value) => new Date(value).toLocaleDateString()} minTickGap={30} /><YAxis unit="%" /><Tooltip labelFormatter={(value) => new Date(value).toLocaleString()} formatter={(value) => [`${value}%`, 'Soil moisture']} /><Line dataKey="moisture" name="Soil moisture" stroke="#0A8754" dot={false} isAnimationActive={false} /></LineChart></ResponsiveContainer></div><div className="space-y-2">{readings.slice(-8).reverse().map((reading) => <div key={reading.id} className="flex flex-wrap justify-between gap-2 rounded-lg border border-[#E3E9E3] p-3 text-xs"><span>{new Date(reading.recorded_at).toLocaleString()}</span><span>{reading.data_source}{reading.is_simulated ? ' · SIMULATED DEMO' : ''}</span><span>Soil moisture: {reading.values?.soil_moisture_pct ?? '—'}% · soil temperature: {reading.values?.soil_temp_c ?? '—'} °C</span></div>)}</div></>}
        </section>

        <section className="cn-card p-6 space-y-3"><div className="flex items-center gap-2"><AlertTriangle size={19} className="text-amber-700" /><h3 className="font-bold text-[#0E2018]">Satellite change detection unavailable</h3></div><p className="text-sm text-[#526F60]">CarbonNova has no connected dated satellite imagery, NDVI, or land-cover observation source. The static farm photos in the repository are illustrative only and are not shown as parcel evidence. No vegetation trend or carbon-stock increase is inferred.</p><p className="text-xs text-[#638071]">To start remote monitoring, configure a documented imagery/analysis provider that returns acquisition date, resolution, processing method, quality flags, and missing-data status.</p></section>

        <section className="cn-card p-4 flex items-start gap-3 text-xs text-[#526F60]"><Info size={17} className="mt-0.5 shrink-0 text-[#0A7B4E]" /><p>Soil respiration, vegetation greenness, estimated carbon stock, stock change, additional sequestration, independently verified reductions, and issued/retired credits are different concepts. This page only graphs stored field sensor observations.</p></section>
      </>}
      <AiAssistantDrawer isOpen={isAiOpen} onClose={() => setIsAiOpen(false)} activeProject={project} />
    </div>
  );
}
