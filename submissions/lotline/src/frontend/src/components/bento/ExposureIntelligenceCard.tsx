import React from 'react';
import { Package, Layers, GitCommit } from 'lucide-react';
import type { ExposureData } from '../../services/api';

interface ExposureIntelligenceCardProps {
  exposure: ExposureData | null;
}

export const ExposureIntelligenceCard: React.FC<ExposureIntelligenceCardProps> = ({ exposure }) => {
  const totalUnits = exposure?.total_affected_units ?? 2400;
  const whUnits = exposure?.warehouse_units ?? 1350;
  const retUnits = exposure?.retailer_delivered_units ?? 850;
  const transUnits = exposure?.in_transit_units ?? 200;

  const whPct = totalUnits > 0 ? (whUnits / totalUnits) * 100 : 0;
  const retPct = totalUnits > 0 ? (retUnits / totalUnits) * 100 : 0;
  const transPct = totalUnits > 0 ? (transUnits / totalUnits) * 100 : 0;

  return (
    <div className="bento-glass-window p-6 flex flex-col justify-between gap-4 h-full">
      <div>
        {/* Header Label */}
        <div className="flex items-center justify-between pb-3 border-b border-white/10">
          <div className="flex items-center space-x-2">
            <Package className="w-3.5 h-3.5 text-[#23cad2]" />
            <span className="text-[11px] font-mono font-bold tracking-wider uppercase text-white/80">
              EXPOSURE INTELLIGENCE
            </span>
          </div>
          <span className="text-[10px] font-mono text-[#8ef5e6] bg-white/5 border border-white/10 px-2 py-0.5 rounded font-semibold">
            LIVE DB2 AUDIT
          </span>
        </div>

        {/* Hero Number & Descriptor */}
        <div className="mt-3.5 mb-3.5">
          <div className="text-4xl sm:text-5xl font-black font-mono tracking-tight text-white leading-none">
            {totalUnits.toLocaleString()}
          </div>
          <div className="text-[10.5px] font-mono font-semibold tracking-wider uppercase text-white/60 mt-1.5">
            POTENTIALLY AFFECTED UNITS
          </div>
        </div>

        {/* Segmented Distribution Bar */}
        <div className="space-y-2.5">
          <div className="h-2.5 w-full bg-black/50 rounded-full overflow-hidden flex p-0.5 border border-white/10">
            <div
              style={{ width: `${whPct}%` }}
              title={`Warehouse: ${whUnits} units (${whPct.toFixed(1)}%)`}
              className="h-full bg-[#23cad2] rounded-l-full transition-all duration-500"
            />
            <div
              style={{ width: `${retPct}%` }}
              title={`Retailers: ${retUnits} units (${retPct.toFixed(1)}%)`}
              className="h-full bg-[#1680ac] transition-all duration-500"
            />
            <div
              style={{ width: `${transPct}%` }}
              title={`In transit: ${transUnits} units (${transPct.toFixed(1)}%)`}
              className="h-full bg-amber-400 rounded-r-full transition-all duration-500"
            />
          </div>

          {/* Three Distinct Exposure Columns */}
          <div className="grid grid-cols-3 gap-2 text-xs">
            <div className="flex flex-col">
              <div className="flex items-center gap-1.5 text-[10px] font-mono text-white/60 uppercase">
                <span className="w-1.5 h-1.5 rounded-full bg-[#23cad2]" />
                <span>Warehouse</span>
              </div>
              <span className="font-mono font-bold text-white text-sm sm:text-base mt-0.5">
                {whUnits.toLocaleString()}
              </span>
              <span className="text-[10px] font-mono text-white/40">{whPct.toFixed(1)}%</span>
            </div>

            <div className="flex flex-col">
              <div className="flex items-center gap-1.5 text-[10px] font-mono text-white/60 uppercase">
                <span className="w-1.5 h-1.5 rounded-full bg-[#1680ac]" />
                <span>Retailers</span>
              </div>
              <span className="font-mono font-bold text-white text-sm sm:text-base mt-0.5">
                {retUnits.toLocaleString()}
              </span>
              <span className="text-[10px] font-mono text-white/40">{retPct.toFixed(1)}%</span>
            </div>

            <div className="flex flex-col">
              <div className="flex items-center gap-1.5 text-[10px] font-mono text-white/60 uppercase">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                <span>Transit</span>
              </div>
              <span className="font-mono font-bold text-amber-300 text-sm sm:text-base mt-0.5">
                {transUnits.toLocaleString()}
              </span>
              <span className="text-[10px] font-mono text-amber-300/60">{transPct.toFixed(1)}%</span>
            </div>
          </div>
        </div>
      </div>

      {/* Scope Footer: 3 Finished Lots • 6 Downstream Lots */}
      <div className="pt-3 border-t border-white/10 flex items-center justify-between text-xs font-mono">
        <div className="flex items-center gap-1.5 text-white/80">
          <Layers className="w-3.5 h-3.5 text-[#23cad2]" />
          <span className="font-bold text-white">{exposure?.finished_product_lots_count || 3}</span>
          <span className="text-[10px] uppercase text-white/50">FINISHED LOTS</span>
        </div>
        <div className="flex items-center gap-1.5 text-white/80">
          <GitCommit className="w-3.5 h-3.5 text-[#8ef5e6]" />
          <span className="font-bold text-[#8ef5e6]">{exposure?.total_downstream_lots_count || 6}</span>
          <span className="text-[10px] uppercase text-white/50">DOWNSTREAM LOTS</span>
        </div>
      </div>
    </div>
  );
};
