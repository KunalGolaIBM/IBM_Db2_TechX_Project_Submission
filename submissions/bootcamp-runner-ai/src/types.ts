export type Screen = 'menu' | 'game' | 'results' | 'dashboard' | 'characters' | 'worlds'
export type WorldId = 'silicon-valley' | 'neon-ai-city' | 'data-center' | 'gpu-factory'
export type PowerUpId = 'boost' | 'shield' | 'magnet' | 'dash' | 'multiplier'

export interface Character {
  id: string
  name: string
  role: string
  color: string
  accent: string
  unlocked: boolean
  unlockCost: number
  effect: string
}

export interface SessionStats {
  score: number
  coins: number
  chips: number
  combo: number
  distance: number
  speed: number
  powerUp: PowerUpId | null
  powerUpTime: number
  hits: number
  world: WorldId
  characterId: string
}

export interface PlayerProgress {
  totalRuns: number
  distance: number
  bestScore: number
  totalCoins: number
  totalChips: number
  unlockedCharacters: string[]
  selectedCharacter: string
  unlockedWorlds: WorldId[]
  selectedWorld: WorldId
  achievements: string[]
  missions: Record<string, number>
}
