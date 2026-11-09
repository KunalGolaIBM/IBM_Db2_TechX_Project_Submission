import React, { useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useMarketDataStore } from '../stores/marketStore';
import { mockProjects, mockDevices, generatePriceHistory } from '../lib/mockData';
import { useAuthStore } from '../stores/authStore';
import { 
  ArrowLeft, FileText, Calendar, Sprout, Wind, MapPin, 
  Leaf, Info, ShoppingCart, ShieldCheck, Flame, ChevronRight, Activity 
} from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer } from 'recharts';

import LiveQualityBadge from '../components/marketplace/LiveQualityBadge';
import QualityScoreGauge from '../components/marketplace/QualityScoreGauge';
import SensorSparkline from '../components/marketplace/SensorSparkline';
import ProjectMap from '../components/marketplace/ProjectMap';

const ListingDetail = () => {
  const { id } = useParams();
  const { listings, sensorReadings, history } = useMarketDataStore();
  const { isAuthenticated } = useAuthStore();

  const listing = useMemo(() => listings.find(l => l.id === id), [listings, id]);
  const project = useMemo(() => mockProjects.find(p => p.id === listing?.project_id), [listing]);
  const devices = useMemo(() => mockDevices.filter(d => d.project_id === project?.id), [project]);
  
  // Use first device corresponding to this project for reading display, simplified
  const displayDevice = devices?.[0];
  const liveReading = sensorReadings[displayDevice?.id];
  const deviceHistory = history[displayDevice?.id];

  // Memoize price history so it doesn't regenerate on tick
  const priceHistory = useMemo(() => {
    if (!listing) return [];
    return generatePriceHistory(listing.price_per_tonne, 30);
  }, [listing?.id, listing?.price_per_tonne]);

  if (!listing || !project) {
    return (
      <div className="min-h-screen pt-32 pb-12 flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-white mb-2">Listing not found</h2>
          <Link to="/marketplace" className="text-carbon-400 hover:text-carbon-300">Return to Marketplace</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen pt-24 pb-24">
      <div className="container mx-auto px-6">
        
        {/* Breadcrumb & Intro */}
        <div className="mb-8">
          <div className="flex items-center gap-2 text-sm text-gray-500 mb-6">
            <Link to="/marketplace" className="hover:text-gray-300 flex items-center gap-1">
              <ArrowLeft size={14} /> Marketplace
            </Link>
            <ChevronRight size={14} />
            <span className="capitalize">{listing.type}</span>
            <ChevronRight size={14} />
            <span className="text-gray-300 truncate max-w-[200px]">{listing.project_name}</span>
          </div>

          <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-6">
            <div>
              <div className="flex items-center gap-3 mb-3 relative z-10">
                <LiveQualityBadge score={listing.quality_score} tier={listing.quality_tier} lastUpdate={listing.last_score_update} />
                <span className="px-3 py-1 bg-dark-800 border border-carbon-800 rounded-full text-xs font-semibold text-gray-400 uppercase tracking-widest">
                  Verified by {listing.methodology}
                </span>
                {listing.blockchain_hash && (
                  <a href="#" className="hidden sm:flex items-center gap-1.5 px-3 py-1 bg-carbon-900/30 border border-carbon-500/20 text-carbon-400 rounded-full text-xs hover:bg-carbon-900/50 transition-colors">
                    <ShieldCheck size={14} />
                    On-chain
                  </a>
                )}
              </div>
              <h1 className="text-3xl lg:text-5xl font-bold text-white mb-4 tracking-tight leading-tight max-w-3xl">
                {listing.project_name}
              </h1>
              <div className="flex flex-wrap items-center gap-4 text-sm text-gray-400">
                <span className="flex items-center gap-1.5"><MapPin size={16} /> {listing.location_state}, {listing.location_district}</span>
                <span className="flex items-center gap-1.5"><Calendar size={16} /> Vintage {listing.vintage_year}</span>
                <span className="flex items-center gap-1.5"><FileText size={16} /> ID: {listing.id.toUpperCase()}</span>
              </div>
            </div>

            {/* Price Buy Card (Desktop Top-Right align) */}
            <div className="glass-card p-6 min-w-[320px] shrink-0">
               <div className="flex justify-between items-start mb-4">
                 <p className="text-gray-400 text-sm">Live Carbon Price</p>
                 <span className="flex items-center gap-1 text-xs text-emerald-400 bg-emerald-400/10 px-2 py-0.5 rounded border border-emerald-400/20">
                   <Activity size={12} /> Auto-adjusting
                 </span>
               </div>
               <div className="flex items-end gap-2 mb-6">
                 <h2 className="text-4xl font-bold text-white">₹{listing.price_per_tonne.toLocaleString()}</h2>
                 <span className="text-gray-500 mb-1">/ tonne</span>
               </div>
               
               <div className="flex justify-between items-center text-sm mb-6 pb-6 border-b border-carbon-800/50">
                 <span className="text-gray-400">Available:</span>
                 <span className="font-semibold text-gray-200">{listing.quantity_available.toLocaleString()} tonnes</span>
               </div>

               <button className="w-full btn-primary flex items-center justify-center gap-2 py-3 text-lg">
                 <ShoppingCart size={20} />
                 {isAuthenticated ? 'Buy Credits' : 'Log in to Buy'}
               </button>
            </div>
          </div>
        </div>

        <div className="grid lg:grid-cols-3 gap-8">
          
          {/* Main Left Column */}
          <div className="lg:col-span-2 space-y-8">
            
            {/* Live dMRV Sensor Dashboard */}
            <div className="glass-card overflow-hidden">
               <div className="px-6 py-5 border-b border-carbon-800/50 bg-dark-800/30 flex justify-between items-center">
                 <div>
                   <h3 className="text-lg font-bold text-white flex items-center gap-2">
                     <Activity className="text-carbon-400" /> Live dMRV Sensor Data
                   </h3>
                   <p className="text-xs text-gray-500 mt-1">Direct telemetry from Field Unit {displayDevice?.id.toUpperCase()}</p>
                 </div>
                 <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-carbon-900 border border-carbon-800 text-xs">
                   <span className="live-dot" /> Live sync
                 </div>
               </div>
               
               <div className="p-6 grid sm:grid-cols-2 gap-4">
                 {liveReading && deviceHistory ? (
                   <>
                     <SensorSparkline 
                       label="Ambient CO₂" value={liveReading.co2_ppm} unit="ppm" color="#10b981" 
                       data={deviceHistory.co2} dataKey="co2" isPositiveGood={false}
                     />
                     <SensorSparkline 
                       label="Soil Moisture" value={liveReading.soil_moisture_pct} unit="%" color="#3b82f6" 
                       data={deviceHistory.soil} dataKey="soil"
                     />
                     <SensorSparkline 
                       label="PM2.5 / Air Quality" value={liveReading.pm25} unit="µg/m³" color="#f59e0b" 
                       data={deviceHistory.pm25} dataKey="pm25" isPositiveGood={false}
                     />
                     <SensorSparkline 
                       label="Humidity" value={liveReading.humidity_pct} unit="%" color="#0ea5e9" 
                       data={deviceHistory.humidity} dataKey="humidity"
                     />
                   </>
                 ) : (
                    <div className="col-span-2 py-12 text-center text-gray-500">Connecting to sensors...</div>
                 )}
               </div>
            </div>

            {/* About Project & Map */}
            <div className="glass-card p-6">
              <h3 className="text-lg font-bold text-white mb-4">Project Description</h3>
              <p className="text-gray-300 leading-relaxed mb-8">{project.description}</p>
              
              <h3 className="text-lg font-bold text-white mb-4">Verification Boundary</h3>
              <div className="h-80 w-full rounded-xl overflow-hidden mb-4">
                 <ProjectMap project={project} devices={devices} />
              </div>
              <p className="text-xs text-gray-500">Map shows exact bounding box registered with methodology standard.</p>
            </div>

            {/* Price History */}
            <div className="glass-card p-6">
               <h3 className="text-lg font-bold text-white mb-6">30-Day Price Trend</h3>
               <div className="h-64 mt-4">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={priceHistory}>
                      <defs>
                        <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <XAxis dataKey="date" stroke="#374151" fontSize={12} tickLine={false} axisLine={false} />
                      <YAxis stroke="#374151" fontSize={12} tickLine={false} axisLine={false} tickFormatter={val => `₹${val}`} />
                      <RechartsTooltip 
                        contentStyle={{ backgroundColor: '#030d08', borderColor: '#1d3025', borderRadius: '12px', color: '#fff' }}
                        itemStyle={{ color: '#10b981', fontWeight: 'bold' }}
                      />
                      <Area type="monotone" dataKey="price" stroke="#10b981" strokeWidth={2} fillOpacity={1} fill="url(#colorPrice)" />
                    </AreaChart>
                  </ResponsiveContainer>
               </div>
            </div>

          </div>

          {/* Right Sidebar */}
          <div className="space-y-6">
             
             {/* Quality Score Insight */}
             <div className="glass-card p-6 flex flex-col items-center text-center">
                <h3 className="text-lg font-bold text-white mb-2 w-full text-left">Quality Assessment</h3>
                <p className="text-sm text-gray-400 mb-6 text-left w-full">AI calculated score based on {devices?.length} live sensor nodes on-site.</p>
                
                <QualityScoreGauge score={listing.quality_score} size={220} strokeWidth={18} />
                
                <div className="mt-8 w-full p-4 bg-dark-900 rounded-xl border border-carbon-800 text-left">
                  <h4 className="text-sm font-semibold text-gray-300 mb-2 border-b border-carbon-800 pb-2">Score Breakdown</h4>
                  <ul className="space-y-2 text-xs text-gray-400">
                    <li className="flex justify-between"><span>Carbon Sink Efficacy</span> <span className="text-emerald-400">+30</span></li>
                    <li className="flex justify-between"><span>Soil Health</span> <span className="text-emerald-400">+25</span></li>
                    <li className="flex justify-between"><span>Biodiversity Proxies</span> <span className="text-emerald-400">+20</span></li>
                    <li className="flex justify-between"><span>Sensor Uptime</span> <span className="text-emerald-400">+10</span></li>
                  </ul>
                </div>
             </div>

             {/* Methodology Info */}
             <div className="glass-card p-6">
                <h3 className="text-sm font-bold text-white mb-4 uppercase tracking-wider">Methodology details</h3>
                <ul className="space-y-4">
                  <li>
                    <p className="text-xs text-gray-500 mb-1">Standard Body</p>
                    <p className="font-medium text-gray-200">{listing.methodology}</p>
                  </li>
                  <li>
                    <p className="text-xs text-gray-500 mb-1">Project Type</p>
                    <p className="font-medium text-gray-200 capitalize flex items-center gap-1.5">
                       {listing.type === 'forestry' ? <Leaf size={14} className="text-carbon-500"/> : 
                        listing.type === 'solar' ? <Flame size={14} className="text-amber-500"/> : 
                        <Sprout size={14} className="text-carbon-500" />}
                       {listing.type}
                    </p>
                  </li>
                  <li>
                    <p className="text-xs text-gray-500 mb-1">Total Project Area</p>
                    <p className="font-medium text-gray-200">{project.area_acres} Acres</p>
                  </li>
                  <li>
                    <p className="text-xs text-gray-500 mb-1">Blockchain Verification</p>
                    {listing.blockchain_hash ? (
                      <p className="text-xs font-mono text-carbon-400 break-all bg-carbon-900/50 p-2 rounded-lg border border-carbon-800/50 mt-1">
                        {listing.blockchain_hash}
                      </p>
                    ) : (
                      <p className="text-sm text-gray-400">Off-chain</p>
                    )}
                  </li>
                </ul>
             </div>

          </div>

        </div>
      </div>
    </div>
  );
};

export default ListingDetail;
