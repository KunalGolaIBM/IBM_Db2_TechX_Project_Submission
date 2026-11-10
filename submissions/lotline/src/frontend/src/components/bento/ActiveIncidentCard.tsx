import React from 'react';
import { ShieldAlert, ChevronRight, CheckCircle2, Clock, FileText } from 'lucide-react';
import type { IncidentDetails } from '../../services/api';

interface ActiveIncidentCardProps {
  incident: IncidentDetails | null;
  onSelectLot?: (lotId: string) => void;
  onExportDossier?: () => void;
}

export const ActiveIncidentCard: React.FC<ActiveIncidentCardProps> = ({
  incident,
  onSelectLot,
  onExportDossier,
}) => {
  const lotDetails = incident?.source_lot_details;

  return (
    <div className="bento-glass-window p-6 flex flex-col space-y-5 sm:space-y-6 h-full">
      {/* 1. Header with Incident ID & Severity */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3.5 border-b border-white/10">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-red-400 animate-pulse shadow-[0_0_8px_#f87171]" />
          <span className="text-[11px] font-mono font-bold tracking-wider uppercase text-white/80">
            ACTIVE INCIDENT
          </span>
          <span className="text-[10px] font-mono text-white/60 bg-white/5 border border-white/10 px-2 py-0.5 rounded font-semibold">
            {incident?.incident_id || 'INC-2026-001'}
          </span>
        </div>
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider bg-red-500/15 text-red-300 border border-red-500/30">
          <ShieldAlert className="w-3 h-3 text-red-400" />
          <span>{incident?.severity || 'CRITICAL'}</span>
        </span>
      </div>

      {/* 2. Dominant Source Lot Identifier Typography */}
      <div>
        <div className="text-[10px] font-mono font-semibold text-white/50 tracking-wider uppercase">
          CONTAMINATED SOURCE LOT
        </div>
        <button
          onClick={() => onSelectLot?.(lotDetails?.lot_id || 'RAW-204')}
          className="text-left group cursor-pointer mt-1.5 w-full block"
        >
          <div className="text-5xl sm:text-6xl font-black font-mono tracking-tight text-white group-hover:text-[#23cad2] transition-colors leading-none">
            {lotDetails?.lot_id || 'RAW-204'}
          </div>
          <div className="text-base sm:text-lg font-semibold text-white/90 mt-2 flex items-center gap-1.5 group-hover:translate-x-1 transition-transform">
            <span>{lotDetails?.item_name || 'Organic Spinach'}</span>
            <ChevronRight className="w-4 h-4 text-[#23cad2]" />
          </div>
        </button>
      </div>

      {/* 3. Structured Specification Matrix */}
      <div className="grid grid-cols-2 gap-3.5 py-3.5 border-y border-white/10 text-xs">
        <div>
          <span className="text-[10px] font-mono text-white/50 uppercase tracking-wider block">Supplier</span>
          <span className="font-semibold text-white mt-1 block truncate">
            {lotDetails?.supplier_name || 'GreenLeaf Foods'}
          </span>
        </div>
        <div>
          <span className="text-[10px] font-mono text-white/50 uppercase tracking-wider block">Original Quantity</span>
          <span className="font-mono font-bold text-white mt-1 block">
            {lotDetails?.quantity_created || 500} {lotDetails?.unit || 'KG'}
          </span>
        </div>
        <div>
          <span className="text-[10px] font-mono text-white/50 uppercase tracking-wider block">Db2 Incident ID</span>
          <span className="font-mono text-white/80 mt-1 block">
            {incident?.incident_id || 'INC-2026-001'}
          </span>
        </div>
        <div>
          <span className="text-[10px] font-mono text-white/50 uppercase tracking-wider block">Lot Status</span>
          <span className="font-mono font-bold text-amber-300 mt-1 inline-flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
            <span>{lotDetails?.status || 'QUARANTINED'}</span>
          </span>
        </div>
      </div>

      {/* 4. Compact Investigation Timeline */}
      <div>
        <div className="text-[10px] font-mono font-semibold text-white/50 uppercase mb-3 tracking-wider">
          INVESTIGATION SEQUENCE
        </div>
        <div className="space-y-2.5 relative pl-4 before:absolute before:left-1.5 before:top-2 before:bottom-2 before:w-[1px] before:bg-white/15">
          {[
            { title: 'Supplier alert received', time: '15:34', status: 'completed' },
            { title: 'Incident registered (Db2)', time: '15:36', status: 'completed' },
            { title: 'Traceability investigation started', time: '15:37', status: 'completed' },
            { title: 'Response awaiting human approval', time: 'Active', status: 'pending' },
          ].map((step, idx) => (
            <div key={idx} className="relative flex items-center justify-between text-xs">
              <span
                className={`absolute -left-4 top-1.5 w-2.5 h-2.5 rounded-full border-2 border-[#030c1a] ${
                  step.status === 'completed'
                    ? 'bg-[#23cad2] shadow-[0_0_6px_#23cad2]'
                    : 'bg-amber-400 animate-pulse shadow-[0_0_6px_#fbbf24]'
                }`}
              />
              <span className={`font-medium ${step.status === 'completed' ? 'text-white/85' : 'text-amber-200'}`}>
                {step.title}
              </span>
              <span className="font-mono text-[10px] text-white/40 pl-2 shrink-0">{step.time}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 5. Dossier Export Trigger */}
      {onExportDossier && (
        <div className="pt-2 border-t border-white/10 mt-auto">
          <button
            onClick={onExportDossier}
            className="w-full py-2.5 px-3 rounded-xl bg-white/[0.04] hover:bg-[#23cad2]/15 border border-white/10 hover:border-[#23cad2]/40 text-white/80 hover:text-[#8ef5e6] text-[11px] font-mono font-semibold flex items-center justify-center gap-2 transition-all cursor-pointer group"
          >
            <FileText className="w-3.5 h-3.5 text-[#23cad2] group-hover:scale-110 transition-transform" />
            <span>GENERATE RECALL DOSSIER (PDF)</span>
          </button>
        </div>
      )}
    </div>
  );
};
