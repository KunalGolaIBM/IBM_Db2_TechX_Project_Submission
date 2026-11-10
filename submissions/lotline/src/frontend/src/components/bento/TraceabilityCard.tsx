import React, { useState } from 'react';
import { GitBranch, ChevronRight, Info, X } from 'lucide-react';
import type { TraceData, TraceNode } from '../../services/api';

interface TraceabilityCardProps {
  trace: TraceData | null;
  onSelectLot?: (lot: TraceNode) => void;
}

export const TraceabilityCard: React.FC<TraceabilityCardProps> = ({ trace, onSelectLot }) => {
  const [inspectNode, setInspectNode] = useState<TraceNode | null>(null);

  const rawLot = trace?.nodes.find((n) => n.lot_type === 'RAW') || {
    lot_id: 'RAW-204',
    item_name: 'Organic Spinach',
    lot_type: 'RAW',
    status: 'QUARANTINED',
    depth: 0,
    facility_id: 'FAC-NGP',
    quantity: 500,
    unit: 'KG',
  };

  const wipLots = trace?.nodes.filter((n) => n.lot_type === 'WIP') || [
    { lot_id: 'WIP-301', item_name: 'Spinach Wrap Base', lot_type: 'WIP', status: 'ACTIVE', depth: 1, facility_id: 'FAC-NGP', quantity: 180, unit: 'KG' },
    { lot_id: 'WIP-302', item_name: 'Spinach Smoothie Puree', lot_type: 'WIP', status: 'ACTIVE', depth: 1, facility_id: 'FAC-NGP', quantity: 120, unit: 'KG' },
    { lot_id: 'WIP-303', item_name: 'Spinach Bowl Mix', lot_type: 'WIP', status: 'ACTIVE', depth: 1, facility_id: 'FAC-NSK', quantity: 100, unit: 'KG' },
  ];

  const finLots = trace?.nodes.filter((n) => n.lot_type === 'FINISHED') || [
    { lot_id: 'FIN-401', item_name: 'Green Spinach Wrap', lot_type: 'FINISHED', status: 'ACTIVE', depth: 2, facility_id: 'FAC-NGP', quantity: 1000, unit: 'UNIT' },
    { lot_id: 'FIN-402', item_name: 'Spinach Green Smoothie', lot_type: 'FINISHED', status: 'ACTIVE', depth: 2, facility_id: 'FAC-NGP', quantity: 800, unit: 'UNIT' },
    { lot_id: 'FIN-403', item_name: 'Garden Veggie Bowl', lot_type: 'FINISHED', status: 'ACTIVE', depth: 2, facility_id: 'FAC-NSK', quantity: 600, unit: 'UNIT' },
  ];

  const handleNodeClick = (node: TraceNode) => {
    setInspectNode(node);
    onSelectLot?.(node);
  };

  return (
    <div className="bento-glass-window p-6 flex flex-col justify-between gap-4 h-full relative">
      <div>
        {/* Collision-Free Responsive Header */}
        <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-white/10">
          <div className="flex items-center space-x-2">
            <GitBranch className="w-3.5 h-3.5 text-[#23cad2]" />
            <span className="text-[11px] font-mono font-bold tracking-wider uppercase text-white/80">
              TRACEABILITY NETWORK
            </span>
          </div>
          <div className="flex items-center gap-2 text-[10px] font-mono shrink-0">
            <span className="px-2 py-0.5 rounded bg-[#23cad2]/15 text-[#8ef5e6] border border-[#23cad2]/30 font-semibold">
              {trace?.total_downstream_lots || 6} DOWNSTREAM LOTS
            </span>
            <span className="text-white/50">{trace?.total_production_levels || 2} LEVELS</span>
          </div>
        </div>

        {/* Tree Lineage Visual Network */}
        <div className="mt-3.5 space-y-2">
          {/* Root Origin: RAW-204 */}
          <div
            onClick={() => handleNodeClick(rawLot)}
            className="p-2 rounded-lg bg-red-950/40 border border-red-500/40 hover:border-red-400 transition-all cursor-pointer flex items-center justify-between group"
          >
            <div className="flex items-center gap-2 min-w-0">
              <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse shrink-0" />
              <div className="truncate flex items-center gap-1.5">
                <span className="font-mono text-xs font-bold text-white group-hover:text-red-200">
                  {rawLot.lot_id}
                </span>
                <span className="text-[11px] text-red-200/75 truncate">({rawLot.item_name})</span>
              </div>
            </div>
            <span className="text-[9px] font-mono uppercase tracking-wider px-1.5 py-0.2 rounded bg-red-500/25 text-red-200 border border-red-500/40 shrink-0">
              ORIGIN
            </span>
          </div>

          {/* Connected Children: WIP -> FIN */}
          <div className="space-y-1.5 relative pl-3.5 before:absolute before:left-1.5 before:top-1 before:bottom-2 before:w-[1.5px] before:bg-gradient-to-b before:from-red-500/50 before:via-[#1680ac] before:to-[#23cad2]/60">
            {wipLots.map((wip, i) => {
              const fin = finLots[i];
              return (
                <div
                  key={wip.lot_id}
                  className="p-2 rounded-lg bg-black/40 border border-white/8 hover:border-white/20 transition-all space-y-1"
                >
                  {/* WIP Node (Level 1) */}
                  <div className="flex items-center justify-between text-xs">
                    <button
                      onClick={() => handleNodeClick(wip)}
                      className="flex items-center gap-2 text-left group cursor-pointer min-w-0 flex-1 mr-2"
                    >
                      <span className="w-1.5 h-1.5 rounded-full bg-[#1680ac] shrink-0" />
                      <span className="font-mono font-bold text-[#8ef5e6] group-hover:underline shrink-0">
                        {wip.lot_id}
                      </span>
                      <span className="text-[11px] text-white/60 truncate">
                        {wip.item_name}
                      </span>
                    </button>
                    <span className="text-[9px] font-mono text-white/40 uppercase shrink-0">L1 WIP</span>
                  </div>

                  {/* Downstream Finished Product (Level 2) */}
                  {fin && (
                    <div className="flex items-center justify-between text-xs pl-3 pt-1 border-t border-white/5">
                      <button
                        onClick={() => handleNodeClick(fin)}
                        className="flex items-center gap-1.5 text-left group cursor-pointer min-w-0 flex-1 mr-2"
                      >
                        <ChevronRight className="w-3 h-3 text-[#23cad2] shrink-0" />
                        <span className="font-mono font-bold text-white group-hover:text-[#23cad2] transition-colors shrink-0">
                          {fin.lot_id}
                        </span>
                        <span className="text-[11px] text-white/70 truncate">
                          {fin.item_name}
                        </span>
                      </button>
                      <span className="text-[9px] font-mono text-amber-300 bg-amber-500/10 px-1.5 py-0.2 rounded uppercase shrink-0">
                        FIN
                      </span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Helper Footer */}
      <div className="pt-2 border-t border-white/10 text-[10.5px] font-mono text-white/50 flex items-center gap-1.5">
        <Info className="w-3 h-3 text-[#23cad2] shrink-0" />
        <span>Click node in lineage tree to inspect Db2 batch</span>
      </div>

      {/* Node Inspection Drawer Modal */}
      {inspectNode && (
        <div className="absolute inset-0 bg-[#061220]/95 backdrop-blur-md rounded-xl p-5 z-20 flex flex-col justify-between border border-[#23cad2]/30 shadow-2xl animate-in fade-in zoom-in-95 duration-150">
          <div>
            <div className="flex items-center justify-between pb-2 border-b border-white/10">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-bold text-white">{inspectNode.lot_id}</span>
                <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-white/10 text-[#8ef5e6]">
                  {inspectNode.lot_type}
                </span>
              </div>
              <button
                onClick={() => setInspectNode(null)}
                className="p-1 rounded hover:bg-white/10 text-white/60 hover:text-white cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="mt-3">
              <h4 className="text-sm font-bold text-white">{inspectNode.item_name}</h4>
              <p className="text-xs text-white/50 mt-0.5">Production Lineage Level {inspectNode.depth}</p>
            </div>

            <div className="grid grid-cols-2 gap-3 mt-4 text-xs font-mono">
              <div className="p-2 rounded bg-black/40 border border-white/5">
                <span className="text-[10px] text-white/40 block">FACILITY</span>
                <span className="text-white font-bold">{inspectNode.facility_id || 'FAC-NGP'}</span>
              </div>
              <div className="p-2 rounded bg-black/40 border border-white/5">
                <span className="text-[10px] text-white/40 block">BATCH QUANTITY</span>
                <span className="text-white font-bold">{inspectNode.quantity || 500} {inspectNode.unit || 'UNITS'}</span>
              </div>
              <div className="p-2 rounded bg-black/40 border border-white/5">
                <span className="text-[10px] text-white/40 block">STATUS</span>
                <span className={inspectNode.status === 'QUARANTINED' ? 'text-amber-300 font-bold' : 'text-emerald-400 font-bold'}>
                  {inspectNode.status}
                </span>
              </div>
              <div className="p-2 rounded bg-black/40 border border-white/5">
                <span className="text-[10px] text-white/40 block">DB2 SCHEMA</span>
                <span className="text-white/80">LOTLINE_APP</span>
              </div>
            </div>
          </div>

          <div className="pt-3 border-t border-white/10 flex justify-end">
            <button
              onClick={() => setInspectNode(null)}
              className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/15 text-xs text-white font-mono cursor-pointer"
            >
              Close Inspector
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
