// Builds a stylized low-poly human runner out of shared geometry + materials.
// All joints are nested Groups so a run cycle can be authored as pure rotations.
//
// Joint hierarchy:
//   root            (lane position / lateral lean)
//     pelvis        (vertical bob, forward lean)
//       torso       (counter-rotation, side tilt)
//         headPivot -> head, visor, hair crest
//         shoulder.L/R -> elbow -> hand
//       hip.L/R -> knee -> shoe
//
// Every mesh uses one of five shared materials, and geometry is cached per
// character id so switching runners never leaks GPU memory.

import * as THREE from 'three'
import type { Character } from './types'

export interface RunnerRig {
  root: THREE.Group
  pelvis: THREE.Group
  torso: THREE.Group
  head: THREE.Group
  shoulderL: THREE.Group
  shoulderR: THREE.Group
  elbowL: THREE.Group
  elbowR: THREE.Group
  hipL: THREE.Group
  hipR: THREE.Group
  kneeL: THREE.Group
  kneeR: THREE.Group
  footL: THREE.Group
  footR: THREE.Group
  /** Fake contact shadow that follows the runner. */
  shadow: THREE.Mesh
  materials: { suit: THREE.MeshStandardMaterial; accent: THREE.MeshStandardMaterial; skin: THREE.MeshStandardMaterial; dark: THREE.MeshStandardMaterial; trim: THREE.MeshBasicMaterial }
  /** Everything the rig owns, for disposal. */
  owned: Set<THREE.Object3D>
}

export interface RunnerBuild {
  rig: RunnerRig
  mesh: THREE.Group
}

const cache = new Map<string, RunnerBuild>()

function makeMaterials(character: Character) {
  return {
    suit: new THREE.MeshStandardMaterial({ color: 0x131c2b, roughness: 0.62, metalness: 0.18 }),
    accent: new THREE.MeshStandardMaterial({ color: new THREE.Color(character.color), emissive: new THREE.Color(character.accent), emissiveIntensity: 0.65, roughness: 0.35, metalness: 0.3 }),
    skin: new THREE.MeshStandardMaterial({ color: 0xe8b98f, roughness: 0.78, metalness: 0.02 }),
    dark: new THREE.MeshStandardMaterial({ color: 0x080d15, roughness: 0.5, metalness: 0.25 }),
    trim: new THREE.MeshBasicMaterial({ color: new THREE.Color(character.color) }),
  }
}

function cylinder(top: number, bottom: number, height: number, material: THREE.Material): THREE.Mesh {
  const mesh = new THREE.Mesh(new THREE.CylinderGeometry(top, bottom, height, 10, 1), material)
  return mesh
}

function box(width: number, height: number, depth: number, material: THREE.Material): THREE.Mesh {
  return new THREE.Mesh(new THREE.BoxGeometry(width, height, depth), material)
}

function sphere(radius: number, material: THREE.Material): THREE.Mesh {
  return new THREE.Mesh(new THREE.SphereGeometry(radius, 12, 10), material)
}

function buildArm(materials: RunnerRig['materials'], side: 1 | -1) {
  const shoulder = new THREE.Group()
  shoulder.position.set(side * 0.34, 0.44, 0)

  const upper = cylinder(0.085, 0.075, 0.44, materials.suit)
  upper.position.y = -0.22
  shoulder.add(upper)

  const cap = sphere(0.13, materials.accent)
  cap.position.y = 0.02
  shoulder.add(cap)

  const elbow = new THREE.Group()
  elbow.position.y = -0.44
  shoulder.add(elbow)

  const fore = cylinder(0.072, 0.058, 0.42, materials.skin)
  fore.position.y = -0.21
  elbow.add(fore)

  const cuff = cylinder(0.075, 0.075, 0.09, materials.trim)
  cuff.position.y = -0.42
  elbow.add(cuff)

  const hand = new THREE.Mesh(new THREE.BoxGeometry(0.13, 0.17, 0.11), materials.skin)
  hand.position.y = -0.53
  elbow.add(hand)

  return { shoulder, elbow }
}

