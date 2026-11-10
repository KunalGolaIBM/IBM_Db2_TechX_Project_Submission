// Pure camera-framing maths shared by the character preview and the gameplay
// camera. Kept free of Three.js so it can be unit tested and so both cameras
// frame the runner the same way at every viewport size.

export interface Size {
  width: number
  height: number
}

export interface Box3Like {
  min: { x: number; y: number; z: number }
  max: { x: number; y: number; z: number }
}

export interface Framing {
  /** Distance from the target along the view direction. */
  distance: number
  /** Vertical field of view in degrees. */
  fov: number
  /** Half extents of the framed box, in world units. */
  halfWidth: number
  halfHeight: number
  /** Centre of the framed box. */
  center: { x: number; y: number; z: number }
}

export const MIN_FOV = 24
export const MAX_FOV = 60

/** Clamp a value into a range. */
export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

/** Aspect ratio that never divides by zero (portrait phones, collapsed panels). */
export function safeAspect(width: number, height: number): number {
  const w = Number.isFinite(width) && width > 0 ? width : 1
  const h = Number.isFinite(height) && height > 0 ? height : 1
  return clamp(w / h, 0.2, 6)
}

/**
 * Device pixel ratio for the renderer. Capped so a 3x phone does not render
 * nine times the pixels of a desktop, and floored at 1.
 */
export function renderPixelRatio(devicePixelRatio: number, cap = 2): number {
  if (!Number.isFinite(devicePixelRatio) || devicePixelRatio <= 0) return 1
  return clamp(devicePixelRatio, 1, cap)
}

/**
 * Distance a perspective camera needs so a box of the given half extents fits
 * inside the frustum with `padding` (1 = exactly touching the edges).
 *
 * The horizontal half-angle is derived from the vertical fov and the aspect, so
 * a narrow (portrait) viewport automatically pulls the camera back instead of
 * cropping the character's shoulders. `halfDepth` accounts for the box having
 * volume: its nearest face is closer to the camera than its centre.
 */
export function fitDistance(halfWidth: number, halfHeight: number, fovDeg: number, aspect: number, padding = 1.12, halfDepth = 0): number {
  const vFov = (clamp(fovDeg, 1, 179) * Math.PI) / 180
  const hFov = 2 * Math.atan(Math.tan(vFov / 2) * aspect)
  const byHeight = halfHeight / Math.tan(vFov / 2)
  const byWidth = halfWidth / Math.tan(hFov / 2)
  // The box has depth, so its nearest face is closer than its centre: add the
  // half depth to the distance so the near face still fits the frustum.
  return Math.max(byHeight, byWidth) * Math.max(1, padding) + halfDepth
}

/**
 * Frames a bounding box for a perspective camera.
 *
 * `fov` is chosen from the viewport shape: tall/narrow viewports get a wider
 * field of view so the character is not pushed so far back that it becomes a
 * speck, wide viewports get a tighter one. The returned distance always fits
 * the whole box, so nothing is ever cropped.
 */
export function frameBox(box: Box3Like, viewport: Size, options: { padding?: number; minFov?: number; maxFov?: number } = {}): Framing {
  const padding = options.padding ?? 1.12
  const minFov = options.minFov ?? MIN_FOV
  const maxFov = options.maxFov ?? MAX_FOV
  const aspect = safeAspect(viewport.width, viewport.height)

  const halfWidth = Math.max(0.001, (box.max.x - box.min.x) / 2)
  const halfHeight = Math.max(0.001, (box.max.y - box.min.y) / 2)
  const halfDepth = Math.max(0, (box.max.z - box.min.z) / 2)
  // The preview spins the model, so the widest silhouette is the box's
  // horizontal diagonal, not its X extent.
  const halfSpan = Math.hypot(halfWidth, halfDepth)
  const center = {
    x: (box.max.x + box.min.x) / 2,
    y: (box.max.y + box.min.y) / 2,
    z: (box.max.z + box.min.z) / 2,
  }

  // Portrait viewports need a wider lens; landscape ones can use a tighter one.
  const fov = clamp(MAX_FOV - (aspect - 0.5) * 12, minFov, maxFov)
  const distance = fitDistance(halfSpan, halfHeight, fov, aspect, padding, halfSpan)
  return { distance, fov, halfWidth, halfHeight, center }
}

/**
 * True when every corner of the box projects inside the camera frustum.
 * Used by the tests and by the preview's self-check.
 */
export function boxInsideFrustum(
  box: Box3Like,
  camera: { position: { x: number; y: number; z: number }; fov: number; aspect: number; near: number; far: number },
  forward: { x: number; y: number; z: number },
  up: { x: number; y: number; z: number },
  margin = 0.98
): boolean {
  const f = normalize(forward)
  const r = normalize(cross(f, up))
  const u = normalize(cross(r, f))
  const tanV = Math.tan((camera.fov * Math.PI) / 360)
  const tanH = tanV * camera.aspect
  const corners: [number, number, number][] = []
  for (const x of [box.min.x, box.max.x]) for (const y of [box.min.y, box.max.y]) for (const z of [box.min.z, box.max.z]) corners.push([x, y, z])

  return corners.every(([x, y, z]) => {
    const dx = x - camera.position.x
    const dy = y - camera.position.y
    const dz = z - camera.position.z
    const depth = dx * f.x + dy * f.y + dz * f.z
    if (depth < camera.near || depth > camera.far) return false
    const sx = (dx * r.x + dy * r.y + dz * r.z) / depth
    const sy = (dx * u.x + dy * u.y + dz * u.z) / depth
    return Math.abs(sx) <= tanH * margin && Math.abs(sy) <= tanV * margin
  })
}

function cross(a: { x: number; y: number; z: number }, b: { x: number; y: number; z: number }) {
  return { x: a.y * b.z - a.z * b.y, y: a.z * b.x - a.x * b.z, z: a.x * b.y - a.y * b.x }
}

function normalize(v: { x: number; y: number; z: number }) {
  const length = Math.hypot(v.x, v.y, v.z) || 1
  return { x: v.x / length, y: v.y / length, z: v.z / length }
}

/** Wraps an angle into (-PI, PI]. */
export function wrapAngle(angle: number): number {
  const tau = Math.PI * 2
  let value = angle % tau
  if (value > Math.PI) value -= tau
  if (value <= -Math.PI) value += tau
  return value
}

/** Shortest signed difference from `from` to `to`, in radians. */
export function angleDelta(from: number, to: number): number {
  return wrapAngle(to - from)
}

/** Frame-rate independent exponential smoothing factor. */
export function damp(delta: number, smoothing: number): number {
  return 1 - Math.exp(-Math.max(0, delta) * Math.max(0, smoothing))
}

/** Named preview angles, in radians around the Y axis (0 = facing the camera). */
export const VIEW_ANGLES = {
  front: 0,
  right: Math.PI / 2,
  back: Math.PI,
  left: -Math.PI / 2,
  threeQuarter: Math.PI / 4,
} as const

export type ViewName = keyof typeof VIEW_ANGLES
