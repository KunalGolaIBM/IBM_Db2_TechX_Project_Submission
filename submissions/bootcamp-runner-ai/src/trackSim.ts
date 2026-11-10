// Headless simulation of the endless track: obstacles, coins and answer gates.
// It is deliberately free of Three.js and React so it can be unit tested and so
// the rendering layer only has to read state and paint it.

import type { Difficulty, Mode } from './types'
import { difficultySettings, modeSettings } from './data'

export const LANE_X = [-2.9, 0, 2.9]
export const SPAWN_Z = -96
export const RECYCLE_Z = 12

/** Real-world speed of the track for a difficulty, in units per second. */
export function speedFor(difficulty: Difficulty): number {
  return difficultySettings[difficulty].speed
}

/** Seconds between obstacle spawns; a lower value means a denser track. */
export function obstacleInterval(difficulty: Difficulty, mode: Mode): number {
  const base = 2.7 - modeSettings[mode].obstacleRate * 2.2
  const factor = difficulty === 'Easy' ? 1.25 : difficulty === 'Hard' ? 0.75 : 1
  return base * factor
}

export type Hazard = {
  lane: number
  kind: 'low' | 'high'
  z: number
  cleared: boolean
  passed: boolean
}

export type Coin = {
  lane: number
  z: number
  collected: boolean
}

export type Gate = {
  optionIndex: number
  lane: number
  z: number
  resolved: boolean
}

/**
 * How far ahead (in seconds) the answer gates are scheduled so the player has
 * time to read the options and change lanes before the gate line arrives.
 */
export const GATE_LEAD_SECONDS = 3.1

export interface SimState {
  distance: number
  hazards: Hazard[]
  coins: Coin[]
  gates: Gate[]
  gateArmed: boolean
  hazardTimer: number
  coinTimer: number
  gateTimer: number
  cleared: number
  hits: number
  collected: number
  rngSeed: number
}

export interface SimEvents {
  onCoin: () => void
  onHit: () => void
  onGate: (optionIndex: number) => void
}

/** Small deterministic PRNG so runs are reproducible in tests. */
function nextRandom(state: SimState): number {
  state.rngSeed = (state.rngSeed * 1664525 + 1013904223) >>> 0
  return state.rngSeed / 4294967296
}

export function createSim(seed = 20261018): SimState {
  return {
    distance: 0,
    hazards: [],
    coins: [],
    gates: [],
    gateArmed: false,
    hazardTimer: 1.6,
    coinTimer: 1.2,
    gateTimer: GATE_LEAD_SECONDS,
    cleared: 0,
    hits: 0,
    collected: 0,
    rngSeed: seed,
  }
}

/**
 * Assigns each answer option to one lane. The option order is shuffled so the
 * correct answer is not always in the same lane, but exactly one option is
 * placed in each of the three lanes.
 */
export function gateAssignment(optionCount: number, rng: () => number): number[] {
  const order = [0, 1, 2].slice(0, Math.min(optionCount, 3))
  for (let i = order.length - 1; i > 0; i -= 1) {
    const j = Math.floor(rng() * (i + 1))
    const swap = order[i]
    order[i] = order[j]
    order[j] = swap
  }
  return order
}

/** Positions the three answer gates across the lanes, shuffled per question. */
export function spawnGates(state: SimState, count: number): Gate[] {
  const optionOrder = gateAssignment(count, () => nextRandom(state))
  const gates: Gate[] = optionOrder.map((optionIndex, lane) => ({ optionIndex, lane, z: SPAWN_Z, resolved: false }))
  state.gates = gates
  state.gateArmed = false
  return gates
}

/** Clears gates without scoring — used when the question changes or the run pauses. */
export function clearGates(state: SimState): void {
  state.gates = []
  state.gateArmed = false
  state.gateTimer = GATE_LEAD_SECONDS
}

export interface StepOptions {
  delta: number
  speed: number
  lane: number
  jumping: boolean
  sliding: boolean
  difficulty: Difficulty
  mode: Mode
  /** Gates are only spawned while a question is waiting for an answer. */
  gatesActive: boolean
  activeGateCount: number
}