function buildLeg(materials: RunnerRig['materials'], side: 1 | -1) {
  const hip = new THREE.Group()
  hip.position.set(side * 0.16, 0.02, 0)

  const thigh = cylinder(0.13, 0.105, 0.62, materials.suit)
  thigh.position.y = -0.31
  hip.add(thigh)

  const stripe = box(0.035, 0.6, 0.14, materials.trim)
  stripe.position.set(side * 0.115, -0.31, 0.02)
  hip.add(stripe)

  const knee = new THREE.Group()
  knee.position.y = -0.62
  hip.add(knee)

  const kneeCap = sphere(0.1, materials.accent)
  knee.add(kneeCap)

  const shin = cylinder(0.1, 0.078, 0.58, materials.suit)
  shin.position.y = -0.29
  knee.add(shin)

  const foot = new THREE.Group()
  foot.position.y = -0.58
  knee.add(foot)

  const sole = box(0.19, 0.1, 0.42, materials.dark)
  sole.position.set(0, -0.04, -0.08)
  foot.add(sole)

  const shoe = box(0.16, 0.09, 0.28, materials.accent)
  shoe.position.set(0, 0.05, -0.08)
  foot.add(shoe)

  return { hip, knee, foot }
}

function build(character: Character): RunnerBuild {
  const materials = makeMaterials(character)
  const owned = new Set<THREE.Object3D>()

  const mesh = new THREE.Group()
  const rig: RunnerRig = {
    root: mesh,
    pelvis: new THREE.Group(),
    torso: new THREE.Group(),
    head: new THREE.Group(),
    shoulderL: new THREE.Group(),
    shoulderR: new THREE.Group(),
    elbowL: new THREE.Group(),
    elbowR: new THREE.Group(),
    hipL: new THREE.Group(),
    hipR: new THREE.Group(),
    kneeL: new THREE.Group(),
    kneeR: new THREE.Group(),
    footL: new THREE.Group(),
    footR: new THREE.Group(),
    shadow: new THREE.Mesh(
      new THREE.CircleGeometry(0.72, 20),
      new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.34, depthWrite: false })
    ),
    materials,
    owned,
  }
  rig.root.name = 'runnerRoot'
  rig.pelvis.name = 'pelvis'
  rig.torso.name = 'torso'
  rig.head.name = 'head'
  rig.shoulderL.name = 'shoulderL'
  rig.shoulderR.name = 'shoulderR'
  rig.elbowL.name = 'elbowL'
  rig.elbowR.name = 'elbowR'
  rig.hipL.name = 'hipL'
  rig.hipR.name = 'hipR'
  rig.kneeL.name = 'kneeL'
  rig.kneeR.name = 'kneeR'
  rig.footL.name = 'footL'
  rig.footR.name = 'footR'
  rig.shadow.name = 'shadow'
  rig.shadow.rotation.x = -Math.PI / 2
  rig.shadow.renderOrder = 2

  // pelvis sits at hip height; everything above hangs from it
  rig.pelvis.position.y = 1.02
  mesh.add(rig.pelvis)

  // --- torso ---------------------------------------------------------------
  const belly = cylinder(0.32, 0.27, 0.56, materials.suit)
  belly.position.y = 0.28
  rig.torso.add(belly)

  const chest = box(0.56, 0.34, 0.32, materials.suit)
  chest.position.y = 0.6
  rig.torso.add(chest)

  const chestPanel = box(0.3, 0.22, 0.06, materials.accent)
  chestPanel.position.set(0, 0.62, -0.19)
  rig.torso.add(chestPanel)

  const belt = cylinder(0.29, 0.29, 0.12, materials.dark)
  belt.position.y = 0.02
  rig.torso.add(belt)

  const beltGlow = box(0.12, 0.09, 0.06, materials.trim)
  beltGlow.position.set(0, 0.02, -0.28)
  rig.torso.add(beltGlow)

  // shoulder yoke: makes the silhouette read as human from behind
  const yoke = box(0.78, 0.13, 0.3, materials.accent)
  yoke.position.y = 0.78
  rig.torso.add(yoke)

  const backpack = box(0.44, 0.5, 0.24, materials.dark)
  backpack.position.set(0, 0.5, 0.22)
  rig.torso.add(backpack)

  const packGlow = box(0.2, 0.34, 0.04, materials.trim)
  packGlow.position.set(0, 0.5, 0.35)
  rig.torso.add(packGlow)

  rig.pelvis.add(rig.torso)
  rig.torso.position.y = 0.14

  // --- head ----------------------------------------------------------------
  rig.head.position.y = 0.88
    rig.torso.add(rig.head)

  const neck = cylinder(0.1, 0.12, 0.2, materials.skin)
  neck.position.y = -0.06
  rig.head.add(neck)

  const skull = sphere(0.23, materials.skin)
  skull.position.y = 0.16
  skull.scale.set(1, 1.12, 1.05)
  rig.head.add(skull)

  const hair = sphere(0.235, materials.dark)
  hair.position.y = 0.19
  hair.scale.set(1.02, 0.95, 1.06)
  rig.head.add(hair)

  const visor = box(0.4, 0.13, 0.09, materials.trim)
  visor.position.set(0, 0.18, -0.19)
  rig.head.add(visor)

  const crest = box(0.07, 0.26, 0.24, materials.accent)
  crest.position.set(0, 0.3, 0.02)
  rig.head.add(crest)

  // --- arms ----------------------------------------------------------------
  const armL = buildArm(materials, -1)
  const armR = buildArm(materials, 1)
  rig.torso.add(armL.shoulder, armR.shoulder)
  rig.shoulderL = armL.shoulder
  rig.elbowL = armL.elbow
  rig.shoulderR = armR.shoulder
  rig.elbowR = armR.elbow

  // --- legs ----------------------------------------------------------------
  const legL = buildLeg(materials, -1)
  const legR = buildLeg(materials, 1)
  rig.pelvis.add(legL.hip, legR.hip)
  rig.hipL = legL.hip
  rig.kneeL = legL.knee
  rig.footL = legL.foot
  rig.hipR = legR.hip
  rig.kneeR = legR.knee
  rig.footR = legR.foot
  rig.shoulderL.name = 'shoulderL'
  rig.shoulderR.name = 'shoulderR'
  rig.elbowL.name = 'elbowL'
  rig.elbowR.name = 'elbowR'
  rig.hipL.name = 'hipL'
  rig.hipR.name = 'hipR'
  rig.kneeL.name = 'kneeL'
  rig.kneeR.name = 'kneeR'
  rig.footL.name = 'footL'
  rig.footR.name = 'footR'

  mesh.traverse((object) => {
    if (object instanceof THREE.Mesh) owned.add(object)
  })

  // Fake contact shadow: a soft ellipse that keeps the runner grounded
  // without paying for a real shadow map.
  rig.shadow.position.y = 0.015
  mesh.add(rig.shadow)
  owned.add(rig.shadow)

  return { rig, mesh }
}

