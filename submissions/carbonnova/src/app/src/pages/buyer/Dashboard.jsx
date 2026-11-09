import React from 'react';
import { useAuthStore } from '../../stores/authStore';
import { Building2, Leaf, ShieldCheck, Flame } from 'lucide-react';

const BuyerDashboard = () => {
  const { user } = useAuthStore();

  return (
    <div className="space-y-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">Welcome, {user?.organization || 'Corporate User'}</h1>
        <p className="text-gray-400">Track your verified carbon offsets and ESG goals.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="stat-card bg-gradient-to-br from-carbon-900/40 to-dark-800">
           <div className="flex justify-between items-start mb-4">
             <div className="p-2.5 bg-carbon-800 rounded-xl"><Leaf className="text-carbon-400" size={20}/></div>
             <span className="text-xs font-semibold px-2 py-1 bg-carbon-900 rounded border border-carbon-700 text-carbon-300">2026 Goal</span>
           </div>
           <p className="text-gray-400 text-sm mb-1">Offset Progress</p>
           <h3 className="text-3xl font-bold text-white mb-4">84%</h3>
           <div className="w-full h-2 rounded-full bg-dark-950 overflow-hidden">
             <div className="h-full bg-carbon-500 w-[84%] rounded-full relative">
               <div className="absolute top-0 left-0 w-full h-full bg-white/20 animate-pulse"></div>
             </div>
           </div>
           <p className="text-xs text-gray-500 mt-3 text-right">4,200 / 5,000 tCO₂e</p>
        </div>

        <div className="stat-card">
           <div className="p-2.5 bg-amber-900/20 rounded-xl w-max mb-4"><Flame className="text-amber-400" size={20}/></div>
           <p className="text-gray-400 text-sm mb-1">Portfolio Quality Average</p>
           <h3 className="text-3xl font-bold text-white">92.4 <span className="text-sm text-amber-400 font-bold ml-2 bg-amber-400/10 px-2 py-0.5 rounded border border-amber-400/20">Gold Tier</span></h3>
           <p className="text-xs text-gray-500 mt-4 leading-relaxed">Backed entirely by dMRV live sensor readings.</p>
        </div>

        <div className="stat-card">
           <div className="p-2.5 bg-blue-900/20 rounded-xl w-max mb-4"><ShieldCheck className="text-blue-400" size={20}/></div>
           <p className="text-gray-400 text-sm mb-1">Certificates Retired</p>
           <h3 className="text-3xl font-bold text-white">12</h3>
           <button className="text-sm font-medium text-blue-400 hover:text-blue-300 mt-4 flex items-center gap-1">
             View On-Chain Proofs &rarr;
           </button>
        </div>
      </div>

      <div className="glass-card">
        <div className="px-6 py-5 border-b border-carbon-800/50 flex justify-between items-center">
          <h3 className="font-bold text-white">Recent Transactions</h3>
          <button className="text-sm font-medium text-carbon-400">View All</button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-carbon-800/30 bg-dark-800/30">
                <th className="table-header p-4 pl-6">Project</th>
                <th className="table-header p-4">Type</th>
                <th className="table-header p-4 text-right">Volume (tCO₂e)</th>
                <th className="table-header p-4 text-right">Total Price</th>
                <th className="table-header p-4 pr-6 text-center">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-carbon-800/20">
              {[
                { name: 'Sundarbans Mangrove Restoration', type: 'Forestry', vol: 100, price: '₹3,20,000', status: 'Completed', date: 'Feb 20, 2026' },
                { name: 'Sahyadri Agroforestry Reserve', type: 'Agroforestry', vol: 50, price: '₹1,22,500', status: 'Completed', date: 'Feb 14, 2026' },
                { name: 'Rajasthan Solar Carbon Offset', type: 'Solar', vol: 200, price: '₹3,70,000', status: 'Pending', date: 'Mar 1, 2026' }
              ].map((tx, i) => (
                <tr key={i} className="hover:bg-dark-800/20 transition-colors">
                  <td className="p-4 pl-6">
                    <p className="font-medium text-gray-200">{tx.name}</p>
                    <p className="text-xs text-gray-500">{tx.date}</p>
                  </td>
                  <td className="p-4 text-sm text-gray-400">{tx.type}</td>
                  <td className="p-4 text-right font-medium text-white">{tx.vol}</td>
                  <td className="p-4 text-right text-carbon-400 font-medium">{tx.price}</td>
                  <td className="p-4 pr-6 text-center">
                    <span className={`text-xs font-semibold px-2 py-1 rounded-md ${
                      tx.status === 'Completed' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-slate-500/10 text-slate-300 border border-slate-500/20'
                    }`}>
                      {tx.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default BuyerDashboard;
