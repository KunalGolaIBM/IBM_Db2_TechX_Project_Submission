/**
 * BOOTCAMP RUNNER — AAA Frontend Architecture
 * Seamlessly integrates with Three.js / WebGL endless runner engine.
 */

import { useState, useEffect } from 'react';
import { GameScreen, GameHUDState, RunResults, PlayerProfile, GameSettings } from './types/game';
import { CHARACTERS_DATA } from './data/characters';
import { MainMenu } from './components/MainMenu';
import { GameHUD } from './components/GameHUD';
import { PauseMenu } from './components/PauseMenu';
import { CharacterSelection } from './components/CharacterSelection';
import { Leaderboard } from './components/Leaderboard';
import { SettingsPanel } from './components/SettingsPanel';
import { ResultsScreen } from './components/ResultsScreen';
import { ThreeRunnerGame } from './components/ThreeRunnerGame';
import { soundEngine } from './utils/audio';

const STORAGE_KEY_PROFILE = 'bootcamp_runner_profile_v1';
const STORAGE_KEY_SETTINGS = 'bootcamp_runner_settings_v1';

const DEFAULT_PROFILE: PlayerProfile = {
  username: 'DevRunner_0x9A',
  level: 42,
  xp: 14250,
  nextLevelXp: 20000,
  coins: 18450,
  selectedCharacterId: 'char-script-ninja',
  unlockedCharacterIds: ['char-junior-debugger', 'char-script-ninja'],
  bestScore: 238900,
  totalDistance: 48900,
  totalRuns: 64,
};

const DEFAULT_SETTINGS: GameSettings = {
  masterVolume: 80,
  sfxVolume: 85,
  musicVolume: 75,
  graphicsQuality: 'High',
  fpsTarget: 120,
  screenShake: true,
  motionBlur: true,
  highContrastHud: false,
  reducedMotion: false,
};

