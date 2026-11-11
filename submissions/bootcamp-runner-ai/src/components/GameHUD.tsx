import React from 'react';
import { Pause, Shield, Zap, Magnet, Cpu, Coins, Flame, ArrowUp, ArrowDown, ArrowLeft, ArrowRight } from 'lucide-react';
import { GameHUDState } from '../types/game';
import { soundEngine } from '../utils/audio';

interface GameHUDProps {
  hudState: GameHUDState;
  onPause: () => void;
  onMoveLeft?: () => void;
  onMoveRight?: () => void;
  onJump?: () => void;
  onSlide?: () => void;
  // Optional simulated actions for testing/previewing before 3D engine hooks
  onTriggerDamage?: () => void;
  onTriggerCoin?: () => void;
  onTriggerPowerUp?: (type: 'shield' | 'magnet' | 'multiplier' | 'overclock') => void;
  onSimulateCrash?: () => void;
  showDevToolbar?: boolean;
}

export const GameHUD: React.FC<GameHUDProps> = ({
  hudState,
  onPause,
  onMoveLeft,
  onMoveRight,
  onJump,
  onSlide,
  onTriggerDamage,
  onTriggerCoin,
  onTriggerPowerUp,
  onSimulateCrash,
  showDevToolbar = true,
}) => {
  const getPowerUpIcon = (type: string) => {
    switch (type) {
      case 'shield':
        return <Shield className="w-4 h-4 text-[#00E5FF]" />;
      case 'magnet':
        return <Magnet className="w-4 h-4 text-[#A3FF12]" />;
      case 'multiplier':
        return <Flame className="w-4 h-4 text-[#F59E0B]" />;
      case 'overclock':
        return <Cpu className="w-4 h-4 text-[#8B5CF6]" />;
      default:
        return <Zap className="w-4 h-4 text-[#00E5FF]" />;
    }
  };

  const getPowerUpBorder = (type: string) => {
    switch (type) {
      case 'shield':
        return 'border-[#00E5FF]/50 bg-[#00E5FF]/10 text-[#00E5FF]';
      case 'magnet':
        return 'border-[#A3FF12]/50 bg-[#A3FF12]/10 text-[#A3FF12]';
      case 'multiplier':
        return 'border-[#F59E0B]/50 bg-[#F59E0B]/10 text-[#F59E0B]';
      case 'overclock':
        return 'border-[#8B5CF6]/50 bg-[#8B5CF6]/10 text-[#8B5CF6]';
      default:
        return 'border-white/30 bg-white/10 text-white';
    }
  };

  return (
    <div className="absolute inset-0 z-20 pointer-events-none flex flex-col justify-between p-4 sm:p-6 select-none overflow-hidden">
      {/* TOP HUD BAR */}
      <div className="w-full flex items-start justify-between gap-4 pointer-events-auto">
        {/* Left: Stage Level & Health Integrity */}
        <div className="flex flex-col gap-2">
          {/* Level Badge */}
          <div className="flex items-center gap-2 bg-[#111827]/85 backdrop-blur-md px-3.5 py-1.5 rounded-lg border border-white/10 shadow-lg">
            <div className="w-2 h-2 rounded-full bg-[#00E5FF] animate-pulse" />
            <div className="font-mono text-xs uppercase tracking-wider text-white">
              <span className="text-[#94A3B8]">STAGE {hudState.currentLevel.toString().padStart(2, '0')} // </span>
              <span className="text-[#00E5FF] font-semibold">{hudState.levelName}</span>
            </div>
          </div>

          {/* Health / Shield Bar */}
          <div className="bg-[#111827]/85 backdrop-blur-md px-3 py-1.5 rounded-lg border border-white/10 shadow-lg w-44">
            <div className="flex justify-between items-center text-[10px] font-mono text-[#94A3B8] mb-1">
              <span>SYSTEM INTEGRITY</span>
              <span className="text-white font-bold">{hudState.health}%</span>
            </div>
            <div className="w-full h-1.5 bg-black/60 rounded-full overflow-hidden border border-white/10">
              <div
                className={`h-full transition-all duration-300 rounded-full ${
                  hudState.health > 50
                    ? 'bg-gradient-to-r from-[#00E5FF] to-[#A3FF12]'
                    : hudState.health > 25
                    ? 'bg-[#F59E0B]'
                    : 'bg-red-500 animate-pulse'
                }`}
                style={{ width: `${hudState.health}%` }}
              />
            </div>
          </div>
        </div>

        {/* Center: Dominant Score & Distance Metric (The AAA centerpiece) */}
        <div className="flex flex-col items-center">
          <div className="bg-[#111827]/90 backdrop-blur-md px-6 py-2 rounded-xl border border-[#00E5FF]/40 shadow-[0_0_25px_rgba(0,229,255,0.25)] flex flex-col items-center min-w-[200px]">
            <span className="text-[10px] font-mono tracking-widest text-[#94A3B8] uppercase">
              SCORE
            </span>
            <span className="font-gaming font-black text-2xl sm:text-3xl text-white tracking-wider tabular-nums drop-shadow-[0_0_12px_rgba(0,229,255,0.7)]">
              {hudState.score.toLocaleString()}
            </span>
            <div className="flex items-center gap-2 mt-0.5 text-xs font-mono text-[#94A3B8]">
              <span>DIST:</span>
              <span className="text-white font-semibold tabular-nums">{hudState.distance.toLocaleString()} m</span>
            </div>
          </div>
        </div>

        {/* Right: Coins, Multiplier Combo, & Pause Button */}
        <div className="flex items-center gap-3">
          {/* ByteCoins */}
          <div className="flex items-center gap-2 bg-[#111827]/85 backdrop-blur-md px-3.5 py-2 rounded-lg border border-white/10 shadow-lg">
            <Coins className="w-4 h-4 text-[#A3FF12]" />
            <span className="font-mono text-sm font-bold text-[#A3FF12] tabular-nums">
              {hudState.coins.toLocaleString()}
            </span>
          </div>

          {/* Combo Multiplier Meter */}
          <div className={`flex items-center gap-1.5 bg-[#111827]/85 backdrop-blur-md px-3 py-2 rounded-lg border shadow-lg ${
            hudState.multiplier > 1
              ? 'border-[#F59E0B]/60 text-[#F59E0B] shadow-[0_0_15px_rgba(245,158,11,0.3)]'
              : 'border-white/10 text-[#94A3B8]'
          }`}>
            <Flame className={`w-4 h-4 ${hudState.multiplier > 1 ? 'animate-bounce text-[#F59E0B]' : ''}`} />
            <span className="font-gaming font-bold text-sm tracking-wide tabular-nums">
              x{hudState.multiplier}
            </span>
          </div>

          {/* Pause Button */}
          <button
            onClick={() => {
              soundEngine.playPause();
              onPause();
            }}
            onMouseEnter={() => soundEngine.playHover()}
            title="Pause Game (ESC / P)"
            className="w-10 h-10 rounded-lg bg-[#111827]/90 hover:bg-[#1E293B] border border-white/20 hover:border-[#00E5FF]/60 text-white flex items-center justify-center transition-all duration-150 cursor-pointer shadow-lg active:scale-95"
          >
            <Pause className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* MIDDLE LATERAL: Active Power-Ups Stack */}
      <div className="flex flex-col gap-2.5 max-w-xs pointer-events-auto">
        {hudState.activePowerUps.map((power) => {
          const percent = Math.max(0, Math.min(100, (power.durationRemaining / power.maxDuration) * 100));
          return (
            <div
              key={power.id}
              className={`flex items-center gap-3 px-3 py-1.5 rounded-lg border backdrop-blur-md shadow-md transition-all ${getPowerUpBorder(
                power.type
              )}`}
            >
              <div className="p-1 rounded bg-black/40">
                {getPowerUpIcon(power.type)}
              </div>
              <div className="flex-1 min-w-[90px]">
                <div className="flex justify-between items-center text-[10px] font-mono font-bold uppercase">
                  <span>{power.name}</span>
                  <span className="tabular-nums">00:{Math.ceil(power.durationRemaining).toString().padStart(2, '0')}s</span>
                </div>
                <div className="w-full h-1 bg-black/40 rounded-full mt-1 overflow-hidden">
                  <div
                    className="h-full bg-current rounded-full transition-all duration-200"
                    style={{ width: `${percent}%` }}
                  />
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* BOTTOM CONTROLS & DEV TEST HARNESS */}
      <div className="w-full flex flex-col items-center gap-3">
        {/* On-screen Mobile Controls (rendered subtly or touch friendly) */}
        <div className="sm:hidden flex items-center justify-between w-full max-w-xs px-2 pointer-events-auto">
          <div className="flex gap-2">
            <button aria-label="Move left" onClick={onMoveLeft} className="w-12 h-12 rounded-xl bg-[#111827]/80 backdrop-blur-md border border-white/20 flex items-center justify-center active:bg-[#00E5FF]/30 active:scale-95 text-white">
              <ArrowLeft className="w-6 h-6" />
            </button>
            <button aria-label="Move right" onClick={onMoveRight} className="w-12 h-12 rounded-xl bg-[#111827]/80 backdrop-blur-md border border-white/20 flex items-center justify-center active:bg-[#00E5FF]/30 active:scale-95 text-white">
              <ArrowRight className="w-6 h-6" />
            </button>
          </div>
          <div className="flex gap-2">
            <button aria-label="Jump" onClick={onJump} className="w-12 h-12 rounded-xl bg-[#111827]/80 backdrop-blur-md border border-white/20 flex items-center justify-center active:bg-[#00E5FF]/30 active:scale-95 text-white">
              <ArrowUp className="w-6 h-6" />
            </button>
            <button aria-label="Slide" onClick={onSlide} className="w-12 h-12 rounded-xl bg-[#111827]/80 backdrop-blur-md border border-white/20 flex items-center justify-center active:bg-[#00E5FF]/30 active:scale-95 text-white">
              <ArrowDown className="w-6 h-6" />
            </button>
          </div>
        </div>

        {/* Developer / Engine Test Strip (Allows testing the HUD states, power-ups, taking damage, and simulating crash to show Results) */}
        {showDevToolbar && (
          <div className="pointer-events-auto bg-[#111827]/90 backdrop-blur-md border border-white/10 px-4 py-2 rounded-xl shadow-2xl flex flex-wrap items-center justify-center gap-3 text-xs">
            <span className="font-mono text-[10px] text-[#94A3B8] uppercase tracking-wider hidden sm:inline">
              HUD SIMULATOR:
            </span>

            <button
              onClick={() => {
                soundEngine.playCoin();
                onTriggerCoin?.();
              }}
              className="px-2.5 py-1 rounded bg-[#1E293B] hover:bg-[#334155] border border-white/10 text-[#A3FF12] font-mono text-[11px] flex items-center gap-1 cursor-pointer transition-colors"
            >
              <Coins className="w-3 h-3" />
              <span>+Coin</span>
            </button>

            <button
              onClick={() => {
                soundEngine.playPowerUp();
                onTriggerPowerUp?.('shield');
              }}
              className="px-2.5 py-1 rounded bg-[#1E293B] hover:bg-[#334155] border border-[#00E5FF]/30 text-[#00E5FF] font-mono text-[11px] flex items-center gap-1 cursor-pointer transition-colors"
            >
              <Shield className="w-3 h-3" />
              <span>+Shield</span>
            </button>

            <button
              onClick={() => {
                soundEngine.playPowerUp();
                onTriggerPowerUp?.('multiplier');
              }}
              className="px-2.5 py-1 rounded bg-[#1E293B] hover:bg-[#334155] border border-[#F59E0B]/30 text-[#F59E0B] font-mono text-[11px] flex items-center gap-1 cursor-pointer transition-colors"
            >
              <Flame className="w-3 h-3" />
              <span>+2x Combo</span>
            </button>

            <button
              onClick={() => onTriggerDamage?.()}
              className="px-2.5 py-1 rounded bg-[#1E293B] hover:bg-[#334155] border border-red-500/30 text-red-400 font-mono text-[11px] cursor-pointer transition-colors"
            >
              Hit Bug (-25% HP)
            </button>

            <button
              onClick={() => onSimulateCrash?.()}
              className="px-3 py-1 rounded bg-red-600/80 hover:bg-red-500 text-white font-mono font-bold text-[11px] cursor-pointer transition-colors shadow-sm"
            >
              Trigger Game Over
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
