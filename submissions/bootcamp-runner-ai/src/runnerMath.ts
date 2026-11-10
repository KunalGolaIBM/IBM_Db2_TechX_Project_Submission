// Pure, frame-rate independent maths for the procedural running character.
// Everything here is expressed as a function of elapsed time / normalised
// progress so the same pose is produced at 30 fps and at 144 fps.

export const RUN_CYCLE_SECONDS = 0.62
export const JUMP_SECONDS = 0.82
export const SLIDE_SECONDS = 0.95
export const JUMP_HEIGHT = 1.95

export interface RunPhase {
  /** 0..1 progress through one stride. */
  phase: number
  /** Vertical bob of the pelvis. */
  bob: number
  /** Torso pitch in radians. */
  pitch: number
  /** Torso roll in radians. */
  roll: number
  /** Head counter-pitch in radians. */
  headPitch: number
  /** World forward lean in radians. */
  lean: number
  /** Shoulder rotation about Z, radians. */
  shoulder: number
  /** Elbow rotation about X, radians. */
  elbow: number
  /** Hip rotation about X, radians. */
  hip: number
  /** Knee rotation about X, radians (always >= 0). */
  knee: number
  /** Ankle rotation about X, radians. */
  ankle: number
}

const TAU = Math.PI * 2

function wrap(value: number): number {
  return ((value % 1) + 1) % 1
}

/**
 * Samples one leg from the shared run phase. The second leg simply reads the
 * same curve half a stride later, which gives the classic opposing-leg swing.
 */
export function sampleRunPhase(time: number, speedFactor = 1): RunPhase {
  const rate = speedFactor > 0 ? speedFactor : 0.001
  const phase = wrap(time / (RUN_CYCLE_SECONDS / rate))
  const swing = Math.sin(phase * TAU)
  const anti = Math.sin(phase * TAU + Math.PI)

  return {
    phase,
    bob: Math.abs(Math.cos(phase * Math.PI * 2)) * 0.085 - 0.04,
    pitch: 0.15 + swing * 0.03,
    roll: swing * 0.045,
    headPitch: -0.1 - swing * 0.03,
    lean: 0.13 + Math.abs(swing) * 0.03,
    shoulder: -swing * 0.95,
    elbow: -0.55 - Math.max(0, anti) * 0.75,
    hip: swing * 0.78,
    knee: Math.max(0, Math.sin(phase * TAU - Math.PI * 0.42)) * 1.55 + 0.12,
    ankle: anti * 0.28,
  }
}

/** Normalised height of a jump in 0..1 over the arc of the jump. */
export function jumpArc(progress: number): number {
  const p = Math.min(Math.max(progress, 0), 1)
  return Math.sin(p * Math.PI)
}

/** How much a sliding runner is crouched, 0 (standing) .. 1 (fully flat). */
export function slideCrouch(progress: number): number {
  const p = Math.min(Math.max(progress, 0), 1)
  const inTime = Math.min(1, p / 0.16)
  const outTime = Math.min(1, (1 - p) / 0.24)
  const easeIn = inTime * inTime * (3 - 2 * inTime)
  const easeOut = outTime * outTime * (3 - 2 * outTime)
  return Math.max(0, Math.min(easeIn, easeOut))
}

/** Small trailing tilt while changing lanes, in radians. */
export function laneLean(currentLaneX: number, targetLaneX: number, laneWidth = 2.9): number {
  const offset = Math.max(-1, Math.min(1, (targetLaneX - currentLaneX) / laneWidth))
  return -offset * 0.3
}
