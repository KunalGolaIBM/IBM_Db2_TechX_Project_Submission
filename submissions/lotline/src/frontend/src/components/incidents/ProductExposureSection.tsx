import React, { useState } from 'react';
import { Layers, Search } from 'lucide-react';
import type { AffectedBatch } from '../../services/api';

interface ProductExposureSectionProps {
  batches: AffectedBatch[];
}

export const ProductExposureSection: React.FC<ProductExposureSectionProps> = ({ batches }) => {
  const [search, setSearch] = useState('');

  const filtered = batches.filter(
    (b) =>
      b.lot_id.toLowerCase().includes(search.toLowerCase()) ||
      b.item_name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <section id="product-exposure" className="bento-opaque-card p-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-white/8">
        <div>
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-[#23cad2]" />
            <h2 className="text-sm font-mono font-bold uppercase tracking-wider text-white">
              PRODUCT EXPOSURE & INVENTORY AUDIT
            </h2>
          </div>
          <p className="text-xs text-white/50 mt-1">
            Finished product lot breakdown across production, secure warehousing, and downstream logistics
          </p>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-white/40 absolute left-2.5 top-2.5" />
          <input
            type="text"
            placeholder="Search lot ID or item..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="bg-black/40 border border-white/10 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white placeholder-white/40 focus:outline-none focus:border-[#23cad2] transition-colors w-48 sm:w-60"
          />
        </div>
      </div>

      {/* Grid of Product Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-5">
        {filtered.map((batch) => {
          const whPct = batch.total_units > 0 ? (batch.warehouse_units / batch.total_units) * 100 : 0;
          const delPct = batch.total_units > 0 ? (batch.delivered_units / batch.total_units) * 100 : 0;
          const transPct = batch.total_units > 0 ? (batch.in_transit_units / batch.total_units) * 100 : 0;

          return (
            <div
              key={batch.lot_id}
              className="p-4 rounded-xl bg-black/35 border border-white/8 hover:border-white/16 transition-all"
            >
              <div className="flex items-center justify-between pb-2 border-b border-white/6">
                <span className="font-mono text-sm font-bold text-white tracking-wide">{batch.lot_id}</span>
                <span className="text-[10px] font-mono text-amber-300 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded uppercase">
                  FINISHED BATCH
                </span>
              </div>

              <h4 className="text-xs font-semibold text-white/90 mt-2 truncate">{batch.item_name}</h4>

              <div className="mt-4">
                <div className="flex items-baseline justify-between">
                  <span className="text-[10px] font-mono text-white/50 uppercase">TOTAL EXPOSED</span>
                  <span className="text-lg font-mono font-black text-white">
                    {batch.total_units.toLocaleString()} <span className="text-xs font-normal text-white/60">units</span>
                  </span>
                </div>

                {/* Micro bar */}
                <div className="h-1.5 w-full bg-white/10 rounded-full overflow-hidden flex mt-2">
                  <div style={{ width: `${whPct}%` }} className="bg-[#23cad2]" />
                  <div style={{ width: `${delPct}%` }} className="bg-[#1680ac]" />
                  <div style={{ width: `${transPct}%` }} className="bg-amber-400" />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2 mt-4 pt-3 border-t border-white/6 text-[11px] font-mono">
                <div>
                  <span className="text-[9px] text-white/40 block">WAREHOUSE</span>
                  <span className="font-bold text-white">{batch.warehouse_units}</span>
                </div>
                <div>
                  <span className="text-[9px] text-white/40 block">DELIVERED</span>
                  <span className="font-bold text-white">{batch.delivered_units}</span>
                </div>
                <div>
                  <span className="text-[9px] text-white/40 block">TRANSIT</span>
                  <span className="font-bold text-amber-300">{batch.in_transit_units}</span>
                </div>
              </div>
            </div>
          );
        })}

        {filtered.length === 0 && (
          <div className="col-span-3 text-center py-8 text-white/40 font-mono text-xs">
            No finished batches found matching query.
          </div>
        )}
      </div>
    </section>
  );
};
