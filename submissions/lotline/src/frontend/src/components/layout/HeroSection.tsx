import React from 'react';
import { ArrowUpRight, ShieldAlert, Sparkles, FileText } from 'lucide-react';

interface HeroSectionProps {
  onInvestigate: () => void;
  onRunAgents: () => void;
  onExportDossier?: () => void;
  isAgentRunning?: boolean;
}

export const HeroSection: React.FC<HeroSectionProps> = ({
  onInvestigate,
  onRunAgents,
  onExportDossier,
  isAgentRunning,
}) => {
  return (
    <section className="relative pt-6 pb-4 px-4 sm:px-6 max-w-[1720px] mx-auto">
      <div className="flex flex-col xl:flex-row xl:items-end xl:justify-between gap-5 border-b border-white/[0.08] pb-5">
        {/* Left: Eyebrow, Controlled Two-Line Headline & Supporting Description */}
        <div className="max-w-[1050px] space-y-2.5">
          {/* Eyebrow */}
          <div className="flex items-center gap-2.5 flex-wrap">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-mono font-bold tracking-wide bg-red-500/15 text-red-300 border border-red-500/30">
              <ShieldAlert className="w-3.5 h-3.5 text-red-400" />
              <span>ACTIVE INCIDENT / INC-2026-001</span>
            </span>
            <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono text-white/50 bg-white/5 border border-white/10 uppercase tracking-wider">
              SIMULATED SCENARIO
            </span>
          </div>

          {/* Controlled Two-Line Heading: exactly 2 lines at 1920px and 1440px */}
          <h1 className="text-[32px] sm:text-[42px] md:text-[46px] xl:text-[clamp(48px,3.8vw,66px)] font-black tracking-[-0.035em] text-white leading-[1.04] whitespace-normal">
            Every affected lot.
            <br className="hidden sm:inline" />{' '}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-white via-[#8ef5e6] to-[#23cad2] inline-block sm:inline">
              Every downstream consequence.
            </span>
          </h1>

          {/* Supporting Copy */}
          <p className="text-xs sm:text-[13.5px] text-white/70 leading-relaxed max-w-2xl pt-0.5">
            Trace raw materials through production, inventory and distribution. Turn fragmented supply-chain data into an actionable recall investigation.
          </p>
        </div>

        {/* Right / Inline Action CTAs */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 shrink-0 xl:pb-0.5 pt-1 xl:pt-0">
          <button
            onClick={onInvestigate}
            className="h-10 sm:h-11 px-5 sm:px-6 rounded-xl bg-[#23cad2] hover:bg-[#3ce5dd] text-[#030c1a] text-xs font-bold tracking-wider uppercase flex items-center justify-center gap-2 transition-all shadow-[0_4px_24px_rgba(35,202,210,0.35)] hover:shadow-[0_6px_32px_rgba(35,202,210,0.5)] active:scale-95 cursor-pointer whitespace-nowrap"
          >
            <span>INVESTIGATE A LOT</span>
            <ArrowUpRight className="w-4 h-4" />
          </button>

          <button
            onClick={onRunAgents}
            disabled={isAgentRunning}
            className="h-10 sm:h-11 px-4 sm:px-5 rounded-xl bg-white/[0.06] hover:bg-white/[0.10] border border-white/12 text-white text-xs font-semibold tracking-wider uppercase flex items-center justify-center gap-2 transition-all active:scale-95 cursor-pointer disabled:opacity-50 whitespace-nowrap"
          >
            <Sparkles className={`w-3.5 h-3.5 text-[#23cad2] ${isAgentRunning ? 'animate-spin' : ''}`} />
            <span>{isAgentRunning ? 'AGENT REASONING...' : 'DISPATCH AGENTS'}</span>
          </button>

          {onExportDossier && (
            <button
              onClick={onExportDossier}
              className="h-10 sm:h-11 px-4 sm:px-5 rounded-xl bg-[#091829] hover:bg-[#0d223a] border border-[#23cad2]/30 text-[#8ef5e6] hover:text-white text-xs font-semibold tracking-wider uppercase flex items-center justify-center gap-2 transition-all active:scale-95 cursor-pointer whitespace-nowrap shadow-[0_2px_12px_rgba(35,202,210,0.15)]"
            >
              <FileText className="w-3.5 h-3.5 text-[#23cad2]" />
              <span>EXPORT DOSSIER (PDF)</span>
            </button>
          )}
        </div>
      </div>
    </section>
  );
};
