import React from 'react';
import { RotateCcw, Home, Trophy, Coins, Zap, Shield, Sparkles, Award } from 'lucide-react';
import { RunResults, PlayerProfile } from '../types/game';
import { soundEngine } from '../utils/audio';

interface ResultsScreenProps {
  results: RunResults;
  player: PlayerProfile;
  onPlayAgain: () => void;
  onMainMenu: () => void;
  onOpenCharacters?: () => void;
}

export const ResultsScreen: React.FC<ResultsScreenProps> = ({
  results,
  player,
  onPlayAgain,
  onMainMenu,
  onOpenCharacters,
}) => {
  const currentXpPercent = Math.min(100, Math.round((player.xp / player.nextLevelXp) * 100));

  return (
    <div className="relative w-full h-screen overflow-hidden flex flex-col justify-center items-center p-4 sm:p-8 bg-[#080B12] select-none text-white">
      {/* Cinematic Cyber Background with Radial Bloom */}
      <div className="absolute inset-0 z-0">
        <img
          src="/assets/bg_cyber_corridor_clean_1794383332925.jpg"
          alt="Results Background"
          referrerPolicy="no-referrer"
          className="w-full h-full object-cover filter brightness-40 blur-xs"
        />
        <div className="absolute inset-0 bg-[#080B12]/80" />
      </div>

      {/* Main Results Container */}
      <div className="relative z-10 w-full max-w-2xl bg-[#111827]/95 border border-[#00E5FF]/40 rounded-2xl p-6 sm:p-10 shadow-[0_0_60px_rgba(0,229,255,0.25)] flex flex-col gap-6 animate-in zoom-in-95 duration-200">
        {/* Cyberpunk chamfer corners */}
        <div className="absolute -top-1 -left-1 w-5 h-5 border-t-2 border-l-2 border-[#00E5FF]" />
        <div className="absolute -top-1 -right-1 w-5 h-5 border-t-2 border-r-2 border-[#00E5FF]" />
        <div className="absolute -bottom-1 -left-1 w-5 h-5 border-b-2 border-l-2 border-[#00E5FF]" />
        <div className="absolute -bottom-1 -right-1 w-5 h-5 border-b-2 border-r-2 border-[#00E5FF]" />

        {/* Top Header & High Score Notification */}
        <div className="text-center">
          {results.isNewHighScore ? (
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-[#00E5FF]/15 border border-[#00E5FF] text-xs font-mono font-bold text-[#00E5FF] mb-3 glow-cyan animate-pulse">
              <Trophy className="w-4 h-4 text-[#00E5FF]" />
              <span>NEW PERSONAL HIGH SCORE RECORD!</span>
            </div>
          ) : (
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded bg-[#8B5CF6]/15 border border-[#8B5CF6]/30 text-xs font-mono text-[#8B5CF6] mb-2">
              <Sparkles className="w-3.5 h-3.5" />
              <span>RUN DEBRIEFING COMPLETE</span>
            </div>
          )}

          <h1 className="font-gaming font-black text-3xl sm:text-5xl text-white tracking-wider">
            SESSION <span className="text-[#00E5FF]">REPORT</span>
          </h1>
          <p className="text-xs sm:text-sm font-mono text-[#94A3B8] mt-1">
            RUNNER: <span className="text-white font-semibold">{results.characterName}</span> // RECURSION COMPLETE
          </p>
        </div>

        {/* Center Primary Score Banner */}
        <div className="bg-[#080B12]/90 border border-white/10 rounded-xl p-5 text-center shadow-inner">
          <div className="text-[11px] font-mono text-[#94A3B8] uppercase tracking-widest mb-1">
            FINAL SCORE ACHIEVED
          </div>
          <div className="font-gaming font-black text-4xl sm:text-6xl text-white tracking-wider tabular-nums drop-shadow-[0_0_20px_rgba(0,229,255,0.6)]">
            {results.finalScore.toLocaleString()}
          </div>
          <div className="flex items-center justify-center gap-3 text-xs font-mono text-[#94A3B8] mt-2">
            <span>PREVIOUS BEST:</span>
            <span className="text-white font-semibold tabular-nums">
              {results.bestScore.toLocaleString()} PTS
            </span>
          </div>
        </div>

        {/* 4-Stat Grid Breakdown */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {/* Distance */}
          <div className="bg-[#1E293B]/70 border border-white/10 rounded-xl p-3.5 text-center">
            <div className="text-[10px] font-mono text-[#94A3B8] uppercase">DISTANCE</div>
            <div className="font-gaming font-bold text-lg sm:text-xl text-[#00E5FF] mt-1 tabular-nums">
              {results.distance.toLocaleString()} m
            </div>
          </div>

          {/* ByteCoins */}
          <div className="bg-[#1E293B]/70 border border-white/10 rounded-xl p-3.5 text-center">
            <div className="text-[10px] font-mono text-[#94A3B8] uppercase flex items-center justify-center gap-1">
              <Coins className="w-3 h-3 text-[#A3FF12]" />
              <span>COINS</span>
            </div>
            <div className="font-gaming font-bold text-lg sm:text-xl text-[#A3FF12] mt-1 tabular-nums">
              +{results.coins.toLocaleString()}
            </div>
          </div>

          {/* Obstacles Avoided */}
          <div className="bg-[#1E293B]/70 border border-white/10 rounded-xl p-3.5 text-center">
            <div className="text-[10px] font-mono text-[#94A3B8] uppercase flex items-center justify-center gap-1">
              <Shield className="w-3 h-3 text-[#8B5CF6]" />
              <span>BUGS EVADED</span>
            </div>
            <div className="font-gaming font-bold text-lg sm:text-xl text-[#8B5CF6] mt-1 tabular-nums">
              {results.obstaclesAvoided}
            </div>
          </div>

          {/* XP Gained */}
          <div className="bg-[#1E293B]/70 border border-white/10 rounded-xl p-3.5 text-center">
            <div className="text-[10px] font-mono text-[#94A3B8] uppercase flex items-center justify-center gap-1">
              <Award className="w-3 h-3 text-[#F59E0B]" />
              <span>XP EARNED</span>
            </div>
            <div className="font-gaming font-bold text-lg sm:text-xl text-[#F59E0B] mt-1 tabular-nums">
              +{results.xpEarned.toLocaleString()}
            </div>
          </div>
        </div>

        {/* Level Progression Progress Bar */}
        <div className="bg-[#080B12]/80 border border-white/10 rounded-xl p-3.5">
          <div className="flex items-center justify-between text-xs font-mono mb-1.5">
            <div className="flex items-center gap-2">
              <span className="text-[#00E5FF] font-gaming font-bold">LEVEL {player.level}</span>
              <span className="text-[#94A3B8]">DEVELOPER PROGRESSION</span>
            </div>
            <span className="text-white font-bold tabular-nums">
              {player.xp.toLocaleString()} / {player.nextLevelXp.toLocaleString()} XP
            </span>
          </div>
          <div className="w-full h-2 bg-black/60 rounded-full overflow-hidden border border-white/10">
            <div
              className="h-full bg-gradient-to-r from-[#00E5FF] via-[#8B5CF6] to-[#A3FF12] rounded-full transition-all duration-700"
              style={{ width: `${currentXpPercent}%` }}
            />
          </div>
        </div>

        {/* Action Buttons: PLAY AGAIN & MAIN MENU */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 pt-2">
          <button
            onClick={() => {
              soundEngine.playLaunch();
              onPlayAgain();
            }}
            onMouseEnter={() => soundEngine.playHover()}
            className="flex-1 py-4 px-6 rounded-lg bg-gradient-to-r from-[#00E5FF] to-[#00B4D8] text-[#080B12] font-gaming font-black text-base tracking-wider flex items-center justify-center gap-2.5 shadow-[0_0_25px_rgba(0,229,255,0.4)] hover:shadow-[0_0_40px_rgba(0,229,255,0.6)] transition-all cursor-pointer transform hover:-translate-y-0.5 active:translate-y-0"
          >
            <RotateCcw className="w-5 h-5 fill-current" />
            <span>PLAY AGAIN</span>
          </button>

          {onOpenCharacters && (
            <button
              onClick={() => {
                soundEngine.playClick();
                onOpenCharacters();
              }}
              onMouseEnter={() => soundEngine.playHover()}
              className="py-3.5 px-5 rounded-lg bg-[#1E293B] hover:bg-[#334155] border border-white/15 text-white font-gaming text-xs sm:text-sm font-bold tracking-wide flex items-center justify-center gap-2 transition-colors cursor-pointer"
            >
              <Zap className="w-4 h-4 text-[#8B5CF6]" />
              <span>UPGRADE RUNNER</span>
            </button>
          )}

          <button
            onClick={() => {
              soundEngine.playClick();
              onMainMenu();
            }}
            onMouseEnter={() => soundEngine.playHover()}
            className="py-3.5 px-5 rounded-lg bg-[#111827] hover:bg-[#1E293B] border border-white/15 text-[#94A3B8] hover:text-white font-gaming text-xs sm:text-sm font-bold tracking-wide flex items-center justify-center gap-2 transition-colors cursor-pointer"
          >
            <Home className="w-4 h-4" />
            <span>MAIN MENU</span>
          </button>
        </div>
      </div>
    </div>
  );
};
