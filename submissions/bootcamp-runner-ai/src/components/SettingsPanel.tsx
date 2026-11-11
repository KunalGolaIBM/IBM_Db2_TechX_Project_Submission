import React, { useState } from 'react';
import { ArrowLeft, Volume2, Monitor, Keyboard, Sliders, Check, AlertTriangle } from 'lucide-react';
import { GameSettings } from '../types/game';
import { soundEngine } from '../utils/audio';

interface SettingsPanelProps {
  settings: GameSettings;
  onUpdateSettings: (newSettings: Partial<GameSettings>) => void;
  onResetCareerData?: () => void;
  onBack: () => void;
}

type SettingsTab = 'audio' | 'graphics' | 'controls' | 'accessibility';

export const SettingsPanel: React.FC<SettingsPanelProps> = ({
  settings,
  onUpdateSettings,
  onResetCareerData,
  onBack,
}) => {
  const [activeTab, setActiveTab] = useState<SettingsTab>('audio');
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [savedNotification, setSavedNotification] = useState(false);

  const handleSettingChange = (patch: Partial<GameSettings>) => {
    onUpdateSettings(patch);
    setSavedNotification(true);
    setTimeout(() => setSavedNotification(false), 1200);
  };

  return (
    <div className="relative w-full h-screen overflow-hidden flex flex-col p-4 sm:p-8 bg-[#080B12] select-none text-white">
      {/* Background Cyber Ambient */}
      <div className="absolute inset-0 pointer-events-none opacity-20 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-[#8B5CF6]/20 via-[#080B12] to-[#080B12]" />

      {/* TOP HEADER */}
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

        <div className="text-center">
          <div className="text-[10px] font-mono text-[#00E5FF] tracking-widest uppercase">
            HARDWARE & LOGIC PREFERENCES
          </div>
          <h1 className="font-gaming font-bold text-xl sm:text-2xl tracking-wider text-white">
            SYSTEM <span className="text-[#00E5FF]">SETTINGS</span>
          </h1>
        </div>

        {/* Saved feedback pill */}
        <div className="w-32 flex justify-end">
          {savedNotification ? (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#A3FF12]/20 border border-[#A3FF12]/40 text-[#A3FF12] text-xs font-mono animate-in fade-in">
              <Check className="w-3.5 h-3.5" />
              <span>SAVED</span>
            </div>
          ) : (
            <span className="text-[11px] font-mono text-[#94A3B8]">CONFIG v3.2</span>
          )}
        </div>
      </header>

      {/* TABS SELECTOR */}
      <div className="relative z-10 flex items-center gap-2 pt-6 pb-4 border-b border-white/5 overflow-x-auto">
        <button
          onClick={() => {
            soundEngine.playClick();
            setActiveTab('audio');
          }}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-gaming text-xs font-bold tracking-wider transition-all cursor-pointer whitespace-nowrap ${
            activeTab === 'audio'
              ? 'bg-[#1E293B] border border-[#00E5FF] text-[#00E5FF] shadow-[0_0_15px_rgba(0,229,255,0.25)]'
              : 'text-[#94A3B8] hover:text-white hover:bg-white/5'
          }`}
        >
          <Volume2 className="w-4 h-4" />
          <span>AUDIO FREQUENCIES</span>
        </button>

        <button
          onClick={() => {
            soundEngine.playClick();
            setActiveTab('graphics');
          }}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-gaming text-xs font-bold tracking-wider transition-all cursor-pointer whitespace-nowrap ${
            activeTab === 'graphics'
              ? 'bg-[#1E293B] border border-[#00E5FF] text-[#00E5FF] shadow-[0_0_15px_rgba(0,229,255,0.25)]'
              : 'text-[#94A3B8] hover:text-white hover:bg-white/5'
          }`}
        >
          <Monitor className="w-4 h-4" />
          <span>GRAPHICS & POST-FX</span>
        </button>

        <button
          onClick={() => {
            soundEngine.playClick();
            setActiveTab('controls');
          }}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-gaming text-xs font-bold tracking-wider transition-all cursor-pointer whitespace-nowrap ${
            activeTab === 'controls'
              ? 'bg-[#1E293B] border border-[#00E5FF] text-[#00E5FF] shadow-[0_0_15px_rgba(0,229,255,0.25)]'
              : 'text-[#94A3B8] hover:text-white hover:bg-white/5'
          }`}
        >
          <Keyboard className="w-4 h-4" />
          <span>KEYMAP & CONTROLS</span>
        </button>

        <button
          onClick={() => {
            soundEngine.playClick();
            setActiveTab('accessibility');
          }}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-gaming text-xs font-bold tracking-wider transition-all cursor-pointer whitespace-nowrap ${
            activeTab === 'accessibility'
              ? 'bg-[#1E293B] border border-[#00E5FF] text-[#00E5FF] shadow-[0_0_15px_rgba(0,229,255,0.25)]'
              : 'text-[#94A3B8] hover:text-white hover:bg-white/5'
          }`}
        >
          <Sliders className="w-4 h-4" />
          <span>ACCESSIBILITY & DATA</span>
        </button>
      </div>

      {/* TAB CONTENT AREA */}
      <div className="relative z-10 flex-1 overflow-y-auto py-6 max-w-3xl mx-auto w-full">
        {/* TAB 1: AUDIO */}
        {activeTab === 'audio' && (
          <div className="space-y-6">
            {/* Master Volume */}
            <div className="bg-[#111827] border border-white/10 rounded-xl p-5">
              <div className="flex justify-between items-center mb-2">
                <div>
                  <div className="text-sm font-gaming font-bold text-white">MASTER VOLUME</div>
                  <div className="text-xs text-[#94A3B8]">Overall audio mix gain</div>
                </div>
                <span className="font-mono text-base font-bold text-[#00E5FF] tabular-nums">
                  {settings.masterVolume}%
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={settings.masterVolume}
                onChange={(e) => {
                  const val = Number(e.target.value);
                  handleSettingChange({ masterVolume: val });
                  soundEngine.updateVolumes(val, settings.sfxVolume);
                }}
                className="w-full accent-[#00E5FF] cursor-pointer h-2 bg-black/50 rounded-lg"
              />
            </div>

            {/* SFX Volume */}
            <div className="bg-[#111827] border border-white/10 rounded-xl p-5">
              <div className="flex justify-between items-center mb-2">
                <div>
                  <div className="text-sm font-gaming font-bold text-white">SFX & FEEDBACK</div>
                  <div className="text-xs text-[#94A3B8]">Footsteps, jet boosts, coin chimes, shields</div>
                </div>
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => {
                      soundEngine.playPowerUp();
                    }}
                    className="px-2 py-1 rounded bg-[#1E293B] hover:bg-[#334155] text-[10px] font-mono text-[#00E5FF] border border-[#00E5FF]/30 cursor-pointer"
                  >
                    Test SFX
                  </button>
                  <span className="font-mono text-base font-bold text-[#A3FF12] tabular-nums">
                    {settings.sfxVolume}%
                  </span>
                </div>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={settings.sfxVolume}
                onChange={(e) => {
                  const val = Number(e.target.value);
                  handleSettingChange({ sfxVolume: val });
                  soundEngine.updateVolumes(settings.masterVolume, val);
                }}
                className="w-full accent-[#A3FF12] cursor-pointer h-2 bg-black/50 rounded-lg"
              />
            </div>

            {/* Music Volume */}
            <div className="bg-[#111827] border border-white/10 rounded-xl p-5">
              <div className="flex justify-between items-center mb-2">
                <div>
                  <div className="text-sm font-gaming font-bold text-white">ELECTRONIC SYNTHWAVE MUSIC</div>
                  <div className="text-xs text-[#94A3B8]">Dynamic cyberpunk soundtrack intensity</div>
                </div>
                <span className="font-mono text-base font-bold text-[#8B5CF6] tabular-nums">
                  {settings.musicVolume}%
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={settings.musicVolume}
                onChange={(e) => handleSettingChange({ musicVolume: Number(e.target.value) })}
                className="w-full accent-[#8B5CF6] cursor-pointer h-2 bg-black/50 rounded-lg"
              />
            </div>
          </div>
        )}

        {/* TAB 2: GRAPHICS & POST-FX */}
        {activeTab === 'graphics' && (
          <div className="space-y-6">
            {/* Graphics Preset */}
            <div className="bg-[#111827] border border-white/10 rounded-xl p-5">
              <div className="mb-3">
                <div className="text-sm font-gaming font-bold text-white">VISUAL FIDELITY PRESET</div>
                <div className="text-xs text-[#94A3B8]">Configures shaders, bloom, particle counts, and volumetric fog</div>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {(['Low', 'Medium', 'High', 'Ultra'] as const).map((level) => (
                  <button
                    key={level}
                    onClick={() => {
                      soundEngine.playClick();
                      handleSettingChange({ graphicsQuality: level });
                    }}
                    className={`py-2.5 px-3 rounded-lg font-gaming text-xs font-bold tracking-wider transition-all cursor-pointer ${
                      settings.graphicsQuality === level
                        ? 'bg-[#00E5FF] text-[#080B12] shadow-[0_0_15px_rgba(0,229,255,0.4)]'
                        : 'bg-[#1E293B] text-[#94A3B8] hover:text-white border border-white/5'
                    }`}
                  >
                    {level.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>

            {/* Target Framerate */}
            <div className="bg-[#111827] border border-white/10 rounded-xl p-5">
              <div className="mb-3">
                <div className="text-sm font-gaming font-bold text-white">TARGET FRAMERATE CAP</div>
                <div className="text-xs text-[#94A3B8]">Lock refresh rate to reduce GPU thermals or unlock for high-Hz displays</div>
              </div>
              <div className="grid grid-cols-4 gap-2">
                {([60, 120, 144, 0] as const).map((fps) => (
                  <button
                    key={fps}
                    onClick={() => {
                      soundEngine.playClick();
                      handleSettingChange({ fpsTarget: fps });
                    }}
                    className={`py-2 px-3 rounded-lg font-mono text-xs font-bold transition-all cursor-pointer ${
                      settings.fpsTarget === fps
                        ? 'bg-[#8B5CF6] text-white shadow-[0_0_15px_rgba(139,92,246,0.4)]'
                        : 'bg-[#1E293B] text-[#94A3B8] hover:text-white border border-white/5'
                    }`}
                  >
                    {fps === 0 ? 'UNCAPPED' : `${fps} FPS`}
                  </button>
                ))}
              </div>
            </div>

            {/* Screen Shake & Motion Blur */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="bg-[#111827] border border-white/10 rounded-xl p-4 flex items-center justify-between">
                <div>
                  <div className="text-xs font-gaming font-bold text-white">SCREEN SHAKE</div>
                  <div className="text-[11px] text-[#94A3B8]">Impact vibrations during collisions</div>
                </div>
                <button
                  onClick={() => handleSettingChange({ screenShake: !settings.screenShake })}
                  className={`w-12 h-6 rounded-full transition-colors relative cursor-pointer ${
                    settings.screenShake ? 'bg-[#00E5FF]' : 'bg-black/60'
                  }`}
                >
                  <div
                    className={`w-5 h-5 rounded-full bg-white transition-transform ${
                      settings.screenShake ? 'translate-x-6' : 'translate-x-0.5'
                    }`}
                  />
                </button>
              </div>

              <div className="bg-[#111827] border border-white/10 rounded-xl p-4 flex items-center justify-between">
                <div>
                  <div className="text-xs font-gaming font-bold text-white">MOTION BLUR</div>
                  <div className="text-[11px] text-[#94A3B8]">High-speed warp velocity streaks</div>
                </div>
                <button
                  onClick={() => handleSettingChange({ motionBlur: !settings.motionBlur })}
                  className={`w-12 h-6 rounded-full transition-colors relative cursor-pointer ${
                    settings.motionBlur ? 'bg-[#00E5FF]' : 'bg-black/60'
                  }`}
                >
                  <div
                    className={`w-5 h-5 rounded-full bg-white transition-transform ${
                      settings.motionBlur ? 'translate-x-6' : 'translate-x-0.5'
                    }`}
                  />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: CONTROLS & BINDINGS */}
        {activeTab === 'controls' && (
          <div className="space-y-4">
            <div className="bg-[#111827] border border-white/10 rounded-xl p-5">
              <div className="text-xs font-mono text-[#00E5FF] uppercase tracking-wider mb-1">
                HARDWARE INPUT MAP
              </div>
              <h2 className="text-lg font-gaming font-bold text-white mb-4">
                DEFAULT RUNNER KEYBINDINGS
              </h2>

              <div className="space-y-3 font-mono text-xs">
                <div className="flex items-center justify-between py-2 border-b border-white/5">
                  <span className="text-[#94A3B8]">DASH LEFT (LANE SWITCH)</span>
                  <div className="flex gap-2">
                    <kbd className="px-2.5 py-1 rounded bg-[#080B12] border border-white/20 text-[#00E5FF] font-bold">A</kbd>
                    <kbd className="px-2.5 py-1 rounded bg-[#080B12] border border-white/20 text-[#00E5FF] font-bold">LEFT ARROW</kbd>
                  </div>
                </div>

                <div className="flex items-center justify-between py-2 border-b border-white/5">
                  <span className="text-[#94A3B8]">DASH RIGHT (LANE SWITCH)</span>
                  <div className="flex gap-2">
                    <kbd className="px-2.5 py-1 rounded bg-[#080B12] border border-white/20 text-[#00E5FF] font-bold">D</kbd>
                    <kbd className="px-2.5 py-1 rounded bg-[#080B12] border border-white/20 text-[#00E5FF] font-bold">RIGHT ARROW</kbd>
                  </div>
                </div>

                <div className="flex items-center justify-between py-2 border-b border-white/5">
                  <span className="text-[#94A3B8]">HIGH JUMP & VAULT</span>
                  <div className="flex gap-2">
                    <kbd className="px-2.5 py-1 rounded bg-[#080B12] border border-white/20 text-[#A3FF12] font-bold">W</kbd>
                    <kbd className="px-2.5 py-1 rounded bg-[#080B12] border border-white/20 text-[#A3FF12] font-bold">UP ARROW</kbd>
                    <kbd className="px-3 py-1 rounded bg-[#080B12] border border-white/20 text-[#A3FF12] font-bold">SPACE</kbd>
                  </div>
                </div>

                <div className="flex items-center justify-between py-2 border-b border-white/5">
                  <span className="text-[#94A3B8]">SLIDE & PHASE DODGE</span>
                  <div className="flex gap-2">
                    <kbd className="px-2.5 py-1 rounded bg-[#080B12] border border-white/20 text-[#8B5CF6] font-bold">S</kbd>
                    <kbd className="px-2.5 py-1 rounded bg-[#080B12] border border-white/20 text-[#8B5CF6] font-bold">DOWN ARROW</kbd>
                  </div>
                </div>

                <div className="flex items-center justify-between py-2 border-b border-white/5">
                  <span className="text-[#94A3B8]">PAUSE EXECUTION</span>
                  <div className="flex gap-2">
                    <kbd className="px-2.5 py-1 rounded bg-[#080B12] border border-white/20 text-white font-bold">ESC</kbd>
                    <kbd className="px-2.5 py-1 rounded bg-[#080B12] border border-white/20 text-white font-bold">P</kbd>
                  </div>
                </div>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-[#00E5FF]/5 border border-[#00E5FF]/20 text-xs text-[#94A3B8] font-mono leading-relaxed">
              * Note: Mobile and touch screen devices automatically render on-screen directional touch targets during gameplay.
            </div>
          </div>
        )}

        {/* TAB 4: ACCESSIBILITY & DATA */}
        {activeTab === 'accessibility' && (
          <div className="space-y-6">
            <div className="bg-[#111827] border border-white/10 rounded-xl p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm font-gaming font-bold text-white">HIGH CONTRAST HUD</div>
                  <div className="text-xs text-[#94A3B8]">Enforces opaque solid backdrops on telemetry meters</div>
                </div>
                <button
                  onClick={() => handleSettingChange({ highContrastHud: !settings.highContrastHud })}
                  className={`w-12 h-6 rounded-full transition-colors relative cursor-pointer ${
                    settings.highContrastHud ? 'bg-[#00E5FF]' : 'bg-black/60'
                  }`}
                >
                  <div
                    className={`w-5 h-5 rounded-full bg-white transition-transform ${
                      settings.highContrastHud ? 'translate-x-6' : 'translate-x-0.5'
                    }`}
                  />
                </button>
              </div>

              <div className="flex items-center justify-between pt-3 border-t border-white/5">
                <div>
                  <div className="text-sm font-gaming font-bold text-white">REDUCED MOTION</div>
                  <div className="text-xs text-[#94A3B8]">Minimizes camera bobbing and fast background oscillation</div>
                </div>
                <button
                  onClick={() => handleSettingChange({ reducedMotion: !settings.reducedMotion })}
                  className={`w-12 h-6 rounded-full transition-colors relative cursor-pointer ${
                    settings.reducedMotion ? 'bg-[#00E5FF]' : 'bg-black/60'
                  }`}
                >
                  <div
                    className={`w-5 h-5 rounded-full bg-white transition-transform ${
                      settings.reducedMotion ? 'translate-x-6' : 'translate-x-0.5'
                    }`}
                  />
                </button>
              </div>
            </div>

            {/* Reset Data Warning Box */}
            <div className="bg-red-950/20 border border-red-500/30 rounded-xl p-5">
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
                <div className="flex-1">
                  <div className="text-sm font-gaming font-bold text-red-400">DATA FLUSH / CAREER RESET</div>
                  <p className="text-xs text-[#94A3B8] mt-1 mb-3">
                    Resets unlocked operators, high scores, and ByteCoin balances back to new installation state.
                  </p>

                  {showResetConfirm ? (
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => {
                          onResetCareerData?.();
                          setShowResetConfirm(false);
                          setSavedNotification(true);
                        }}
                        className="px-3.5 py-1.5 rounded bg-red-600 hover:bg-red-500 text-white font-mono text-xs font-bold cursor-pointer"
                      >
                        CONFIRM COMPLETE PURGE
                      </button>
                      <button
                        onClick={() => setShowResetConfirm(false)}
                        className="px-3.5 py-1.5 rounded bg-[#1E293B] text-[#94A3B8] font-mono text-xs cursor-pointer"
                      >
                        CANCEL
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setShowResetConfirm(true)}
                      className="px-3 py-1.5 rounded bg-[#1E293B] hover:bg-red-900/40 border border-red-500/30 text-red-300 font-mono text-xs cursor-pointer transition-colors"
                    >
                      RESET CAREER PROGRESS
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
