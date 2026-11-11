/**
 * BOOTCAMP RUNNER — Core Game & UI Types
 */

export type GameScreen =
  | 'MENU'
  | 'PLAYING'
  | 'PAUSED'
  | 'CHARACTERS'
  | 'LEADERBOARD'
  | 'SETTINGS'
  | 'RESULTS';

export type CharacterRarity = 'Common' | 'Rare' | 'Epic' | 'Legendary' | 'Mythic';

export interface CharacterStats {
  speed: number;          // 1 - 100
  jump: number;           // 1 - 100
  shieldDuration: number; // 1 - 100
  magnetRadius: number;   // 1 - 100
  syntaxBonus: number;    // 1 - 100
}

export interface Character {
  id: string;
  name: string;
  title: string;
  description: string;
  rarity: CharacterRarity;
  unlocked: boolean;
  unlockCost?: number;
  image: string;
  accentColor: string;
  glowColor: string;
  stats: CharacterStats;
  passive: {
    name: string;
    description: string;
    codeSnippet: string;
  };
}

export interface PowerUpActive {
  id: string;
  type: 'shield' | 'magnet' | 'multiplier' | 'overclock';
  name: string;
  durationRemaining: number;
  maxDuration: number;
  iconName: 'Shield' | 'Magnet' | 'Zap' | 'Cpu';
}

export interface GameHUDState {
  score: number;
  distance: number;
  coins: number;
  currentLevel: number;
  levelName: string;
  combo: number;
  multiplier: number;
  obstaclesAvoided: number;
  activePowerUps: PowerUpActive[];
  health: number; // 0 - 100
  maxHealth: number;
}

export interface RunResults {
  finalScore: number;
  distance: number;
  coins: number;
  obstaclesAvoided: number;
  bestScore: number;
  isNewHighScore: boolean;
  xpEarned: number;
  characterId: string;
  characterName: string;
  timestamp: number;
}

export interface PlayerProfile {
  username: string;
  level: number;
  xp: number;
  nextLevelXp: number;
  coins: number;
  selectedCharacterId: string;
  unlockedCharacterIds: string[];
  bestScore: number;
  totalDistance: number;
  totalRuns: number;
}

export interface LeaderboardEntry {
  rank: number;
  username: string;
  score: number;
  distance: number;
  characterName: string;
  characterRarity: CharacterRarity;
  avatarLetter: string;
  isCurrentPlayer?: boolean;
  countryCode?: string;
  dateStr?: string;
}

export interface GameSettings {
  masterVolume: number; // 0 - 100
  sfxVolume: number;    // 0 - 100
  musicVolume: number;  // 0 - 100
  graphicsQuality: 'Low' | 'Medium' | 'High' | 'Ultra';
  fpsTarget: 60 | 120 | 144 | 0; // 0 is uncapped
  screenShake: boolean;
  motionBlur: boolean;
  highContrastHud: boolean;
  reducedMotion: boolean;
}
