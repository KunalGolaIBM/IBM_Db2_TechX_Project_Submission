import React from 'react';
import { Link } from 'react-router-dom';
import { MapPin, Info, ArrowUpRight } from 'lucide-react';
import LiveQualityBadge from './LiveQualityBadge';

const CreditListingCard = ({ listing }) => {
  return (
    <div className="glass-card-hover group relative overflow-hidden flex flex-col h-full">
      {/* Visual Accent based on tier */}
      <div className={`absolute top-0 left-0 w-full h-1 ${
        listing.quality_tier === 'gold' ? 'bg-gradient-to-r from-amber-400 to-yellow-500' :
        listing.quality_tier === 'silver' ? 'bg-slate-400' :
        listing.quality_tier === 'bronze' ? 'bg-orange-600' :
        'bg-red-500'
      }`} />

      <div className="p-5 flex-1 flex flex-col">
        <div className="flex justify-between items-start mb-4">
          <LiveQualityBadge 
            score={listing.quality_score} 
            tier={listing.quality_tier} 
            lastUpdate={listing.last_score_update} 
          />
          <span className="text-xs px-2 py-1 rounded-md bg-dark-700 border border-carbon-800 text-gray-400 uppercase tracking-wide">
            {listing.type}
          </span>
        </div>

        <h3 className="text-lg font-bold text-white mb-2 leading-tight group-hover:text-carbon-300 transition-colors">
          {listing.project_name}
        </h3>
        
        <div className="flex items-center gap-1.5 text-sm text-gray-400 mb-6">
          <MapPin size={14} className="shrink-0" />
          <span className="truncate">{listing.location_state}, India</span>
        </div>

        <div className="mt-auto grid grid-cols-2 gap-4">
          <div className="bg-dark-900/50 rounded-xl p-3 border border-carbon-800/20">
            <p className="text-xs text-gray-500 mb-1">Available Volume</p>
            <p className="text-lg font-semibold text-gray-200">{listing.quantity_available.toLocaleString()} <span className="text-xs font-normal text-gray-500">tCO₂e</span></p>
          </div>
          <div className="bg-dark-900/50 rounded-xl p-3 border border-carbon-800/20">
             <p className="text-xs text-gray-500 mb-1 flex items-center gap-1">
               Live Price
               <Info size={12} className="text-carbon-600" />
             </p>
             <p className="text-lg font-semibold text-carbon-400">₹{listing.price_per_tonne.toLocaleString()} <span className="text-xs font-normal text-carbon-600/60">/t</span></p>
          </div>
        </div>
      </div>

      <div className="px-5 py-4 border-t border-carbon-800/30 bg-dark-800/30 flex justify-between items-center group-hover:bg-carbon-900/20 transition-colors">
         <span className="text-xs text-gray-500">Voluntary standard: {listing.methodology}</span>
         <Link 
           to={`/marketplace/${listing.id}`}
           className="p-2 rounded-full bg-carbon-800 text-carbon-300 group-hover:bg-carbon-500 group-hover:text-white transition-all transform group-hover:rotate-45"
         >
           <ArrowUpRight size={16} />
         </Link>
      </div>
    </div>
  );
};

export default CreditListingCard;
