import React from 'react';
import { Play, RotateCcw, Home, Volume2, VolumeX, ShieldAlert } from 'lucide-react';
import { soundEngine } from '../utils/audio';

interface PauseMenuProps {
  score: number;
  distance: number;
  coins: number;
  onResume: () => void;
  onRestart: () => void;
  onMainMenu: () => void;
  isMuted: boolean;
  onToggleMute: () => void;
}

export const PauseMenu: React.FC<PauseMenuProps> = ({
  score,
  distance,
  coins,
  onResume,
  onRestart,
  onMainMenu,
  isMuted,
  onToggleMute,
}) => {
  return (
    <div className="absolute inset-0 z-30 bg-[#080B12]/85 backdrop-blur-md flex items-center justify-center p-6 select-none animate-in fade-in duration-200">
      <div className="relative w-full max-w-md bg-[#111827] border border-[#00E5FF]/40 rounded-2xl p-6 sm:p-8 shadow-[0_0_50px_rgba(0,229,255,0.2)]">
        {/* Cyberpunk corner brackets */}
        <div className="absolute -top-1 -left-1 w-4 h-4 border-t-2 border-l-2 border-[#00E5FF]" />
        <div className="absolute -top-1 -right-1 w-4 h-4 border-t-2 border-r-2 border-[#00E5FF]" />
        <div className="absolute -bottom-1 -left-1 w-4 h-4 border-b-2 border-l-2 border-[#00E5FF]" />
        <div className="absolute -bottom-1 -right-1 w-4 h-4 border-b-2 border-r-2 border-[#00E5FF]" />

        {/* Header */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded bg-[#8B5CF6]/15 border border-[#8B5CF6]/30 text-xs font-mono text-[#8B5CF6] mb-2">
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>EXECUTION SUSPENDED</span>
          </div>
          <h2 className="font-gaming font-black text-3xl sm:text-4xl text-white tracking-wider">
            GAME <span className="text-[#00E5FF]">PAUSED</span>
          </h2>
        </div>

        {/* Session Snapshot Stats */}
        <div className="grid grid-cols-3 gap-2 bg-[#080B12]/80 border border-white/10 rounded-xl p-3 mb-6 text-center">
          <div>
            <div className="text-[10px] font-mono text-[#94A3B8] uppercase">Score</div>
            <div className="text-sm font-gaming font-bold text-white tabular-nums">
              {score.toLocaleString()}
            </div>
          </div>
          <div className="border-x border-white/10">
            <div className="text-[10px] font-mono text-[#94A3B8] uppercase">Distance</div>
            <div className="text-sm font-mono font-bold text-[#00E5FF] tabular-nums">
              {distance}m
            </div>
          </div>
          <div>
            <div className="text-[10px] font-mono text-[#94A3B8] uppercase">Coins</div>
            <div className="text-sm font-mono font-bold text-[#A3FF12] tabular-nums">
              {coins}
            </div>
          </div>
        </div>

        {/* Buttons List */}
        <div className="flex flex-col gap-3">
          {/* Resume */}
          <button
            onClick={() => {
              soundEngine.playClick();
              onResume();
            }}
            onMouseEnter={() => soundEngine.playHover()}
            className="w-full py-3.5 px-6 rounded-lg bg-gradient-to-r from-[#00E5FF] to-[#00B4D8] text-[#080B12] font-gaming font-bold text-base tracking-wider flex items-center justify-center gap-2.5 shadow-[0_0_20px_rgba(0,229,255,0.4)] hover:shadow-[0_0_30px_rgba(0,229,255,0.6)] transition-all cursor-pointer"
          >
            <Play className="w-4 h-4 fill-current" />
            <span>RESUME RUN</span>
          </button>

          {/* Restart */}
          <button
            onClick={() => {
              soundEngine.playClick();
              onRestart();
            }}
            onMouseEnter={() => soundEngine.playHover()}
            className="w-full py-3 px-6 rounded-lg bg-[#1E293B] hover:bg-[#334155] border border-white/15 text-white font-gaming text-sm font-semibold tracking-wider flex items-center justify-center gap-2.5 transition-colors cursor-pointer"
          >
            <RotateCcw className="w-4 h-4 text-[#8B5CF6]" />
            <span>RESTART RUN</span>
          </button>

          {/* Audio Quick Mute */}
          <button
            onClick={() => {
              soundEngine.playClick();
              onToggleMute();
            }}
            className="w-full py-2.5 px-6 rounded-lg bg-[#1E293B]/60 hover:bg-[#1E293B] border border-white/10 text-[#94A3B8] hover:text-white font-mono text-xs flex items-center justify-center gap-2 transition-colors cursor-pointer"
          >
            {isMuted ? <VolumeX className="w-4 h-4 text-red-400" /> : <Volume2 className="w-4 h-4 text-[#A3FF12]" />}
            <span>{isMuted ? 'UNMUTE AUDIO' : 'MUTE AUDIO'}</span>
          </button>

          {/* Main Menu */}
          <button
            onClick={() => {
              soundEngine.playClick();
              onMainMenu();
            }}
            onMouseEnter={() => soundEngine.playHover()}
            className="w-full py-3 px-6 rounded-lg bg-transparent hover:bg-white/5 text-[#94A3B8] hover:text-white font-gaming text-xs tracking-wider flex items-center justify-center gap-2 transition-colors cursor-pointer mt-1"
          >
            <Home className="w-4 h-4" />
            <span>QUIT TO MAIN MENU</span>
          </button>
        </div>
      </div>
    </div>
  );
};
