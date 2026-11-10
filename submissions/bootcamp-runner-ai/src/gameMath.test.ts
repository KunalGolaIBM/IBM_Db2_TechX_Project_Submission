import { describe, expect, it } from 'vitest'
import { isGameOver, laneAfterMove, scoreAnswer } from './gameMath'
import type { SessionStats } from './types'

const stats: SessionStats = { score: 0, coins: 0, correct: 0, answered: 0, bestStreak: 0, distance: 0 }

describe('runner game rules', () => {
  it('keeps lane movement within the three-lane track', () => {
    expect(laneAfterMove(0, -1)).toBe(0)
    expect(laneAfterMove(1, -1)).toBe(0)
    expect(laneAfterMove(2, 1)).toBe(2)
  })

  it('awards score, coins, and a streak for correct answers', () => {
    const result = scoreAnswer(stats, true, 'Normal')
    expect(result).toMatchObject({ score: 145, coins: 5, correct: 1, answered: 1, bestStreak: 1 })
  })

  it('resets streak and prevents negative scores for wrong answers', () => {
    const result = scoreAnswer({ ...stats, score: 10, bestStreak: 3 }, false, 'Normal')
    expect(result).toMatchObject({ score: 0, answered: 1, bestStreak: 0 })
  })

  it('ends a session when no lives remain', () => {
    expect(isGameOver(0)).toBe(true)
    expect(isGameOver(1)).toBe(false)
  })
})