/**
 * Advances the world by `delta` seconds. Objects are recycled in place so the
 * object count never grows during a run.
 */
export function stepSim(state: SimState, options: StepOptions, events: SimEvents): void {
  const { delta, speed, lane, jumping, sliding, difficulty, mode, gatesActive } = options
  state.distance += speed * delta

  const move = speed * delta

  // --- hazards ------------------------------------------------------------
  state.hazardTimer -= delta
  if (state.hazardTimer <= 0) {
    const lane = Math.floor(nextRandom(state) * 3)
    const kind: Hazard['kind'] = nextRandom(state) < 0.32 ? 'high' : 'low'
    const recycled = state.hazards.find((hazard) => hazard.z > RECYCLE_Z - 4)
    const next: Hazard = { lane, kind, z: SPAWN_Z - nextRandom(state) * 8, cleared: false, passed: false }
    if (recycled) {
      recycled.lane = next.lane
      recycled.kind = next.kind
      recycled.z = next.z
      recycled.cleared = false
      recycled.passed = false
    } else if (state.hazards.length < 12) {
      state.hazards.push(next)
    }
    state.hazardTimer = obstacleInterval(difficulty, mode) * (0.8 + nextRandom(state) * 0.5)
  }
  for (const hazard of state.hazards) {
    hazard.z += move
    if (!hazard.passed && hazard.z > -1.1 && hazard.z < 0.7) {
      if (hazard.lane === lane) {
        const dodged = hazard.kind === 'high' ? sliding : jumping
        if (dodged && !hazard.cleared) {
          hazard.cleared = true
          state.cleared += 1
        } else {
          state.hits += 1
          events.onHit()
        }
      }
      hazard.passed = true
    }
    if (hazard.z > RECYCLE_Z) {
      hazard.z = SPAWN_Z - nextRandom(state) * 30
      hazard.lane = Math.floor(nextRandom(state) * 3)
      hazard.cleared = false
      hazard.passed = false
    }
  }

  // --- coins --------------------------------------------------------------
  state.coinTimer -= delta
  if (state.coinTimer <= 0) {
    const laneIndex = Math.floor(nextRandom(state) * 3)
    const free = state.coins.find((coin) => coin.z > RECYCLE_Z - 4)
    const z = SPAWN_Z - nextRandom(state) * 12
    if (free) {
      free.lane = laneIndex
      free.z = z
      free.collected = false
    } else if (state.coins.length < 22) {
      state.coins.push({ lane: laneIndex, z, collected: false })
    }
    state.coinTimer = 0.55 + nextRandom(state) * 0.6
  }
  for (const coin of state.coins) {
    coin.z += move
    if (!coin.collected && coin.lane === lane && coin.z > -0.9 && coin.z < 0.9) {
      coin.collected = true
      state.collected += 1
      events.onCoin()
    }
    if (coin.z > RECYCLE_Z) {
      coin.z = SPAWN_Z - nextRandom(state) * 40
      coin.lane = Math.floor(nextRandom(state) * 3)
      coin.collected = false
    }
  }

  // --- answer gates -------------------------------------------------------
  if (!gatesActive) {
    if (state.gates.length > 0) clearGates(state)
    return
  }
  if (state.gates.length === 0) {
    state.gateTimer -= delta
    if (state.gateTimer <= 0) spawnGates(state, options.activeGateCount)
    return
  }

  // The gates travel as one rigid row. The row resolves when its centre
  // crosses the runner, which is also the moment the question is answered.
  let rowZ = -Infinity
  for (const gate of state.gates) {
    gate.z += move
    rowZ = Math.max(rowZ, gate.z)
  }
  if (rowZ >= -0.35 && !state.gateArmed) {
    state.gateArmed = true
    const chosen = state.gates.find((gate) => gate.lane === lane)
    for (const gate of state.gates) gate.resolved = true
    state.gateTimer = GATE_LEAD_SECONDS
    events.onGate(chosen ? chosen.optionIndex : -1)
  }
}

/** Screen-space-ish hint: which lane a gate currently occupies. */
export function gateLane(state: SimState, optionIndex: number): number {
  return state.gates.find((gate) => gate.optionIndex === optionIndex)?.lane ?? -1
}
