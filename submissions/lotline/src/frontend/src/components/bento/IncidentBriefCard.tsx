import React from 'react';
import { FileText } from 'lucide-react';
import type { IncidentDetails } from '../../services/api';

interface IncidentBriefCardProps {
  incident: IncidentDetails | null;
}

export const IncidentBriefCard: React.FC<IncidentBriefCardProps> = ({ incident }) => {
  const lotDetails = incident?.source_lot_details;

  return (
    <div className="bento-opaque-card p-6 flex flex-col justify-between gap-4 h-full">
      <div>
        {/* Header Label */}
        <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
          <div className="flex items-center space-x-2">
            <FileText className="w-3.5 h-3.5 text-[#23cad2]" />
            <span className="text-[11px] font-mono font-bold tracking-wider uppercase text-white/70">
              INCIDENT BRIEF
            </span>
          </div>
          <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-white/[0.04] text-white/40 border border-white/[0.08]">
            SIMULATED DATA
          </span>
        </div>

        {/* Narrative Description */}
        <p className="mt-3 text-[13px] sm:text-[13.5px] text-white/85 leading-relaxed">
          {incident?.description || 'Supplier GreenLeaf Foods reported possible Salmonella contamination in organic spinach lot RAW-204. Downstream batches require investigation.'}
        </p>
      </div>

      {/* Metadata Specification Grid */}
      <div className="grid grid-cols-2 gap-3 pt-3.5 border-t border-white/[0.06] text-xs">
        <div>
          <span className="text-[10px] font-mono text-white/45 uppercase tracking-wider block">Source</span>
          <span className="font-semibold text-white truncate block mt-0.5">
            {lotDetails?.supplier_name || 'GreenLeaf Foods'}
          </span>
        </div>
        <div>
          <span className="text-[10px] font-mono text-white/45 uppercase tracking-wider block">Material</span>
          <span className="font-semibold text-white truncate block mt-0.5">
            {lotDetails?.item_name || 'Organic Spinach'}
          </span>
        </div>
        <div>
          <span className="text-[10px] font-mono text-white/45 uppercase tracking-wider block">Affected Raw Lot</span>
          <span className="font-mono font-bold text-[#8ef5e6] block mt-0.5">
            {lotDetails?.lot_id || 'RAW-204'}
          </span>
        </div>
        <div>
          <span className="text-[10px] font-mono text-white/45 uppercase tracking-wider block">Severity</span>
          <span className="font-bold text-red-400 block mt-0.5 uppercase tracking-wide">
            {incident?.severity || 'CRITICAL'}
          </span>
        </div>
      </div>
    </div>
  );
};
