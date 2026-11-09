import React from 'react';
import { Link } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';
import {
  useProjects, useActivity, useDevices, useAiStatus,
} from '../../hooks/useApi';
import api from '../../lib/api';
import { useQueries } from '@tanstack/react-query';
import {
  Leaf, MapPin, Cpu, TrendingUp, Activity, ArrowRight, Droplets,
  Thermometer, FlaskConical, Gauge, Sparkles, AlertTriangle, CheckCircle2,
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer, Cell } from 'recharts';
import { Loading, ErrorState, EmptyState } from '../../components/monitoring/StateBlocks';
import { SimulatedBadge, SourceBadge } from '../../components/monitoring/SourceBadges';

const StatCard = ({ icon: Icon, color = 'text-carbon-400', bg = 'bg-carbon-900/50', label, value, unit, sub }) => (
  <div className="stat-card">
    <div className={`flex items-center gap-3 mb-1 ${color}`}>
      <div className={`p-2 ${bg} rounded-lg`}><Icon size={18} /></div>
      <span className="font-medium text-sm">{label}</span>
    </div>
    <h3 className="text-3xl font-bold text-white">
      {value} {unit && <span className="text-sm font-normal text-gray-500">{unit}</span>}
    </h3>
    {sub && <p className="text-xs text-gray-500 mt-1">{sub}</p>}
  </div>
);

