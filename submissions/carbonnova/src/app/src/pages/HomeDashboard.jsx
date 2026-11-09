import React from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import {
  Leaf,
  BarChart3,
  ShieldCheck,
  Globe,
  ArrowRight,
  MapPin,
  TrendingUp,
  Radar,
  Layers,
  FileText,
  AlertCircle,
  CheckCircle2,
  Clock,
} from 'lucide-react';
import { useProjects, useActivity } from '../hooks/useApi';

export const HomeDashboard = () => {
  const { revealSidebar, setSidebarVisible } = useOutletContext() || {};
  const projectsQ = useProjects();
  const activityQ = useActivity(6);

  const projects = projectsQ.data?.projects || [];
  const activities = activityQ.data?.activity || [];

  const totalHa = projects.reduce((acc, p) => acc + (p.area_hectares || (p.area_acres ? p.area_acres * 0.404686 : 0)), 0);
  const activeCount = projects.filter((p) => p.status === 'active').length;
  const metrics = [
    { label: 'Monitored land', value: projectsQ.isLoading ? 'Loading…' : projectsQ.isError ? 'Unavailable' : totalHa ? totalHa.toFixed(1) : '0', unit: 'hectares', note: `${projects.length} saved projects`, icon: Leaf },
    { label: 'Estimated carbon stock', value: '—', unit: 'tCO₂e', note: 'Open Carbon Estimates for a project result', icon: BarChart3 },
    { label: 'Sequestration model', value: '—', unit: 'tCO₂e/year', note: 'Not aggregated across projects', icon: TrendingUp },
    { label: 'Active projects', value: projectsQ.isLoading ? 'Loading…' : projectsQ.isError ? 'Unavailable' : String(activeCount), unit: 'in pipeline', note: `${projects.length} saved projects`, icon: Layers },
  ];

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* 1. HERO SHOWCASE - EXACT MATCH TO REFERENCE IMAGE (Top Left) */}
      <div className="relative rounded-3xl overflow-hidden shadow-xl border border-[#D5E2D7] min-h-[460px] flex items-center bg-[#072418]">
        {/* Background Aerial Photograph */}
        <img
          src="/hero-landscape.jpg"
          alt="CarbonNova Agricultural Landscape"
          className="absolute inset-0 w-full h-full object-cover object-center opacity-85"
        />

        {/* Soft Radial & Linear Atmospheric Green Gradient */}
        <div className="absolute inset-0 bg-gradient-to-r from-[#072218]/95 via-[#08291D]/80 to-transparent lg:to-[#08291D]/20" />

        {/* Hero Content Container */}
        <div className="relative z-10 w-full p-8 md:p-12 lg:p-16 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-10">
          
          {/* Left Column: Copy & Value Proposition */}
          <div className="max-w-2xl text-white space-y-6">
            {/* Brand Logo in Hero */}
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-white/10 backdrop-blur-md border border-white/20 flex items-center justify-center p-2">
                <svg viewBox="0 0 40 40" fill="none" className="w-full h-full">
                  <path d="M36 6C22 6 8 16 8 30C8 35.5 12.5 38 18 38C32 38 38 24 38 10C38 7.8 37.2 6 36 6Z" fill="#34D399" />
                  <path d="M14 34C14 26 22 18 34 10C24 14 18 20 14 34Z" fill="#0C3327" />
                </svg>
              </div>
              <span className="text-2xl font-bold tracking-tight">CarbonNova</span>
            </div>

            {/* Main Headline */}
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight leading-[1.15] text-white">
              AI-Powered Carbon Intelligence <br />
              <span className="text-[#6EE7B7]">for a Greener Future.</span>
            </h1>

            {/* Description */}
            <p className="text-sm sm:text-base text-[#D1E7DC] font-normal leading-relaxed max-w-xl">
              We help farmers and landowners map agricultural land, organize environmental evidence, and understand transparent carbon indicators with AI-assisted interpretation.
            </p>

            {/* 4 Feature Tags with Icons */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-2">
              <div className="flex items-center gap-2.5 text-xs text-[#E1F3EA] font-medium">
                <div className="w-7 h-7 rounded-lg bg-white/10 border border-white/15 flex items-center justify-center shrink-0 text-[#34D399]">
                  <Leaf size={15} />
                </div>
                <span>Parcel mapping</span>
              </div>

              <div className="flex items-center gap-2.5 text-xs text-[#E1F3EA] font-medium">
                <div className="w-7 h-7 rounded-lg bg-white/10 border border-white/15 flex items-center justify-center shrink-0 text-[#34D399]">
                  <BarChart3 size={15} />
                </div>
                <span>Deterministic indicators</span>
              </div>

              <div className="flex items-center gap-2.5 text-xs text-[#E1F3EA] font-medium">
                <div className="w-7 h-7 rounded-lg bg-white/10 border border-white/15 flex items-center justify-center shrink-0 text-[#34D399]">
                  <ShieldCheck size={15} />
                </div>
                <span>Evidence ledger</span>
              </div>

              <div className="flex items-center gap-2.5 text-xs text-[#E1F3EA] font-medium">
                <div className="w-7 h-7 rounded-lg bg-white/10 border border-white/15 flex items-center justify-center shrink-0 text-[#34D399]">
                  <Globe size={15} />
                </div>
                <span>AI explanations</span>
              </div>
            </div>

            {/* CTA Button */}
            <div className="pt-2">
              <Link
                to="/role-select"
                className="inline-flex items-center gap-3 bg-[#0C3327] hover:bg-[#124C3A] text-white font-semibold text-sm px-7 py-3.5 rounded-full border border-[#2D6A44] shadow-lg shadow-black/20 hover:shadow-emerald-950/40 transition-all active:scale-98 cursor-pointer"
              >
                <span>A Greener Future Starts Here</span>
                <ArrowRight size={17} className="text-[#34D399]" />
              </Link>
            </div>
          </div>

          {/* Right Floating Badge Pin on Landscape (matching image) */}
          <div className="hidden lg:flex flex-col items-center justify-center relative p-6">
            {/* Faux Polygon Glow Area on image */}
            <div className="relative w-72 h-52 border-2 border-[#34D399]/80 bg-[#10B981]/20 backdrop-blur-[2px] rounded-2xl flex items-center justify-center shadow-glow">
              {/* Central Map Pin */}
              <div className="flex flex-col items-center">
                <div className="w-8 h-8 rounded-full bg-white text-[#0C3327] flex items-center justify-center shadow-lg border-2 border-[#10B981] animate-bounce">
                  <MapPin size={18} />
                </div>
              </div>

              {/* Carbon Potential Tag */}
              <div className="absolute -top-5 bg-[#0C2D20]/90 backdrop-blur-md text-white border border-[#34D399]/40 px-4 py-2 rounded-xl shadow-xl flex flex-col items-center">
                <span className="text-[10px] text-[#A7F3D0] uppercase font-semibold tracking-wider">
                  Interactive farm map
                </span>
                <span className="text-base font-extrabold text-white">
                  User-mapped boundaries
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 2. OVERVIEW KPI CARDS */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {metrics.map((metric) => {
          const Icon = metric.icon;
          return <div key={metric.label} className="cn-card p-6 flex flex-col justify-between">
          <div className="flex items-center justify-between mb-3"><span className="text-xs font-semibold text-[#5B7767] uppercase tracking-wider">{metric.label}</span><div className="w-9 h-9 rounded-xl bg-[#E8F7F0] text-[#0A7B4E] flex items-center justify-center"><Icon size={18} /></div></div>
          <div><div className="flex items-baseline gap-2"><span className="text-3xl font-extrabold text-[#0E2018]">{metric.value}</span><span className="text-sm font-medium text-[#5B7767]">{metric.unit}</span></div><p className="text-xs text-[#6A8576] mt-1.5">{metric.note}</p></div>
        </div>;
        })}
      </div>



      {/* 3. QUICK SHORTCUTS & RECENT LAND ACTIVITY */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Quick Launch Cards (2 Cols) */}
        <div className="lg:col-span-2 space-y-6">
          <div className="cn-card p-6">
            <div className="flex items-center justify-between mb-5">
              <div>
                <h3 className="font-bold text-lg text-[#0E2018]">Platform Quick Actions</h3>
                <p className="text-xs text-[#658172]">Direct access to core carbon intelligence tools</p>
              </div>
              <Link to="/land-analysis" className="text-xs font-semibold text-[#0C3327] hover:underline flex items-center gap-1">
                Explore Maps <ArrowRight size={13} />
              </Link>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Link
                to="/land-analysis"
                className="group p-5 rounded-2xl border border-[#E3E9E3] hover:border-[#10B981] bg-[#FAFBF9] hover:bg-white hover:shadow-card transition-all"
              >
                <div className="w-10 h-10 rounded-xl bg-[#0C3327] text-white flex items-center justify-center mb-3 group-hover:scale-105 transition-transform">
                  <MapPin size={20} />
                </div>
                <h4 className="font-bold text-[#0E2018] group-hover:text-[#0C3327] text-base mb-1">
                  Land Analysis & Mapping
                </h4>
                <p className="text-xs text-[#617E6F] leading-relaxed">
                  Draw and save geospatial parcel outlines over imagery; environmental observations remain unavailable until sourced.
                </p>
              </Link>

              <Link
                to="/carbon-estimates"
                className="group p-5 rounded-2xl border border-[#E3E9E3] hover:border-[#10B981] bg-[#FAFBF9] hover:bg-white hover:shadow-card transition-all"
              >
                <div className="w-10 h-10 rounded-xl bg-[#0C3327] text-white flex items-center justify-center mb-3 group-hover:scale-105 transition-transform">
                  <BarChart3 size={20} />
                </div>
                <h4 className="font-bold text-[#0E2018] group-hover:text-[#0C3327] text-base mb-1">
                  Carbon Estimates
                </h4>
                <p className="text-xs text-[#617E6F] leading-relaxed">
                  Review separately labelled stock, respiration, and indicative annual model outputs with source data and limitations.
                </p>
              </Link>

              <Link
                to="/monitoring"
                className="group p-5 rounded-2xl border border-[#E3E9E3] hover:border-[#10B981] bg-[#FAFBF9] hover:bg-white hover:shadow-card transition-all"
              >
                <div className="w-10 h-10 rounded-xl bg-[#0C3327] text-white flex items-center justify-center mb-3 group-hover:scale-105 transition-transform">
                  <Radar size={20} />
                </div>
                <h4 className="font-bold text-[#0E2018] group-hover:text-[#0C3327] text-base mb-1">
                  Change Detection & Monitoring
                </h4>
                <p className="text-xs text-[#617E6F] leading-relaxed">
                  Inspect available saved field readings. Satellite time-series, NDVI, and change-detection data are not connected.
                </p>
              </Link>

              <Link
                to="/carbon-credits"
                className="group p-5 rounded-2xl border border-[#E3E9E3] hover:border-[#10B981] bg-[#FAFBF9] hover:bg-white hover:shadow-card transition-all"
              >
                <div className="w-10 h-10 rounded-xl bg-[#0C3327] text-white flex items-center justify-center mb-3 group-hover:scale-105 transition-transform">
                  <ShieldCheck size={20} />
                </div>
                <h4 className="font-bold text-[#0E2018] group-hover:text-[#0C3327] text-base mb-1">
                  Carbon Credits & dMRV
                </h4>
                <p className="text-xs text-[#617E6F] leading-relaxed">
                  Organize evidence for project preparation. No automated validation, registry, or credit issuance is available.
                </p>
              </Link>
            </div>
          </div>
        </div>

        {/* Recent Monitoring Activity (1 Col) */}
        <div className="cn-card p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-4 border-b border-[#EBF0EC] mb-4">
              <h3 className="font-bold text-base text-[#0E2018]">Recent Activity</h3>
              <span className="text-[10px] font-semibold uppercase tracking-wider text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded-full">
                Audit Trail
              </span>
            </div>

            <div className="space-y-4">
              {activities.length > 0 ? (
                activities.slice(0, 5).map((act, i) => (
                  <div key={i} className="flex items-start gap-3">
                    <div className="w-7 h-7 rounded-lg bg-[#EBF5EF] text-[#0A7B4E] flex items-center justify-center shrink-0 mt-0.5">
                      <Clock size={14} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-semibold text-[#183528] leading-tight">
                        {act.message}
                      </p>
                      <p className="text-[11px] text-[#738D7F] mt-0.5">
                        {new Date(act.at).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })} · {act.source}
                      </p>
                    </div>
                  </div>
                ))
              ) : (
                <>
                  <div className="flex items-start gap-3">
                    <div className="w-7 h-7 rounded-lg bg-[#E8F7F0] text-[#0A7B4E] flex items-center justify-center shrink-0 mt-0.5">
                      <CheckCircle2 size={14} />
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-[#183528]">Vegetation growth detected</p>
                      <p className="text-[11px] text-[#738D7F]">Jun 10, 2025 · Sentinel-2 Analysis</p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3">
                    <div className="w-7 h-7 rounded-lg bg-[#E8F7F0] text-[#0A7B4E] flex items-center justify-center shrink-0 mt-0.5">
                      <TrendingUp size={14} />
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-[#183528]">Soil carbon increase (+4.2%)</p>
                      <p className="text-[11px] text-[#738D7F]">May 28, 2025 · IPCC Tier 2 Run</p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3">
                    <div className="w-7 h-7 rounded-lg bg-[#FEF6E6] text-[#B45309] flex items-center justify-center shrink-0 mt-0.5">
                      <AlertCircle size={14} />
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-[#183528]">Land use change (minor clearing)</p>
                      <p className="text-[11px] text-[#738D7F]">May 12, 2025 · Alert Reviewed</p>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>

          <div className="pt-4 border-t border-[#EBF0EC] mt-6">
            <Link
              to="/reports"
              className="text-xs font-semibold text-[#0C3327] hover:underline flex items-center justify-center gap-1.5 py-2 rounded-xl bg-[#F4F7F4] hover:bg-[#EAF1EB] transition-colors"
            >
              <FileText size={14} /> View All Activity Reports
            </Link>
          </div>
        </div>

      </div>
    </div>
  );
};

export default HomeDashboard;