/** Returns a cached runner for this character (built once, reused afterwards). */
export function createRunner(character: Character): RunnerBuild {
  const cached = cache.get(character.id)
  if (cached) return cached
  const built = build(character)
  cache.set(character.id, built)
  return built
}

/** Clones a cached runner so multiple instances never share a transform. */
export function cloneRunner(character: Character): RunnerBuild {
  const source = createRunner(character)
  const mesh = source.mesh.clone(true)
  const find = (name: string) => mesh.getObjectByName(name) as THREE.Group
  const rig: RunnerRig = {
    ...source.rig,
    root: mesh,
    pelvis: find('pelvis'),
    torso: find('torso'),
    head: find('head') as THREE.Group,
    shoulderL: find('shoulderL'),
    shoulderR: find('shoulderR'),
    elbowL: find('elbowL'),
    elbowR: find('elbowR'),
    hipL: find('hipL'),
    hipR: find('hipR'),
    kneeL: find('kneeL'),
    kneeR: find('kneeR'),
    footL: find('footL'),
    footR: find('footR'),
    shadow: mesh.getObjectByName('shadow') as THREE.Mesh,
    // Clones share geometry and materials with the cached original, so this
    // instance owns nothing and must never dispose the shared resources.
    owned: new Set<THREE.Object3D>(),
  }
  return { rig, mesh }
}

/** Frees every geometry/material created for a character. */
export function disposeRunner(characterId: string): void {
  const built = cache.get(characterId)
  if (!built) return
  built.rig.owned.forEach((object: THREE.Object3D) => {
    if (object instanceof THREE.Mesh) object.geometry.dispose()
  })
  Object.values(built.rig.materials).forEach((material) => material.dispose())
  cache.delete(characterId)
}
