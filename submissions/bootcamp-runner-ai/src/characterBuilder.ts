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
//
// Conventions that keep the runner visible from every angle:
//   * The model faces -Z (the direction it runs), so a camera at +Z sees the
//     front and a camera at -Z sees the back.
//   * The root origin sits on the ground between the feet (y = 0), so the
//     bounding box is always [0, ~1.9] in Y and can be framed directly.
//   * Every material is DoubleSide: thin parts (visor, chest panel, stripes)
//     are boxes, and a single-sided material would make them vanish as the
//     character turns.

import * as THREE from 'three'
import type { Character, CharacterHeadgear } from './types'

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
    suit: new THREE.MeshStandardMaterial({ color: 0x131c2b, roughness: 0.62, metalness: 0.18, side: THREE.DoubleSide }),
    accent: new THREE.MeshStandardMaterial({ color: new THREE.Color(character.color), emissive: new THREE.Color(character.accent), emissiveIntensity: 0.65, roughness: 0.35, metalness: 0.3, side: THREE.DoubleSide }),
    skin: new THREE.MeshStandardMaterial({ color: 0xe8b98f, roughness: 0.78, metalness: 0.02, side: THREE.DoubleSide }),
    dark: new THREE.MeshStandardMaterial({ color: 0x080d15, roughness: 0.5, metalness: 0.25, side: THREE.DoubleSide }),
    trim: new THREE.MeshBasicMaterial({ color: new THREE.Color(character.color), side: THREE.DoubleSide }),
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
  // The pivot sits at the outer edge of the chest (half width 0.28) so the
  // arm hangs beside the torso instead of inside it.
  shoulder.position.set(side * 0.36, 0.44, 0)

  // The upper arm is skin-toned with a short accent sleeve at the shoulder:
  // a dark sleeve tube vanished against the torso in the side views.
  const upper = cylinder(0.085, 0.075, 0.44, materials.skin)
  upper.position.y = -0.22
  shoulder.add(upper)

  const sleeve = cylinder(0.1, 0.09, 0.2, materials.suit)
  sleeve.position.y = -0.1
  shoulder.add(sleeve)

  const band = cylinder(0.095, 0.095, 0.05, materials.accent)
  band.position.y = -0.2
  shoulder.add(band)

  // The shoulder cap is a rounded pad, not a ball: a full sphere read as a
  // floating orb in the side and three-quarter views.
  const cap = new THREE.Mesh(new THREE.SphereGeometry(0.12, 12, 8, 0, Math.PI * 2, 0, Math.PI * 0.6), materials.accent)
  cap.position.y = 0.02
  cap.scale.set(1, 0.85, 1)
  shoulder.add(cap)

  // A small outward splay keeps the arms clear of the hips in every pose.
  shoulder.userData.restZ = side * 0.1
  shoulder.rotation.z = side * 0.1

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

  // A relaxed elbow bend keeps the hands clear of the hips and gives the arm
  // a readable silhouette from the side. The run cycle adds to this offset.
  elbow.userData.restX = -0.3
  elbow.rotation.x = -0.3

  return { shoulder, elbow }
}

