import React from 'react';
import { Play, Users, Trophy, Settings, Terminal, Shield, Sparkles, ChevronRight, Coins } from 'lucide-react';
import { PlayerProfile, Character } from '../types/game';
import { soundEngine } from '../utils/audio';

interface MainMenuProps {
  player: PlayerProfile;
  selectedCharacter: Character;
  onPlay: () => void;
  onOpenCharacters: () => void;
  onOpenLeaderboard: () => void;
  onOpenSettings: () => void;
}

export const MainMenu: React.FC<MainMenuProps> = ({
  player,
  selectedCharacter,
  onPlay,
  onOpenCharacters,
  onOpenLeaderboard,
  onOpenSettings,
}) => {
  const xpPercentage = Math.min(100, Math.round((player.xp / player.nextLevelXp) * 100));

  const handleAction = (callback: () => void, isPlay = false) => {
    if (isPlay) {
      soundEngine.playLaunch();
    } else {
      soundEngine.playClick();
    }
    callback();
  };

  return (
    <div className="relative w-full h-screen overflow-hidden flex flex-col justify-between p-6 sm:p-10 select-none">
      {/* Cinematic Cyber Background without baked-in text */}
      <div className="absolute inset-0 z-0">
        <img
          src="/assets/bg_cyber_corridor_clean_1794383332925.jpg"
          alt="Bootcamp Runner Cyber Corridor"
          referrerPolicy="no-referrer"
          className="w-full h-full object-cover object-center filter brightness-90 contrast-110"
        />
        {/* Atmospheric Gradients & Vignette */}
        <div className="absolute inset-0 bg-gradient-to-t from-[#080B12] via-[#080B12]/60 to-[#080B12]/40" />
        <div className="absolute inset-0 bg-gradient-to-r from-[#080B12]/90 via-[#080B12]/40 to-transparent" />

        {/* Cyberpunk Scanlines and subtle grid */}
        <div
          className="absolute inset-0 pointer-events-none opacity-20"
          style={{
            backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0, 229, 255, 0.05) 3px)',
            backgroundSize: '100% 4px'
          }}
        />
      </div>

      {/* Top Header Strip: Brand & Player Profile */}
      <header className="relative z-10 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        {/* Brand Lockup */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-[#111827] border border-[#00E5FF]/40 flex items-center justify-center glow-cyan-sm shadow-inner">
            <Terminal className="w-5 h-5 text-[#00E5FF]" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-gaming font-bold tracking-wider text-xl text-white">
                BOOTCAMP<span className="text-[#00E5FF]">RUNNER</span>
              </span>
              <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold tracking-wider uppercase bg-[#8B5CF6]/20 border border-[#8B5CF6]/50 text-[#8B5CF6]">
                DEV RELEASE
              </span>
            </div>
            <p className="text-xs text-[#94A3B8] font-mono tracking-tight">
              CYBER_KERNEL // PROTOCOL 3.0
            </p>
          </div>
        </div>

        {/* Player Profile Card */}
        <div className="flex items-center gap-4 bg-[#111827]/80 backdrop-blur-md border border-white/10 px-4 py-2.5 rounded-xl shadow-2xl">
          {/* Avatar and Level */}
          <div className="relative">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-[#00E5FF]/30 to-[#8B5CF6]/40 border border-[#00E5FF]/50 flex items-center justify-center font-gaming font-bold text-sm text-[#F8FAFC]">
              {player.username.slice(0, 2).toUpperCase()}
            </div>
            <div className="absolute -bottom-1 -right-1 px-1.5 py-0.2 bg-[#00E5FF] text-[#080B12] font-gaming font-black text-[9px] rounded-sm">
              L{player.level}
            </div>
          </div>

          {/* User Info & XP Bar */}
          <div className="min-w-[130px]">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-semibold text-white tracking-wide truncate max-w-[110px]">
                {player.username}
              </span>
              <span className="text-[10px] font-mono text-[#94A3B8] tabular-nums">
                {xpPercentage}%
              </span>
            </div>
            {/* XP progress bar */}
            <div className="w-full h-1.5 bg-black/50 rounded-full mt-1 overflow-hidden border border-white/10">
              <div
                className="h-full bg-gradient-to-r from-[#00E5FF] to-[#A3FF12] transition-all duration-500 rounded-full"
                style={{ width: `${xpPercentage}%` }}
              />
            </div>
          </div>

          {/* ByteCoins Balance */}
          <div className="flex items-center gap-1.5 pl-3 border-l border-white/10">
            <Coins className="w-4 h-4 text-[#A3FF12]" />
            <span className="font-mono text-xs font-bold text-[#A3FF12] tabular-nums">
              {player.coins.toLocaleString()}
            </span>
          </div>
        </div>
      </header>

      {/* Center Left: Main Hero & Game Action Menu */}
      <main className="relative z-10 max-w-2xl my-auto py-8">
        {/* Title Badges and Headlines */}
        <div className="space-y-4">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-md bg-[#00E5FF]/10 border border-[#00E5FF]/30 text-xs font-mono text-[#00E5FF] tracking-wide">
            <Sparkles className="w-3.5 h-3.5" />
            <span>3D ENDLESS SPRINT ENGINE ACTIVE</span>
          </div>

          <h1 className="font-gaming font-black text-4xl sm:text-6xl lg:text-7xl tracking-tight text-white leading-none">
            CODE. <span className="text-[#00E5FF] drop-shadow-[0_0_25px_rgba(0,229,255,0.6)]">RUN.</span>{' '}
            <span className="text-[#8B5CF6]">SURVIVE.</span>
          </h1>

          <p className="text-base sm:text-lg text-[#94A3B8] max-w-xl font-normal leading-relaxed text-balance">
            Your coding journey just became an endless adventure. Dash through recursive firewalls, evade runtime bugs, and deploy zero-latency compiler shields.
          </p>
        </div>

        {/* Selected Runner Quick Badge */}
        <div className="mt-6 inline-flex items-center gap-3 bg-[#111827]/80 backdrop-blur-md border border-[#00E5FF]/30 px-3.5 py-2 rounded-lg">
          <div className="w-8 h-8 rounded overflow-hidden border border-white/20 bg-black/40">
            <img
              src={selectedCharacter.image}
              alt={selectedCharacter.name}
              className="w-full h-full object-cover"
            />
          </div>
          <div>
            <div className="text-[10px] text-[#94A3B8] font-mono uppercase tracking-wider">
              Selected Runner
            </div>
            <div className="text-xs font-gaming font-bold text-white flex items-center gap-1.5">
              <span>{selectedCharacter.name}</span>
              <span className="text-[10px] text-[#00E5FF]">[{selectedCharacter.rarity}]</span>
            </div>
          </div>
        </div>

        {/* Navigation Action Buttons (Modern AAA Stack) */}
        <div className="mt-8 flex flex-col sm:flex-row items-stretch sm:items-center gap-3.5">
          {/* Primary Big PLAY NOW Button */}
          <button
            onClick={() => handleAction(onPlay, true)}
            onMouseEnter={() => soundEngine.playHover()}
            className="group relative px-8 py-4 bg-gradient-to-r from-[#00E5FF] to-[#00B4D8] text-[#080B12] font-gaming font-black text-lg tracking-wider rounded-lg clip-chamfer shadow-[0_0_30px_rgba(0,229,255,0.45)] hover:shadow-[0_0_45px_rgba(0,229,255,0.7)] transition-all duration-200 transform hover:-translate-y-0.5 active:translate-y-0 flex items-center justify-center gap-3 cursor-pointer"
          >
            <Play className="w-5 h-5 fill-current" />
            <span>PLAY NOW</span>
            <ChevronRight className="w-5 h-5 transition-transform group-hover:translate-x-1" />
          </button>

          {/* Secondary AAA Actions */}
          <button
            onClick={() => handleAction(onOpenCharacters)}
            onMouseEnter={() => soundEngine.playHover()}
            className="px-5 py-3.5 bg-[#111827]/90 hover:bg-[#1E293B] border border-white/15 hover:border-[#8B5CF6]/60 text-white font-gaming text-xs sm:text-sm font-bold tracking-wide rounded-lg flex items-center justify-center gap-2.5 transition-all duration-200 cursor-pointer shadow-lg hover:shadow-[0_0_20px_rgba(139,92,246,0.3)]"
          >
            <Users className="w-4 h-4 text-[#8B5CF6]" />
            <span>CHARACTERS</span>
          </button>

          <button
            onClick={() => handleAction(onOpenLeaderboard)}
            onMouseEnter={() => soundEngine.playHover()}
            className="px-5 py-3.5 bg-[#111827]/90 hover:bg-[#1E293B] border border-white/15 hover:border-[#A3FF12]/60 text-white font-gaming text-xs sm:text-sm font-bold tracking-wide rounded-lg flex items-center justify-center gap-2.5 transition-all duration-200 cursor-pointer shadow-lg hover:shadow-[0_0_20px_rgba(163,255,18,0.3)]"
          >
            <Trophy className="w-4 h-4 text-[#A3FF12]" />
            <span>LEADERBOARD</span>
          </button>

          <button
            onClick={() => handleAction(onOpenSettings)}
            onMouseEnter={() => soundEngine.playHover()}
            aria-label="Game Settings"
            className="px-4 py-3.5 bg-[#111827]/90 hover:bg-[#1E293B] border border-white/15 hover:border-white/40 text-[#94A3B8] hover:text-white rounded-lg flex items-center justify-center transition-all duration-200 cursor-pointer shadow-lg"
          >
            <Settings className="w-5 h-5" />
          </button>
        </div>
      </main>

      {/* Footer Strip: Key Controls & System Telemetry */}
      <footer className="relative z-10 pt-4 border-t border-white/10 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 text-xs font-mono text-[#94A3B8]">
        {/* Controls legend */}
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-[#F8FAFC]/70 uppercase tracking-wider font-semibold">Controls:</span>
          <div className="flex items-center gap-1.5">
            <kbd className="px-1.5 py-0.5 rounded bg-black/60 border border-white/20 text-[#00E5FF] font-bold">A/D</kbd>
            <kbd className="px-1.5 py-0.5 rounded bg-black/60 border border-white/20 text-[#00E5FF] font-bold">â†/â†’</kbd>
            <span>Lanes</span>
          </div>
          <span className="text-white/20">Â·</span>
          <div className="flex items-center gap-1.5">
            <kbd className="px-1.5 py-0.5 rounded bg-black/60 border border-white/20 text-[#00E5FF] font-bold">W</kbd>
            <kbd className="px-1.5 py-0.5 rounded bg-black/60 border border-white/20 text-[#00E5FF] font-bold">SPACE</kbd>
            <span>Jump</span>
          </div>
          <span className="text-white/20">Â·</span>
          <div className="flex items-center gap-1.5">
            <kbd className="px-1.5 py-0.5 rounded bg-black/60 border border-white/20 text-[#00E5FF] font-bold">S</kbd>
            <kbd className="px-1.5 py-0.5 rounded bg-black/60 border border-white/20 text-[#00E5FF] font-bold">â†“</kbd>
            <span>Slide</span>
          </div>
        </div>

        {/* High score badge */}
        <div className="flex items-center gap-2 bg-[#111827]/70 px-3 py-1 rounded-md border border-white/10">
          <Shield className="w-3.5 h-3.5 text-[#00E5FF]" />
          <span>PERSONAL BEST:</span>
          <span className="text-white font-bold tabular-nums">
            {player.bestScore.toLocaleString()} PTS
          </span>
        </div>
      </footer>
    </div>
  );
};
