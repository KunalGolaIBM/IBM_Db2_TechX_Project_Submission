import { characters, worlds, achievementNames, missionNames } from './data'
import type { PlayerProgress, SessionStats, WorldId } from './types'

const key = 'bootcamp-runner-arcade-progress-v1'
export const defaultProgress: PlayerProgress = {
  totalRuns: 0, distance: 0, bestScore: 0, totalCoins: 0, totalChips: 0,
  unlockedCharacters: ['sam'], selectedCharacter: 'sam', unlockedWorlds: ['silicon-valley'],
  selectedWorld: 'silicon-valley', achievements: [], missions: Object.fromEntries(missionNames.map((name) => [name, 0])),
}

export function loadProgress(): PlayerProgress {
  try {
    const saved = JSON.parse(localStorage.getItem(key) ?? 'null') as Partial<PlayerProgress> | null
    return { ...defaultProgress, ...saved, missions: { ...defaultProgress.missions, ...(saved?.missions ?? {}) } }
  } catch { return defaultProgress }
}

export function saveProgress(progress: PlayerProgress): void {
  localStorage.setItem(key, JSON.stringify(progress))
}

export function applyRun(progress: PlayerProgress, stats: SessionStats): PlayerProgress {
  const next = { ...progress, totalRuns: progress.totalRuns + 1, distance: progress.distance + stats.distance, bestScore: Math.max(progress.bestScore, stats.score), totalCoins: progress.totalCoins + stats.coins, totalChips: progress.totalChips + stats.chips, missions: { ...progress.missions } }
  next.missions['Run 500 meters'] = Math.max(next.missions['Run 500 meters'], Math.floor(next.distance))
  next.missions['Collect 100 coins'] = Math.max(next.missions['Collect 100 coins'], next.totalCoins)
  next.missions['Reach speed 20'] = Math.max(next.missions['Reach speed 20'], Math.floor(stats.speed))
  const unlocked = new Set(next.achievements)
  if (next.totalRuns > 0) unlocked.add('First Run')
  if (next.totalCoins >= 100) unlocked.add('Coin Collector')
  if (stats.speed >= 20) unlocked.add('Speed Demon')
  if (stats.hits === 0 && stats.distance >= 500) unlocked.add('Survivor')
  if (next.distance >= 1_000_000) unlocked.add('Million-Meter Runner')
  if (next.unlockedCharacters.length === characters.length) unlocked.add('Full Character Collection')
  next.achievements = achievementNames.filter((name) => unlocked.has(name))
  return next
}

export function unlockCharacter(progress: PlayerProgress, id: string): PlayerProgress {
  const character = characters.find((item) => item.id === id)
  if (!character || progress.unlockedCharacters.includes(id) || progress.totalCoins < character.unlockCost) return progress
  return { ...progress, totalCoins: progress.totalCoins - character.unlockCost, unlockedCharacters: [...progress.unlockedCharacters, id] }
}

export function unlockWorld(progress: PlayerProgress, id: WorldId): PlayerProgress {
  const world = worlds.find((item) => item.id === id)
  if (!world || progress.unlockedWorlds.includes(id) || progress.totalCoins < world.unlockCost) return progress
  return { ...progress, totalCoins: progress.totalCoins - world.unlockCost, unlockedWorlds: [...progress.unlockedWorlds, id] }
}