const fmtTime = (iso) => (iso ? new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—');

const SellerDashboard = () => {
  const { user } = useAuthStore();
  const projectsQ = useProjects();
  const devicesQ = useDevices();
  const activityQ = useActivity(8);
  const aiStatusQ = useAiStatus();

  const projects = projectsQ.data?.projects || [];

  // Carbon estimates for every project (science layer, via backend engine)
  const carbonQueries = useQueries({
    queries: projects.map((p) => ({
      queryKey: ['carbon', p.id, '7d'],
      queryFn: () => api.getCarbon(p.id, '7d'),
      staleTime: 60000,
      enabled: projectsQ.isSuccess,
    })),
  });
  const carbonLoading = carbonQueries.some((q) => q.isLoading);
  const carbonByProject = Object.fromEntries(
    projects.map((p, i) => [p.id, carbonQueries[i]?.data]).filter(([, v]) => v)
  );

  const totalAreaAcres = projects.reduce((s, p) => s + (p.area_acres || 0), 0);
  const totalAreaHa = projects.reduce((s, p) => s + (p.area_hectares || 0), 0);
  const activeProjects = projects.filter((p) => p.status === 'active').length;
  const devices = devicesQ.data?.devices || [];
  const onlineDevices = devices.filter((d) => d.is_active !== false).length;
  const readings24h = projects.reduce((s, p) => s + (p.readings_last_24h || 0), 0);

  const seqTotals = Object.values(carbonByProject).reduce(
    (acc, c) => ({
      net: acc.net + (c.estimate.metrics.net_sequestration_project_tCO2e_yr || 0),
      low: acc.low + (c.estimate.metrics.net_sequestration_uncertainty.low || 0),
      high: acc.high + (c.estimate.metrics.net_sequestration_uncertainty.high || 0),
      pct: c.estimate.metrics.net_sequestration_uncertainty.pct || 0,
    }),
    { net: 0, low: 0, high: 0, pct: 0 }
  );

  const chartData = projects.map((p) => {
    const est = carbonByProject[p.id]?.estimate;
    return {
      name: p.name.length > 18 ? p.name.slice(0, 17) + '…' : p.name,
      net: est?.metrics.net_sequestration_project_tCO2e_yr ?? 0,
      resp: est?.metrics.soil_respiration_project_tCO2e_yr ?? 0,
      full: p.name,
    };
  });

  const hasData = projectsQ.isSuccess && projects.length > 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="mb-2 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">
            Welcome back, {user?.full_name?.split(' ')[0] || 'farmer'}
          </h1>
          <p className="text-gray-400">Monitoring overview — land, soil parameters, sensors and indicative carbon trends.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold px-2.5 py-1.5 rounded-full bg-amber-400/10 border border-amber-400/30 text-amber-300">
            <AlertTriangle size={12} /> Demo mode · sensor data simulated
          </span>
          <span className={`inline-flex items-center gap-1.5 text-[11px] font-semibold px-2.5 py-1.5 rounded-full border ${
            aiStatusQ.data?.configured
              ? 'bg-violet-400/10 border-violet-400/30 text-violet-300'
              : 'bg-dark-700 border-carbon-800 text-gray-400'
          }`}>
            <Sparkles size={12} /> AI {aiStatusQ.data?.configured ? 'connected (Nemotron)' : 'not configured'}
          </span>
        </div>
      </div>

      {projectsQ.isLoading && <Loading label="Loading monitoring projects…" />}
      <ErrorState error={projectsQ.error} onRetry={projectsQ.refetch} label="Failed to load projects" />

      {projectsQ.isSuccess && projects.length === 0 && (
        <EmptyState
          icon={MapPin}
          title="No monitoring projects yet"
          description="Create your first land & monitoring project to start tracking soil parameters, sensors and indicative carbon estimates."
          action="Create a project"
          onAction={() => { window.location.href = '/seller/projects'; }}
        />
      )}

      {hasData && (
        <>
          {/* KPI row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            <StatCard
              icon={Leaf} label="Monitored Land"
              value={totalAreaHa.toLocaleString(undefined, { maximumFractionDigits: 1 })}
              unit="ha" sub={`${projects.length} projects (${activeProjects} active) · ${totalAreaAcres.toLocaleString()} acres`}
            />
            <StatCard
              icon={TrendingUp} color="text-emerald-400" bg="bg-emerald-900/30"
              label="Est. Net Sequestration" value={seqTotals.net.toFixed(1)} unit="tCO₂e/yr"
              sub={carbonLoading ? 'calculating…' : `indicative · range ${seqTotals.low.toFixed(0)}–${seqTotals.high.toFixed(0)} ±${seqTotals.pct}% · not verified credits`}
            />
            <StatCard
              icon={Cpu} color="text-blue-400" bg="bg-blue-900/30"
              label="Sensors" value={`${onlineDevices}/${devices.length}`} unit="online"
              sub={`simulated nodes · ${readings24h} readings in last 24h`}
            />
            <StatCard
              icon={Activity} color="text-amber-400" bg="bg-amber-900/20"
              label="Recent Activity" value={activityQ.data?.activity?.length ?? '—'} unit="events"
              sub="timestamped audit trail"
            />
          </div>

          <div className="grid lg:grid-cols-3 gap-6">
            {/* Estimated carbon trends (indicative) */}
            <div className="lg:col-span-2 glass-card p-6">
              <div className="flex items-center justify-between mb-1">
                <h3 className="font-bold text-white">Estimated Carbon Trends (indicative)</h3>
                <Link to="/seller/projects" className="text-xs text-carbon-400 hover:text-carbon-300 flex items-center gap-1">
                  Manage projects <ArrowRight size={12} />
                </Link>
              </div>
              <p className="text-xs text-gray-500 mb-4">
                Deterministic engine estimates — separate from AI. Bars show indicative annual net sequestration vs. soil respiration (a carbon <em>loss</em> flux).
              </p>
              {carbonLoading && <Loading label="Running carbon engine…" className="py-8" />}
              {!carbonLoading && (
                <div className="h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData} margin={{ top: 4, right: 8, left: -8, bottom: 0 }} barGap={4}>
                      <XAxis dataKey="name" stroke="#374151" fontSize={11} tickLine={false} axisLine={false} />
                      <YAxis stroke="#374151" fontSize={11} tickLine={false} axisLine={false} />
                      <RechartsTooltip
                        contentStyle={{ backgroundColor: '#071a10', borderColor: '#1d3025', borderRadius: '12px', color: '#fff', fontSize: 12 }}
                        formatter={(v, name) => [`${v} tCO₂e/yr`, name === 'net' ? 'Net sequestration (est.)' : 'Soil respiration (loss)']}
                        labelFormatter={(label, payload) => payload?.[0]?.payload?.full || label}
                      />
                      <Bar dataKey="net" name="net" radius={[6, 6, 0, 0]} isAnimationActive={false}>
                        {chartData.map((_, i) => <Cell key={i} fill="#14b178" />)}
                      </Bar>
                      <Bar dataKey="resp" name="resp" radius={[6, 6, 0, 0]} isAnimationActive={false}>
                        {chartData.map((_, i) => <Cell key={i} fill="#f59e0b" />)}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
              <p className="text-[11px] text-gray-500 mt-3">
                Estimates use default SOC parameters (no lab data) — see each project’s Carbon tab for formulas, assumptions & uncertainty.
              </p>
            </div>

            {/* Sensor status */}
            <div className="glass-card">
              <div className="px-6 py-4 border-b border-carbon-800/50 flex items-center justify-between">
                <h3 className="font-bold text-white">Sensor Status</h3>
                <Link to="/seller/monitoring" className="text-xs text-carbon-400 hover:text-carbon-300">View all</Link>
              </div>
              <div className="divide-y divide-carbon-800/30">
                {devicesQ.isLoading && <Loading label="Loading devices…" className="py-8" />}
                {devicesQ.error && <div className="p-4"><ErrorState error={devicesQ.error} onRetry={devicesQ.refetch} compact /></div>}
                {devices.map((d) => (
                  <div key={d.id} className="px-5 py-3.5 flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-200 truncate flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full shrink-0 ${d.is_active !== false && d.battery_pct > 15 ? 'bg-emerald-400' : 'bg-amber-500'}`} />
                        {d.name}
                      </p>
                      <p className="text-xs text-gray-500 truncate">{d.project_name} · {fmtTime(d.last_reading_at)}</p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="text-xs font-semibold text-gray-300">{d.battery_pct}%</p>
                      <p className="text-[10px] text-gray-500">{d.reading_count} readings</p>
                    </div>
                  </div>
                ))}
                {devicesQ.isSuccess && devices.length === 0 && (
                  <p className="p-6 text-sm text-gray-500 text-center">No sensors registered.</p>
                )}
              </div>
            </div>
          </div>

          {/* Project overview */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-white">Project Overview</h3>
              <Link to="/seller/projects" className="text-xs text-carbon-400 hover:text-carbon-300 flex items-center gap-1">
                Land & project management <ArrowRight size={12} />
              </Link>
            </div>
            <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-6">
              {projects.map((p) => {
                const lr = p.latest_reading;
                return (
                  <Link
                    key={p.id}
                    to={`/seller/projects/${p.id}`}
                    className="glass-card-hover p-5 flex flex-col gap-3 group"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <h4 className="font-bold text-white truncate group-hover:text-carbon-300 transition-colors">{p.name}</h4>
                        <p className="text-xs text-gray-500 flex items-center gap-1 mt-0.5">
                          <MapPin size={11} /> {p.location || 'Location not set'}
                        </p>
                      </div>
                      <span className={`text-[10px] font-bold uppercase px-2 py-1 rounded-md border shrink-0 ${
                        p.status === 'active'
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                          : 'bg-slate-500/10 text-slate-400 border-slate-500/30'
                      }`}>{p.status}</span>
                    </div>

                    <div className="flex items-center gap-3 text-xs text-gray-400">
                      <span className="bg-dark-900/60 px-2 py-1 rounded-md border border-carbon-800/40 capitalize">{p.land_type}</span>
                      <span className="bg-dark-900/60 px-2 py-1 rounded-md border border-carbon-800/40">{p.area_hectares} ha · {p.area_acres} ac</span>
                      {lr && <SourceBadge readings={[lr]} small />}
                    </div>

                    {lr ? (
                      <div className="grid grid-cols-3 gap-2 text-center">
                        <div className="bg-dark-900/50 rounded-lg py-2 border border-carbon-800/30">
                          <p className="text-[10px] text-gray-500 flex items-center justify-center gap-1"><Droplets size={9} /> Moisture</p>
                          <p className="text-sm font-semibold text-gray-200">{lr.values.soil_moisture_pct}%</p>
                        </div>
                        <div className="bg-dark-900/50 rounded-lg py-2 border border-carbon-800/30">
                          <p className="text-[10px] text-gray-500 flex items-center justify-center gap-1"><Thermometer size={9} /> Soil T</p>
                          <p className="text-sm font-semibold text-gray-200">{lr.values.soil_temp_c}°C</p>
                        </div>
                        <div className="bg-dark-900/50 rounded-lg py-2 border border-carbon-800/30">
                          <p className="text-[10px] text-gray-500 flex items-center justify-center gap-1"><FlaskConical size={9} /> CO₂</p>
                          <p className="text-sm font-semibold text-gray-200">{lr.values.soil_co2_respiration}</p>
                        </div>
                      </div>
                    ) : (
                      <p className="text-xs text-gray-500 bg-dark-900/50 rounded-lg py-3 border border-carbon-800/30 text-center">
                        No readings yet — sensor not reporting
                      </p>
                    )}
                    <p className="text-[11px] text-gray-600">Last reading: {fmtTime(p.last_reading_at)}</p>
                  </Link>
                );
              })}
            </div>
          </div>

          {/* Activity + AI shortcuts */}
          <div className="grid lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 glass-card">
              <div className="px-6 py-4 border-b border-carbon-800/50 flex items-center justify-between">
                <h3 className="font-bold text-white flex items-center gap-2"><Activity size={16} className="text-carbon-400" /> Recent Activity</h3>
                <span className="text-[10px] text-gray-500 uppercase tracking-wider">Audit trail</span>
              </div>
              <div className="divide-y divide-carbon-800/20 max-h-72 overflow-y-auto styled-scrollbar">
                {activityQ.isLoading && <Loading label="Loading activity…" className="py-8" />}
                {activityQ.error && <div className="p-4"><ErrorState error={activityQ.error} onRetry={activityQ.refetch} compact /></div>}
                {activityQ.data?.activity?.map((a) => (
                  <div key={a.id} className="px-6 py-3 flex items-start gap-3">
                    <div className={`mt-0.5 w-2 h-2 rounded-full shrink-0 ${
                      a.severity === 'warning' ? 'bg-amber-400' : a.source === 'nebius-ai' ? 'bg-violet-400' : a.source === 'device' ? 'bg-emerald-400' : 'bg-carbon-500'
                    }`} />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm text-gray-300 leading-snug">{a.message}</p>
                      <p className="text-[11px] text-gray-600 mt-0.5">{fmtTime(a.at)} · <span className="uppercase tracking-wide">{a.source}</span></p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="glass-card p-6 flex flex-col gap-4">
              <h3 className="font-bold text-white">Quick Actions</h3>
              <Link to="/seller/monitoring" className="btn-secondary flex items-center justify-between text-sm py-3">
                <span className="flex items-center gap-2"><Cpu size={16} /> IoT Monitoring</span> <ArrowRight size={14} />
              </Link>
              <Link to="/seller/assistant" className="btn-secondary flex items-center justify-between text-sm py-3">
                <span className="flex items-center gap-2"><Sparkles size={16} /> AI Carbon Assistant</span> <ArrowRight size={14} />
              </Link>
              <Link to="/seller/reports" className="btn-secondary flex items-center justify-between text-sm py-3">
                <span className="flex items-center gap-2"><Gauge size={16} /> Generate MRV Report</span> <ArrowRight size={14} />
              </Link>
              <div className="mt-auto pt-4 border-t border-carbon-800/40 text-[11px] text-gray-500 flex items-start gap-2">
                <CheckCircle2 size={13} className="text-carbon-500 shrink-0 mt-0.5" />
                <span>All readings on this dashboard are SIMULATED demo data. Estimates are indicative and not verified carbon credits.</span>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default SellerDashboard;