function buildLeg(materials: RunnerRig['materials'], side: 1 | -1) {
  const hip = new THREE.Group()
  hip.position.set(side * 0.16, 0.02, 0)

  const thigh = cylinder(0.13, 0.105, 0.62, materials.suit)
  thigh.position.y = -0.31
  hip.add(thigh)

  // The stripe is a thin band wrapped around the thigh, so it reads from the
  // front, back and both sides instead of only one face.
  const stripe = cylinder(0.135, 0.135, 0.05, materials.trim)
  stripe.position.y = -0.3
  hip.add(stripe)

  const knee = new THREE.Group()
  knee.position.y = -0.62
  hip.add(knee)

  // The knee cap is a pad on the front of the joint, not a ball centred on it:
  // a centred sphere read as a floating orb in the side views.
  const kneeCap = new THREE.Mesh(new THREE.SphereGeometry(0.1, 12, 8, 0, Math.PI * 2, 0, Math.PI * 0.6), materials.accent)
  kneeCap.rotation.x = -Math.PI / 2
  kneeCap.position.set(0, 0, -0.06)
  knee.add(kneeCap)

  const shin = cylinder(0.1, 0.078, 0.58, materials.suit)
  shin.position.y = -0.29
  knee.add(shin)

  // Shin band: a thin accent ring so the lower leg reads from every angle.
  const shinBand = cylinder(0.105, 0.105, 0.05, materials.accent)
  shinBand.position.y = -0.2
  knee.add(shinBand)

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

  // Shoulder yoke: a slim accent bar across the collarbones. It is narrower
  // than the shoulders so it never reads as a plank sticking out sideways.
  const yoke = box(0.6, 0.1, 0.26, materials.accent)
  yoke.position.y = 0.78
  rig.torso.add(yoke)

  // The pack sits behind the chest (chest back face is z = +0.16) so it never
  // pokes through the front of the suit, and it is narrower than the chest so
  // it does not stick out past the shoulders in the side views.
  const backpack = box(0.4, 0.46, 0.2, materials.dark)
  backpack.position.set(0, 0.5, 0.26)
  rig.torso.add(backpack)

  const packGlow = box(0.18, 0.3, 0.04, materials.trim)
  packGlow.position.set(0, 0.5, 0.37)
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

  // Hair is a cap, not a second skull: a full sphere would swallow the face
  // and make the head read as a featureless ball from the front.
  const hair = new THREE.Mesh(new THREE.SphereGeometry(0.235, 14, 10, 0, Math.PI * 2, 0, Math.PI * 0.55), materials.dark)
  hair.position.y = 0.19
  hair.scale.set(1.02, 0.95, 1.06)
  rig.head.add(hair)

  const visor = box(0.4, 0.13, 0.09, materials.trim)
  visor.position.set(0, 0.18, -0.19)
  rig.head.add(visor)

  // A dark band across the back of the head separates the hair cap from the
  // neck and makes the back view read as a head rather than a ball.
  const headBand = box(0.34, 0.07, 0.06, materials.accent)
  headBand.position.set(0, 0.12, 0.2)
  rig.head.add(headBand)

  const crest = box(0.07, 0.26, 0.24, materials.accent)
  crest.position.set(0, 0.3, 0.02)
  rig.head.add(crest)

  // Per-character headgear sits on top of the shared head, so every runner
  // keeps the same readable face while still looking distinct.
  buildHeadgear(character.headgear ?? 'visor', materials, rig.head)

  // Name the head parts so the preview can verify the face is present.
  skull.name = 'skull'
  visor.name = 'visor'
  crest.name = 'crest'
  hair.name = 'hair'

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

  // The shadow is a ground decal, not part of the body: keep it out of the
  // bounding box so framing never reserves space for it.
  rig.shadow.userData.ignoreBounds = true

  // Body proportions. Scaling the root keeps every joint, the run cycle and
  // the measured bounding box consistent, so framing adapts automatically.
  const build = character.build ?? 'runner'
  if (build === 'heavy') mesh.scale.set(1.16, 0.97, 1.16)
  else if (build === 'tall') mesh.scale.set(0.94, 1.1, 0.94)
  else if (build === 'compact') mesh.scale.set(0.9, 0.9, 0.9)

  return { rig, mesh }
}

/** Adds the character's signature head accessory. */
function buildHeadgear(kind: CharacterHeadgear, materials: RunnerRig['materials'], head: THREE.Group) {
  if (kind === 'cap') {
    const brim = box(0.42, 0.04, 0.2, materials.accent)
    brim.position.set(0, 0.24, -0.2)
    head.add(brim)
    const dome = new THREE.Mesh(new THREE.SphereGeometry(0.245, 14, 8, 0, Math.PI * 2, 0, Math.PI * 0.5), materials.accent)
    dome.position.y = 0.2
    head.add(dome)
  } else if (kind === 'headset') {
    for (const side of [-1, 1]) {
      const cup = cylinder(0.09, 0.09, 0.07, materials.accent)
      cup.rotation.z = Math.PI / 2
      cup.position.set(side * 0.24, 0.16, 0)
      head.add(cup)
    }
    const band = new THREE.Mesh(new THREE.TorusGeometry(0.24, 0.025, 6, 16, Math.PI), materials.accent)
    band.position.y = 0.16
    band.rotation.z = Math.PI
    head.add(band)
  } else if (kind === 'crown') {
    const ring = cylinder(0.2, 0.2, 0.06, materials.accent)
    ring.position.y = 0.36
    head.add(ring)
    for (let i = 0; i < 5; i += 1) {
      const spike = new THREE.Mesh(new THREE.ConeGeometry(0.035, 0.12, 6), materials.accent)
      const angle = (i / 5) * Math.PI * 2
      spike.position.set(Math.sin(angle) * 0.17, 0.44, Math.cos(angle) * 0.17)
      head.add(spike)
    }
  } else if (kind === 'helmet') {
    const shell = new THREE.Mesh(new THREE.SphereGeometry(0.26, 16, 10, 0, Math.PI * 2, 0, Math.PI * 0.62), materials.accent)
    shell.position.y = 0.17
    head.add(shell)
    const stripe = box(0.06, 0.1, 0.5, materials.trim)
    stripe.position.y = 0.3
    head.add(stripe)
  }
}

/**
 * World-space bounding box of the runner's body (shadow excluded).
 * Computed from the current pose, so it is valid for the idle pose, the run
 * cycle and the slide crouch alike.
 */
export function measureRunner(mesh: THREE.Object3D): THREE.Box3 {
  mesh.updateWorldMatrix(true, true)
  const box = new THREE.Box3()
  const child = new THREE.Box3()
  mesh.traverse((object) => {
    if (!(object instanceof THREE.Mesh) || object.userData.ignoreBounds) return
    if (!object.geometry.boundingBox) object.geometry.computeBoundingBox()
    child.copy(object.geometry.boundingBox as THREE.Box3).applyMatrix4(object.matrixWorld)
    box.union(child)
  })
  if (box.isEmpty()) box.setFromObject(mesh)
  return box
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
