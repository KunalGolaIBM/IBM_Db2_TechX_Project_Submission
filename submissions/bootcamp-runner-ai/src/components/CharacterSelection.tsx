import React, { useState, useEffect } from 'react';
import { ChevronLeft, ChevronRight, ArrowLeft, Lock, Check, Zap, Sparkles, Coins } from 'lucide-react';
import { Character, CharacterRarity, PlayerProfile } from '../types/game';
import { soundEngine } from '../utils/audio';

interface CharacterSelectionProps {
  characters: Character[];
  selectedCharacterId: string;
  player: PlayerProfile;
  onSelectCharacter: (characterId: string) => void;
  onUnlockCharacter: (characterId: string, cost: number) => boolean;
  onBack: () => void;
}

export const CharacterSelection: React.FC<CharacterSelectionProps> = ({
  characters,
  selectedCharacterId,
  player,
  onSelectCharacter,
  onUnlockCharacter,
  onBack,
}) => {
  const [currentIndex, setCurrentIndex] = useState(() => {
    const idx = characters.findIndex((c) => c.id === selectedCharacterId);
    return idx >= 0 ? idx : 0;
  });

  const [unlockFeedback, setUnlockFeedback] = useState<string | null>(null);

  const character = characters[currentIndex];
  const isSelected = selectedCharacterId === character.id;
  const isUnlocked = player.unlockedCharacterIds.includes(character.id) || character.unlocked;

  const handleNext = () => {
    soundEngine.playClick();
    setCurrentIndex((prev) => (prev + 1) % characters.length);
  };

  const handlePrev = () => {
    soundEngine.playClick();
    setCurrentIndex((prev) => (prev - 1 + characters.length) % characters.length);
  };

  // Keyboard navigation for arrow keys
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft') handlePrev();
      if (e.key === 'ArrowRight') handleNext();
      if (e.key === 'Escape') onBack();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [currentIndex, characters.length]);

  const handleSelect = () => {
    soundEngine.playLaunch();
    onSelectCharacter(character.id);
  };

  const handleUnlock = () => {
    if (!character.unlockCost) return;
    if (player.coins < character.unlockCost) {
      setUnlockFeedback('INSUFFICIENT BYTECOINS');
      setTimeout(() => setUnlockFeedback(null), 2500);
      return;
    }
    const success = onUnlockCharacter(character.id, character.unlockCost);
    if (success) {
      soundEngine.playPowerUp();
      onSelectCharacter(character.id);
    }
  };

  const getRarityBadgeStyle = (rarity: CharacterRarity) => {
    switch (rarity) {
      case 'Mythic':
        return 'text-[#EC4899] border-[#EC4899]/50 bg-[#EC4899]/10 shadow-[0_0_15px_rgba(236,72,153,0.3)]';
      case 'Legendary':
        return 'text-[#00E5FF] border-[#00E5FF]/50 bg-[#00E5FF]/10 shadow-[0_0_15px_rgba(0,229,255,0.3)]';
      case 'Epic':
        return 'text-[#8B5CF6] border-[#8B5CF6]/50 bg-[#8B5CF6]/10 shadow-[0_0_15px_rgba(139,92,246,0.3)]';
      case 'Rare':
        return 'text-[#F59E0B] border-[#F59E0B]/50 bg-[#F59E0B]/10 shadow-[0_0_15px_rgba(245,158,11,0.3)]';
      default:
        return 'text-[#A3FF12] border-[#A3FF12]/50 bg-[#A3FF12]/10 shadow-[0_0_15px_rgba(163,255,18,0.3)]';
    }
  };

  return (
    <div className="relative w-full h-screen overflow-hidden flex flex-col justify-between p-4 sm:p-8 bg-[#080B12] select-none text-white">
      {/* Background ambient lighting matching character */}
      <div
        className="absolute inset-0 pointer-events-none transition-all duration-700 opacity-25"
        style={{
          background: `radial-gradient(circle at 40% 50%, ${character.accentColor} 0%, transparent 60%)`,
        }}
      />
      {/* Subtle scanline overlay */}
      <div
        className="absolute inset-0 pointer-events-none opacity-15"
        style={{
          backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(255,255,255,0.03) 3px)',
          backgroundSize: '100% 4px'
        }}
      />

      {/* TOP BAR: Back Navigation, Title & Coin Bank */}
      <header className="relative z-10 flex items-center justify-between pb-4 border-b border-white/10">
        <button
          onClick={() => {
            soundEngine.playClick();
            onBack();
          }}
          onMouseEnter={() => soundEngine.playHover()}
          className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-[#111827] hover:bg-[#1E293B] border border-white/15 text-[#94A3B8] hover:text-white transition-colors cursor-pointer text-xs font-mono"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>RETURN TO MENU [ESC]</span>
        </button>

        <div className="text-center hidden sm:block">
          <div className="text-[10px] font-mono text-[#00E5FF] tracking-widest uppercase">
            OPERATOR ROSTER
          </div>
          <h2 className="font-gaming font-bold text-xl tracking-wider text-white">
            CHARACTER SELECTION
          </h2>
        </div>

        {/* Player ByteCoins Balance */}
        <div className="flex items-center gap-2 bg-[#111827] px-4 py-2 rounded-lg border border-white/10 shadow-lg">
          <Coins className="w-4 h-4 text-[#A3FF12]" />
          <span className="font-mono text-sm font-bold text-[#A3FF12] tabular-nums">
            {player.coins.toLocaleString()}
          </span>
          <span className="text-[10px] font-mono text-[#94A3B8] uppercase">COINS</span>
        </div>
      </header>

      {/* MAIN BODY: Split Grid (Left Character Showcase, Right Stats & Lore) */}
      <div className="relative z-10 flex-1 grid grid-cols-1 lg:grid-cols-12 gap-6 items-center my-auto py-4 overflow-y-auto lg:overflow-visible">
        {/* LEFT COLUMN: Character Concept Display Stage (cols 1-6) */}
        <div className="lg:col-span-6 relative flex flex-col items-center justify-center">
          {/* Main Visual Frame */}
          <div className="relative w-full max-w-sm sm:max-w-md aspect-[3/4] max-h-[55vh] sm:max-h-[60vh] rounded-2xl overflow-hidden border border-white/20 shadow-2xl bg-[#111827]/80 group flex items-center justify-center">
            {/* Holographic glowing ring around the pedestal */}
            <div
              className="absolute -bottom-8 w-64 h-24 rounded-full blur-xl opacity-60 transition-colors duration-500"
              style={{ backgroundColor: character.accentColor }}
            />

            {/* Character Concept Portrait */}
            <img
              src={character.image}
              alt={character.name}
              referrerPolicy="no-referrer"
              className={`w-full h-full object-cover object-center transition-transform duration-500 group-hover:scale-105 ${
                !isUnlocked ? 'filter grayscale contrast-125 brightness-75' : ''
              }`}
            />

            {/* Locked Overlay if not unlocked */}
            {!isUnlocked && (
              <div className="absolute inset-0 bg-[#080B12]/70 backdrop-blur-xs flex flex-col items-center justify-center gap-3">
                <div className="w-16 h-16 rounded-full bg-black/80 border border-white/20 flex items-center justify-center shadow-2xl">
                  <Lock className="w-7 h-7 text-[#F59E0B]" />
                </div>
                <div className="text-center px-4">
                  <div className="font-gaming font-bold text-lg text-white">LOCKED OPERATOR</div>
                  <div className="font-mono text-xs text-[#94A3B8] mt-1">
                    Unlock requires {character.unlockCost?.toLocaleString()} ByteCoins
                  </div>
                </div>
              </div>
            )}

            {/* Floating Navigation Arrows over Portrait */}
            <button
              onClick={handlePrev}
              onMouseEnter={() => soundEngine.playHover()}
              aria-label="Previous character"
              className="absolute left-3 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-black/60 hover:bg-black/90 border border-white/20 hover:border-[#00E5FF] text-white flex items-center justify-center transition-all cursor-pointer shadow-lg active:scale-95"
            >
              <ChevronLeft className="w-6 h-6" />
            </button>
            <button
              onClick={handleNext}
              onMouseEnter={() => soundEngine.playHover()}
              aria-label="Next character"
              className="absolute right-3 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-black/60 hover:bg-black/90 border border-white/20 hover:border-[#00E5FF] text-white flex items-center justify-center transition-all cursor-pointer shadow-lg active:scale-95"
            >
              <ChevronRight className="w-6 h-6" />
            </button>

            {/* Active Selected Marker in top left */}
            {isSelected && (
              <div className="absolute top-4 left-4 flex items-center gap-1.5 px-3 py-1 rounded-md bg-[#00E5FF] text-[#080B12] font-gaming font-black text-xs shadow-lg">
                <Check className="w-4 h-4 stroke-[3]" />
                <span>ACTIVE RUNNER</span>
              </div>
            )}
          </div>
        </div>

        {/* RIGHT COLUMN: Character Specifications, Lore & Stats (cols 7-12) */}
        <div className="lg:col-span-6 flex flex-col gap-4 max-w-xl">
          {/* Header & Titles */}
          <div>
            <div className="flex items-center gap-3 mb-2">
              <span className={`px-2.5 py-0.5 rounded text-xs font-mono font-bold uppercase border ${getRarityBadgeStyle(character.rarity)}`}>
                {character.rarity}
              </span>
              <span className="text-xs font-mono text-[#94A3B8]">
                ID: {character.id}
              </span>
            </div>

            <h1 className="font-gaming font-black text-3xl sm:text-4xl text-white tracking-wide">
              {character.name}
            </h1>
            <p className="text-sm font-semibold text-[#00E5FF] mt-0.5">
              {character.title}
            </p>
            <p className="text-xs sm:text-sm text-[#94A3B8] leading-relaxed mt-2">
              {character.description}
            </p>
          </div>

          {/* Unique Passive Perk Card */}
          <div className="bg-[#111827]/90 border border-white/10 rounded-xl p-3.5 shadow-lg">
            <div className="flex items-center justify-between text-xs font-gaming font-bold text-white mb-1.5">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-[#A3FF12]" />
                <span>PASSIVE PERK: {character.passive.name}</span>
              </div>
            </div>
            <p className="text-xs text-[#CBD5E1] mb-2 leading-snug">
              {character.passive.description}
            </p>
            <div className="px-2.5 py-1 rounded bg-[#080B12] border border-white/10 font-mono text-[11px] text-[#00E5FF] truncate">
              <code>{character.passive.codeSnippet}</code>
            </div>
          </div>

          {/* Character Attribute Statistics Bars */}
          <div className="space-y-2.5 bg-[#111827]/60 border border-white/10 rounded-xl p-3.5">
            <div className="text-[11px] font-mono font-bold tracking-wider text-[#94A3B8] uppercase">
              RUNNER TELEMETRY RATINGS
            </div>

            {/* Stat Row: Speed */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs font-mono">
                <span className="text-[#94A3B8]">SPRINT VELOCITY</span>
                <span className="text-white font-bold tabular-nums">{character.stats.speed} / 100</span>
              </div>
              <div className="h-1.5 bg-black/50 rounded-full overflow-hidden border border-white/10">
                <div
                  className="h-full bg-[#00E5FF] rounded-full transition-all duration-300"
                  style={{ width: `${character.stats.speed}%` }}
                />
              </div>
            </div>

            {/* Stat Row: Jump */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs font-mono">
                <span className="text-[#94A3B8]">JUMP LATENCY & HEIGHT</span>
                <span className="text-white font-bold tabular-nums">{character.stats.jump} / 100</span>
              </div>
              <div className="h-1.5 bg-black/50 rounded-full overflow-hidden border border-white/10">
                <div
                  className="h-full bg-[#8B5CF6] rounded-full transition-all duration-300"
                  style={{ width: `${character.stats.jump}%` }}
                />
              </div>
            </div>

            {/* Stat Row: Shield Duration */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs font-mono">
                <span className="text-[#94A3B8]">COMPILER SHIELD RESILIENCE</span>
                <span className="text-white font-bold tabular-nums">{character.stats.shieldDuration} / 100</span>
              </div>
              <div className="h-1.5 bg-black/50 rounded-full overflow-hidden border border-white/10">
                <div
                  className="h-full bg-[#A3FF12] rounded-full transition-all duration-300"
                  style={{ width: `${character.stats.shieldDuration}%` }}
                />
              </div>
            </div>

            {/* Stat Row: Coin Magnet */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs font-mono">
                <span className="text-[#94A3B8]">BYTE MAGNET RADIUS</span>
                <span className="text-white font-bold tabular-nums">{character.stats.magnetRadius} / 100</span>
              </div>
              <div className="h-1.5 bg-black/50 rounded-full overflow-hidden border border-white/10">
                <div
                  className="h-full bg-[#F59E0B] rounded-full transition-all duration-300"
                  style={{ width: `${character.stats.magnetRadius}%` }}
                />
              </div>
            </div>
          </div>

          {/* Action Button: SELECT or UNLOCK */}
          <div className="pt-2">
            {isUnlocked ? (
              <button
                onClick={handleSelect}
                disabled={isSelected}
                onMouseEnter={() => !isSelected && soundEngine.playHover()}
                className={`w-full py-3.5 px-6 rounded-lg font-gaming font-bold text-sm sm:text-base tracking-wider flex items-center justify-center gap-2 transition-all ${
                  isSelected
                    ? 'bg-[#1E293B] text-[#94A3B8] border border-white/10 cursor-default'
                    : 'bg-gradient-to-r from-[#00E5FF] to-[#00B4D8] text-[#080B12] shadow-[0_0_25px_rgba(0,229,255,0.4)] hover:shadow-[0_0_35px_rgba(0,229,255,0.6)] cursor-pointer active:scale-98'
                }`}
              >
                {isSelected ? (
                  <>
                    <Check className="w-5 h-5 text-[#00E5FF]" />
                    <span>OPERATOR DEPLOYED</span>
                  </>
                ) : (
                  <>
                    <Zap className="w-5 h-5 fill-current" />
                    <span>EQUIP AS ACTIVE RUNNER</span>
                  </>
                )}
              </button>
            ) : (
              <div className="space-y-2">
                <button
                  onClick={handleUnlock}
                  onMouseEnter={() => soundEngine.playHover()}
                  className="w-full py-3.5 px-6 rounded-lg bg-gradient-to-r from-[#F59E0B] to-[#D97706] text-[#080B12] font-gaming font-bold text-sm sm:text-base tracking-wider flex items-center justify-center gap-2 shadow-[0_0_20px_rgba(245,158,11,0.4)] hover:shadow-[0_0_30px_rgba(245,158,11,0.6)] cursor-pointer active:scale-98 transition-all"
                >
                  <Lock className="w-4 h-4 fill-current" />
                  <span>UNLOCK FOR {character.unlockCost?.toLocaleString()} BYTECOINS</span>
                </button>
                {unlockFeedback && (
                  <p className="text-center font-mono text-xs text-red-400 animate-pulse">
                    {unlockFeedback}
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* BOTTOM CAROUSEL STRIP: All Characters Selector */}
      <footer className="relative z-10 pt-3 border-t border-white/10 flex items-center justify-center gap-3 overflow-x-auto py-1">
        {characters.map((item, idx) => {
          const itemUnlocked = player.unlockedCharacterIds.includes(item.id) || item.unlocked;
          const isActiveIndex = idx === currentIndex;
          return (
            <button
              key={item.id}
              onClick={() => {
                soundEngine.playClick();
                setCurrentIndex(idx);
              }}
              className={`relative flex items-center gap-2.5 px-3 py-1.5 rounded-lg border transition-all cursor-pointer whitespace-nowrap shrink-0 ${
                isActiveIndex
                  ? 'bg-[#1E293B] border-[#00E5FF] shadow-[0_0_15px_rgba(0,229,255,0.3)]'
                  : 'bg-[#111827]/70 border-white/10 hover:border-white/30 opacity-70 hover:opacity-100'
              }`}
            >
              <div className="w-8 h-8 rounded overflow-hidden bg-black/40 border border-white/10">
                <img
                  src={item.image}
                  alt={item.name}
                  className={`w-full h-full object-cover ${!itemUnlocked ? 'filter grayscale' : ''}`}
                />
              </div>
              <div className="text-left">
                <div className="text-xs font-gaming font-bold text-white flex items-center gap-1.5">
                  <span>{item.name}</span>
                  {!itemUnlocked && <Lock className="w-3 h-3 text-[#F59E0B]" />}
                </div>
                <div className="text-[10px] font-mono text-[#94A3B8]">
                  {item.rarity}
                </div>
              </div>
            </button>
          );
        })}
      </footer>
    </div>
  );
};
