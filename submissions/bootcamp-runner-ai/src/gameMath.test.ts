import { describe, expect, it } from 'vitest'
import { isGameOver, laneAfterMove, registerHit, scoreCollectible } from './gameMath'
import type { SessionStats } from './types'

const stats: SessionStats = { score: 0, coins: 0, chips: 0, combo: 1, distance: 0, speed: 11, powerUp: null, powerUpTime: 0, hits: 0, world: 'silicon-valley', characterId: 'sam' }

describe('arcade runner rules', () => {
  it('keeps lane movement within the three-lane track', () => {
    expect(laneAfterMove(0, -1)).toBe(0)
    expect(laneAfterMove(1, -1)).toBe(0)
    expect(laneAfterMove(2, 1)).toBe(2)
  })
  it('awards collectible score using the combo', () => {
    expect(scoreCollectible(stats, 10)).toMatchObject({ score: 10, combo: 1.1 })
  })
  it('resets combo and prevents negative scores on a hit', () => {
    expect(registerHit({ ...stats, score: 20, combo: 4 })).toMatchObject({ score: 0, hits: 1, combo: 1 })
  })
  it('ends a run after three hits', () => {
    expect(isGameOver(3)).toBe(true)
    expect(isGameOver(2)).toBe(false)
  })
})
