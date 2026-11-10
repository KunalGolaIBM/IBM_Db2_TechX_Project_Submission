import type { SessionStats } from './types'

export function laneAfterMove(lane: number, direction: -1 | 1): number {
  return Math.max(0, Math.min(2, lane + direction))
}

export function scoreCollectible(stats: SessionStats, value: number, combo = stats.combo): SessionStats {
  return { ...stats, score: stats.score + Math.round(value * combo), combo: Math.min(9, combo + 0.1) }
}

export function registerHit(stats: SessionStats): SessionStats {
  return { ...stats, hits: stats.hits + 1, combo: 1, score: Math.max(0, stats.score - 75) }
}

export function isGameOver(hits: number, lives = 3): boolean {
  return hits >= lives
}
