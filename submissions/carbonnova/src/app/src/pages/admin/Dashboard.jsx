import React from 'react';
import { useMarketDataStore } from '../../stores/marketStore';
import { ShieldAlert, Users, TrendingUp, Activity, CheckCircle, Clock } from 'lucide-react';
import { mockTransactions } from '../../lib/mockData';

const AdminDashboard = () => {
  const { listings, platformStats } = useMarketDataStore();

  const flaggedListings = listings.filter(l => l.quality_tier === 'flagged');

  return (
    <div className="space-y-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">Platform Overview</h1>
        <p className="text-gray-400">Monitor system health, flagged issues, and platform revenue.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
        <div className="stat-card border-t-2 border-carbon-500">
           <p className="text-gray-400 text-sm mb-1">Total GMV</p>
           <h3 className="text-2xl font-bold text-white mb-2">₹{(platformStats.totalGMV / 100000).toFixed(1)}L</h3>
           <p className="text-xs text-carbon-400 flex items-center gap-1"><TrendingUp size={12}/> +14% WoW</p>
        </div>
        <div className="stat-card border-t-2 border-emerald-500">
           <p className="text-gray-400 text-sm mb-1">Platform Fees</p>
           <h3 className="text-2xl font-bold text-white mb-2">₹{((platformStats.totalGMV * 0.02) / 1000).toFixed(1)}K</h3>
           <p className="text-xs text-emerald-400 flex items-center gap-1">2% Take rate</p>
        </div>
        <div className="stat-card border-t-2 border-blue-500">
           <p className="text-gray-400 text-sm mb-1">Total Users</p>
           <h3 className="text-2xl font-bold text-white mb-2">{platformStats.activeSellers + platformStats.activeBuyers}</h3>
           <p className="text-xs text-blue-400">{platformStats.activeSellers} Sellers / {platformStats.activeBuyers} Buyers</p>
        </div>
        <div className="stat-card border-t-2 border-amber-500">
           <p className="text-gray-400 text-sm mb-1">Active Sensors</p>
           <h3 className="text-2xl font-bold text-white mb-2">{platformStats.activeSensors}</h3>
           <p className="text-xs text-amber-400 flex items-center gap-1"><Activity size={12} /> 99.8% Uptime</p>
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        
        {/* Recent Transactions Feed */}
        <div className="glass-card flex flex-col h-[500px]">
          <div className="px-6 py-5 border-b border-carbon-800/50 flex justify-between items-center shrink-0">
            <h3 className="font-bold text-white flex items-center gap-2">
              <Activity className="text-carbon-400" size={18} /> Live Transaction Feed
            </h3>
            <span className="live-dot" />
          </div>
          <div className="flex-1 overflow-y-auto px-2 py-2 styled-scrollbar">
            <div className="space-y-2">
              {mockTransactions.map((tx) => (
                <div key={tx.id} className="p-4 rounded-xl hover:bg-dark-800/50 transition-colors flex justify-between items-center border border-transparent hover:border-carbon-800/50">
                   <div className="flex items-center gap-4">
                     <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${
                       tx.status === 'completed' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-slate-500/10 text-slate-400'
                     }`}>
                       {tx.status === 'completed' ? <CheckCircle size={18} /> : <Clock size={18} />}
                     </div>
                     <div>
                       <p className="font-medium text-gray-200 text-sm">{tx.buyer_name}</p>
                       <p className="text-xs text-gray-500 truncate w-48">Bought {tx.quantity}t from {tx.project_name}</p>
                     </div>
                   </div>
                   <div className="text-right">
                     <p className="text-sm font-bold text-carbon-400">₹{(tx.total_amount).toLocaleString()}</p>
                     <p className="text-[10px] text-gray-500">Fee: ₹{tx.platform_fee.toLocaleString()}</p>
                   </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Flagged Listings Alert */}
        <div className="glass-card flex flex-col">
          <div className="px-6 py-5 border-b border-red-900/40 bg-red-900/10 flex justify-between items-center shrink-0">
            <h3 className="font-bold text-red-400 flex items-center gap-2">
              <ShieldAlert size={18} /> Action Required: Flagged Projects
            </h3>
            <span className="px-2.5 py-1 bg-red-500 text-white text-xs font-bold rounded-full">
              {flaggedListings.length}
            </span>
          </div>
          <div className="p-6">
            <p className="text-sm text-gray-400 mb-4 pb-4 border-b border-carbon-800/40">
              The following listings have dropped below a Quality Score of 45 and have been automatically suspended from the marketplace pending manual review.
            </p>
            
            <div className="space-y-4">
              {flaggedListings.map(listing => (
                <div key={listing.id} className="p-4 rounded-xl bg-dark-800 border border-red-900/30 flex flex-col sm:flex-row justify-between sm:items-center gap-4">
                   <div>
                     <p className="font-medium text-red-300 text-sm">{listing.project_name}</p>
                     <p className="text-xs text-red-400/70">Score dropped to {listing.quality_score}/100 • Sensor anomaly</p>
                   </div>
                   <div className="flex gap-2">
                     <button className="px-3 py-1.5 rounded-lg text-xs font-medium bg-dark-900 text-gray-300 border border-carbon-800 hover:text-white">Review Data</button>
                     <button className="px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30">Suspend User</button>
                   </div>
                </div>
              ))}
              
              {flaggedListings.length === 0 && (
                <div className="text-center py-8">
                  <p className="text-gray-500 text-sm">No flagged listings right now. Auto-dMRV is healthy.</p>
                </div>
              )}
            </div>
          </div>
        </div>
        
      </div>
    </div>
  );
};

export default AdminDashboard;