export default function App() {
  const [screen, setScreen] = useState<GameScreen>('MENU');

  // Player Profile with LocalStorage persistence
  const [player, setPlayer] = useState<PlayerProfile>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY_PROFILE);
      return saved ? JSON.parse(saved) : DEFAULT_PROFILE;
    } catch {
      return DEFAULT_PROFILE;
    }
  });

  // Settings with LocalStorage persistence
  const [settings, setSettings] = useState<GameSettings>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY_SETTINGS);
      return saved ? JSON.parse(saved) : DEFAULT_SETTINGS;
    } catch {
      return DEFAULT_SETTINGS;
    }
  });

  // Active in-game HUD telemetry
  const [hudState, setHudState] = useState<GameHUDState>({
    score: 0,
    distance: 0,
    coins: 0,
    currentLevel: 1,
    levelName: 'KERNEL CORRIDOR',
    combo: 1,
    multiplier: 1,
    obstaclesAvoided: 0,
    health: 100,
    maxHealth: 100,
    activePowerUps: [
      {
        id: 'p-1',
        type: 'shield',
        name: 'COMPILER SHIELD',
        durationRemaining: 10,
        maxDuration: 10,
        iconName: 'Shield',
      },
    ],
  });

  // Last run results for ResultsScreen
  const [lastResults, setLastResults] = useState<RunResults | null>(null);

  // Sync sound engine volume
  useEffect(() => {
    soundEngine.updateVolumes(settings.masterVolume, settings.sfxVolume);
  }, [settings.masterVolume, settings.sfxVolume]);

  // Persist Profile
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY_PROFILE, JSON.stringify(player));
    } catch {}
  }, [player]);

  // Persist Settings
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY_SETTINGS, JSON.stringify(settings));
    } catch {}
  }, [settings]);

  // Selected character lookup
  const selectedCharacter =
    CHARACTERS_DATA.find((c) => c.id === player.selectedCharacterId) || CHARACTERS_DATA[0];

  // Global Keyboard Shortcuts (Pause, Escape)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' || e.key === 'p' || e.key === 'P') {
        if (screen === 'PLAYING') {
          soundEngine.playPause();
          setScreen('PAUSED');
        } else if (screen === 'PAUSED') {
          soundEngine.playClick();
          setScreen('PLAYING');
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [screen]);

  // Game Loop Handlers
  const handleStartGame = () => {
    setHudState({
      score: 0,
      distance: 0,
      coins: 0,
      currentLevel: 1,
      levelName: 'KERNEL CORRIDOR',
      combo: 1,
      multiplier: 1,
      obstaclesAvoided: 0,
      health: 100,
      maxHealth: 100,
      activePowerUps: [
        {
          id: `p-${Date.now()}`,
          type: 'shield',
          name: 'BOOT SHIELD',
          durationRemaining: 10,
          maxDuration: 10,
          iconName: 'Shield',
        },
      ],
    });
    setScreen('PLAYING');
  };

  const handleScoreUpdate = (score: number, distance: number, coins: number, multiplier: number) => {
    setHudState((prev) => {
      // Stage progression based on distance
      let currentLevel = prev.currentLevel;
      let levelName = prev.levelName;
      if (distance > 3000) {
        currentLevel = 4;
        levelName = 'QUANTUM CORE';
      } else if (distance > 1800) {
        currentLevel = 3;
        levelName = 'DATA HIGHWAY';
      } else if (distance > 800) {
        currentLevel = 2;
        levelName = 'SYNTAX LABYRINTH';
      }

      return {
        ...prev,
        score,
        distance,
        coins,
        multiplier,
        currentLevel,
        levelName,
      };
    });
  };

  const handleGameOver = (finalScore: number, distance: number, coinsEarned: number, obstaclesAvoided: number) => {
    const isNewBest = finalScore > player.bestScore;
    const finalBest = Math.max(finalScore, player.bestScore);
    const xpGained = Math.round(distance * 0.4 + coinsEarned * 5 + finalScore * 0.02);

    const results: RunResults = {
      finalScore,
      distance,
      coins: coinsEarned,
      obstaclesAvoided,
      bestScore: finalBest,
      isNewHighScore: isNewBest,
      xpEarned: xpGained,
      characterId: selectedCharacter.id,
      characterName: selectedCharacter.name,
      timestamp: Date.now(),
    };

    setLastResults(results);

    // Update Player Progression
    setPlayer((prev) => {
      let nextXp = prev.xp + xpGained;
      let nextLvl = prev.level;
      let nextLvlTarget = prev.nextLevelXp;

      while (nextXp >= nextLvlTarget) {
        nextXp -= nextLvlTarget;
        nextLvl += 1;
        nextLvlTarget = Math.round(nextLvlTarget * 1.2);
      }

      return {
        ...prev,
        coins: prev.coins + coinsEarned,
        xp: nextXp,
        level: nextLvl,
        nextLevelXp: nextLvlTarget,
        bestScore: finalBest,
        totalDistance: prev.totalDistance + distance,
        totalRuns: prev.totalRuns + 1,
      };
    });

    setScreen('RESULTS');
  };

  const handleSelectCharacter = (characterId: string) => {
    setPlayer((prev) => ({
      ...prev,
      selectedCharacterId: characterId,
    }));
  };

  const handleUnlockCharacter = (characterId: string, cost: number): boolean => {
    if (player.coins < cost) return false;
    setPlayer((prev) => ({
      ...prev,
      coins: prev.coins - cost,
      unlockedCharacterIds: [...prev.unlockedCharacterIds, characterId],
      selectedCharacterId: characterId,
    }));
    return true;
  };

  const handleResetCareerData = () => {
    localStorage.removeItem(STORAGE_KEY_PROFILE);
    setPlayer(DEFAULT_PROFILE);
  };

  return (
    <div className="relative w-full h-screen bg-[#080B12] text-[#F8FAFC] overflow-hidden">
      {/* VIEW: MAIN MENU */}
      {screen === 'MENU' && (
        <MainMenu
          player={player}
          selectedCharacter={selectedCharacter}
          onPlay={handleStartGame}
          onOpenCharacters={() => setScreen('CHARACTERS')}
          onOpenLeaderboard={() => setScreen('LEADERBOARD')}
          onOpenSettings={() => setScreen('SETTINGS')}
        />
      )}

      {/* VIEW: PLAYING or PAUSED (3D Runner Canvas + Game HUD Overlay) */}
      {(screen === 'PLAYING' || screen === 'PAUSED') && (
        <div className="relative w-full h-full">
          {/* Real 3D Endless Runner Scene with Visible Runner Person */}
          <ThreeRunnerGame
            key={selectedCharacter.id}
            selectedCharacter={selectedCharacter}
            settings={settings}
            isPaused={screen === 'PAUSED'}
            onScoreUpdate={handleScoreUpdate}
            onDamage={(hp) => setHudState((prev) => ({ ...prev, health: hp }))}
            onGameOver={handleGameOver}
            onPowerUpCollect={(type) => {
              setHudState((prev) => ({
                ...prev,
                activePowerUps: [
                  ...prev.activePowerUps.filter((p) => p.type !== type),
                  {
                    id: `p-${Date.now()}`,
                    type,
                    name: type === 'shield' ? 'COMPILER SHIELD' : type === 'multiplier' ? '2X MULTIPLIER' : 'BYTE MAGNET',
                    durationRemaining: 12,
                    maxDuration: 12,
                    iconName: type === 'shield' ? 'Shield' : 'Zap',
                  },
                ],
              }));
            }}
            activePowerUps={hudState.activePowerUps}
          />

          {/* Game HUD Overlay */}
          <GameHUD
            hudState={hudState}
            onPause={() => setScreen('PAUSED')}
            onTriggerDamage={() => {
              setHudState((prev) => {
                const nextHp = Math.max(0, prev.health - 25);
                if (nextHp <= 0) {
                  setTimeout(() => handleGameOver(prev.score, prev.distance, prev.coins, prev.obstaclesAvoided), 200);
                }
                return { ...prev, health: nextHp };
              });
            }}
            onTriggerCoin={() => {
              setHudState((prev) => ({
                ...prev,
                coins: prev.coins + 1,
                score: prev.score + 50 * prev.multiplier,
              }));
            }}
            onTriggerPowerUp={(type) => {
              setHudState((prev) => {
                const existing = prev.activePowerUps.filter((p) => p.type !== type);
                return {
                  ...prev,
                  multiplier: type === 'multiplier' ? prev.multiplier + 1 : prev.multiplier,
                  activePowerUps: [
                    ...existing,
                    {
                      id: `p-${Date.now()}`,
                      type,
                      name: type === 'shield' ? 'COMPILER SHIELD' : type === 'multiplier' ? '2X MULTIPLIER' : 'BYTE MAGNET',
                      durationRemaining: 10,
                      maxDuration: 10,
                      iconName: type === 'shield' ? 'Shield' : 'Zap',
                    },
                  ],
                };
              });
            }}
            onSimulateCrash={() => handleGameOver(hudState.score, hudState.distance, hudState.coins, hudState.obstaclesAvoided)}
          />

          {/* Pause Modal Overlay */}
          {screen === 'PAUSED' && (
            <PauseMenu
              score={hudState.score}
              distance={hudState.distance}
              coins={hudState.coins}
              onResume={() => setScreen('PLAYING')}
              onRestart={handleStartGame}
              onMainMenu={() => setScreen('MENU')}
              isMuted={settings.masterVolume === 0}
              onToggleMute={() => {
                setSettings((prev) => ({
                  ...prev,
                  masterVolume: prev.masterVolume === 0 ? 80 : 0,
                }));
              }}
            />
          )}
        </div>
      )}

      {/* VIEW: CHARACTER SELECTION */}
      {screen === 'CHARACTERS' && (
        <CharacterSelection
          characters={CHARACTERS_DATA}
          selectedCharacterId={player.selectedCharacterId}
          player={player}
          onSelectCharacter={handleSelectCharacter}
          onUnlockCharacter={handleUnlockCharacter}
          onBack={() => setScreen('MENU')}
        />
      )}

      {/* VIEW: LEADERBOARD */}
      {screen === 'LEADERBOARD' && (
        <Leaderboard onBack={() => setScreen('MENU')} />
      )}

      {/* VIEW: SETTINGS */}
      {screen === 'SETTINGS' && (
        <SettingsPanel
          settings={settings}
          onUpdateSettings={(patch) => setSettings((prev) => ({ ...prev, ...patch }))}
          onResetCareerData={handleResetCareerData}
          onBack={() => setScreen('MENU')}
        />
      )}

      {/* VIEW: RESULTS SCREEN */}
      {screen === 'RESULTS' && lastResults && (
        <ResultsScreen
          results={lastResults}
          player={player}
          onPlayAgain={handleStartGame}
          onMainMenu={() => setScreen('MENU')}
          onOpenCharacters={() => setScreen('CHARACTERS')}
        />
      )}
    </div>
  );
}
