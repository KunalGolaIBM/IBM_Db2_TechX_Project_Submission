import React, { useState, useMemo } from 'react';
import { useMarketDataStore } from '../stores/marketStore';
import CreditListingCard from '../components/marketplace/CreditListingCard';
import { Search, Filter, SlidersHorizontal } from 'lucide-react';

const Marketplace = () => {
  const { listings } = useMarketDataStore();
  const [searchTerm, setSearchTerm] = useState('');
  const [activeType, setActiveType] = useState('all');
  const [activeTier, setActiveTier] = useState('all');

  const filteredListings = useMemo(() => {
    return listings.filter(listing => {
      if (listing.status !== 'active') return false;
      
      const matchesSearch = listing.project_name.toLowerCase().includes(searchTerm.toLowerCase()) || 
                            listing.location_state.toLowerCase().includes(searchTerm.toLowerCase());
      
      const matchesType = activeType === 'all' || listing.type === activeType;
      const matchesTier = activeTier === 'all' || listing.quality_tier === activeTier;

      return matchesSearch && matchesType && matchesTier;
    });
  }, [listings, searchTerm, activeType, activeTier]);

  return (
    <div className="min-h-screen pt-24 pb-12">
      <div className="container mx-auto px-6">
        
        {/* Header & Search */}
        <div className="mb-10 lg:flex items-end justify-between gap-6">
          <div className="mb-6 lg:mb-0">
            <h1 className="text-4xl font-bold text-white mb-2">Marketplace</h1>
            <p className="text-gray-400">Discover and trade verifiable, high-integrity carbon credits.</p>
          </div>
          
          <div className="flex-1 max-w-2xl relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500 w-5 h-5" />
            <input 
              type="text" 
              placeholder="Search by project name, location..." 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-dark-800/80 border border-carbon-800/60 rounded-2xl pl-12 pr-4 py-4 text-gray-100 placeholder-gray-500 focus:outline-none focus:border-carbon-500 focus:ring-1 focus:ring-carbon-500/30 transition-all shadow-inner"
            />
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-4 mb-8 pb-6 border-b border-carbon-800/40">
           <div className="flex items-center gap-2 mr-4 text-gray-400 font-medium">
             <Filter size={18} />
             <span>Filters:</span>
           </div>

           <div className="flex bg-dark-800 p-1 rounded-xl border border-carbon-800/50">
             {['all', 'forestry', 'agroforestry', 'solar', 'biogas'].map(type => (
               <button
                 key={type}
                 onClick={() => setActiveType(type)}
                 className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-all ${activeType === type ? 'bg-carbon-900 text-carbon-300 shadow-sm' : 'text-gray-400 hover:text-gray-200'}`}
               >
                 {type}
               </button>
             ))}
           </div>

           <div className="flex bg-dark-800 p-1 rounded-xl border border-carbon-800/50">
             <button
               onClick={() => setActiveTier('all')}
               className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-all ${activeTier === 'all' ? 'bg-carbon-900 text-gray-200 shadow-sm' : 'text-gray-400 hover:text-gray-200'}`}
             >
               All Tiers
             </button>
             <button
               onClick={() => setActiveTier('gold')}
               className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-all ${activeTier === 'gold' ? 'bg-amber-400/20 text-amber-400 shadow-sm' : 'text-gray-400 hover:text-amber-400/70'}`}
             >
               Gold
             </button>
             <button
               onClick={() => setActiveTier('silver')}
               className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-all ${activeTier === 'silver' ? 'bg-slate-400/20 text-slate-300 shadow-sm' : 'text-gray-400 hover:text-slate-300/70'}`}
             >
               Silver
             </button>
             <button
               onClick={() => setActiveTier('bronze')}
               className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-all ${activeTier === 'bronze' ? 'bg-orange-600/20 text-orange-400 shadow-sm' : 'text-gray-400 hover:text-orange-400/70'}`}
             >
               Bronze
             </button>
           </div>
           
           <button className="ml-auto btn-secondary flex items-center gap-2 py-2">
             <SlidersHorizontal size={16} /> Sort By
           </button>
        </div>

        {/* Results Grid */}
        <div className="mb-6 flex justify-between items-center">
          <p className="text-gray-400 font-medium">Showing {filteredListings.length} listings</p>
          <span className="flex items-center gap-2 text-xs font-semibold px-3 py-1 bg-carbon-900/40 rounded-full border border-carbon-800 text-carbon-400">
             <span className="live-dot" /> Live Pricing Active
          </span>
        </div>

        {filteredListings.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {filteredListings.map(listing => (
              <CreditListingCard key={listing.id} listing={listing} />
            ))}
          </div>
        ) : (
          <div className="text-center py-24 bg-dark-800/30 rounded-3xl border border-carbon-800/30 border-dashed">
            <div className="w-16 h-16 bg-carbon-900/50 rounded-full flex items-center justify-center mx-auto mb-4">
              <Leaf className="w-8 h-8 text-carbon-600" />
            </div>
            <h3 className="text-xl font-bold text-white mb-2">No listings found</h3>
            <p className="text-gray-400 max-w-sm mx-auto">Try adjusting your filters or search terms to find what you're looking for.</p>
            <button 
              onClick={() => { setSearchTerm(''); setActiveType('all'); setActiveTier('all'); }}
              className="mt-6 text-carbon-400 hover:text-carbon-300 font-medium pb-1 border-b border-carbon-500 border-dashed"
            >
              Clear all filters
            </button>
          </div>
        )}

      </div>
    </div>
  );
};

export default Marketplace;
