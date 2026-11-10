import type { Difficulty, SessionStats } from './types'
import { difficultySettings } from './data'

export function laneAfterMove(lane: number, direction: -1 | 1): number {
  return Math.max(0, Math.min(2, lane + direction))
}

export function scoreAnswer(stats: SessionStats, correct: boolean, difficulty: Difficulty): SessionStats {
  const settings = difficultySettings[difficulty]
  if (correct) {
    const streak = stats.bestStreak + 1
    return { ...stats, score: stats.score + Math.round(100 * settings.multiplier + streak * 20), correct: stats.correct + 1, answered: stats.answered + 1, bestStreak: streak, coins: stats.coins + 5 }
  }
  return { ...stats, score: Math.max(0, stats.score - 50), answered: stats.answered + 1, bestStreak: 0 }
}

export function isGameOver(lives: number): boolean {
  return lives <= 0
}
