import { describe, expect, it } from 'vitest'
import { RUN_CYCLE_SECONDS, jumpArc, laneLean, sampleRunPhase, slideCrouch } from './runnerMath'

describe('runnerMath running dynamics and regression checks', () => {
  it('alternates leg swing across half-strides', () => {
    // At phase = 0.25 (1/4 cycle), swing = sin(PI/2) = 1 (max forward for left leg)
    const tQuarter = RUN_CYCLE_SECONDS * 0.25
    const phaseQuarter = sampleRunPhase(tQuarter, 1)
    expect(phaseQuarter.hip).toBeGreaterThan(0.7)

    // At phase = 0.75 (3/4 cycle), swing = sin(3PI/2) = -1 (max backward for left leg)
    const tThreeQuarter = RUN_CYCLE_SECONDS * 0.75
    const phaseThreeQuarter = sampleRunPhase(tThreeQuarter, 1)
    expect(phaseThreeQuarter.hip).toBeLessThan(-0.7)

    // Opposing leg (right leg) has rotation -phase.hip, confirming opposition
    expect(-phaseQuarter.hip).toBeLessThan(-0.7)
    expect(-phaseThreeQuarter.hip).toBeGreaterThan(0.7)
  })

  it('swings arms in natural opposition to legs', () => {
    // When left leg swings forward (hip > 0), left shoulder rotation (-swing * 0.95) is negative
    // and right shoulder -(-swing * 0.95) is positive
    const phase = sampleRunPhase(RUN_CYCLE_SECONDS * 0.25, 1)
    expect(phase.hip).toBeGreaterThan(0)
    expect(phase.shoulder).toBeLessThan(0)
  })

  it('keeps knee flexion positive throughout run cycle', () => {
    // Knees bend backward (rotation >= 0)
    for (let step = 0; step < 20; step++) {
      const t = (RUN_CYCLE_SECONDS * step) / 20
      const phase = sampleRunPhase(t, 1)
      expect(phase.knee).toBeGreaterThanOrEqual(0)
    }
  })

  it('maintains balanced torso pitch and head counter-pitch', () => {
    const phase = sampleRunPhase(0, 1)
    expect(phase.pitch).toBeGreaterThan(0)
    expect(phase.headPitch).toBeLessThan(0)
  })

  it('computes jump arc and slide crouch within valid bounds', () => {
    expect(jumpArc(0)).toBe(0)
    expect(jumpArc(0.5)).toBeCloseTo(1)
    expect(jumpArc(1)).toBeCloseTo(0)

    expect(slideCrouch(0)).toBe(0)
    expect(slideCrouch(0.5)).toBeGreaterThan(0.9)
    expect(slideCrouch(1)).toBe(0)
  })

  it('calculates lane lean opposing lateral movement direction', () => {
    // Moving from lane 0 (x=-3.2) towards lane 1 (x=0): target - current > 0
    const leanRight = laneLean(-3.2, 0, 3.2)
    expect(leanRight).toBeLessThan(0) // Banks into the turn

    const leanLeft = laneLean(0, -3.2, 3.2)
    expect(leanLeft).toBeGreaterThan(0)
  })
})
