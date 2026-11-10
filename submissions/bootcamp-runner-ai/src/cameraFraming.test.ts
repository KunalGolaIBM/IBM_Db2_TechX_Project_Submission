import { describe, expect, it } from 'vitest'
import { VIEW_ANGLES, angleDelta, boxInsideFrustum, fitDistance, frameBox, renderPixelRatio, safeAspect, wrapAngle } from './cameraFraming'

// The runner rig is ~1.9 units tall, ~0.9 wide and ~0.6 deep, standing on y = 0.
const runnerBox = { min: { x: -0.45, y: 0, z: -0.3 }, max: { x: 0.45, y: 1.9, z: 0.3 } }

const viewports = [
  { name: 'desktop 1920x1080', width: 1920, height: 1080 },
  { name: 'laptop 1366x768', width: 1366, height: 768 },
  { name: 'tablet landscape 1024x768', width: 1024, height: 768 },
  { name: 'tablet portrait 768x1024', width: 768, height: 1024 },
  { name: 'phone portrait 390x844', width: 390, height: 844 },
  { name: 'phone landscape 844x390', width: 844, height: 390 },
]

describe('camera framing', () => {
  it('never divides by zero on collapsed viewports', () => {
    expect(safeAspect(0, 0)).toBe(1)
    expect(safeAspect(390, 0)).toBeGreaterThan(0)
    expect(Number.isFinite(safeAspect(0, 844))).toBe(true)
  })

  it('caps the device pixel ratio', () => {
    expect(renderPixelRatio(3)).toBe(2)
    expect(renderPixelRatio(1.5)).toBe(1.5)
    expect(renderPixelRatio(0)).toBe(1)
    expect(renderPixelRatio(Number.NaN)).toBe(1)
  })

  it('pulls the camera back further for narrow viewports', () => {
    const wide = fitDistance(0.45, 0.95, 45, 16 / 9)
    const narrow = fitDistance(0.45, 0.95, 45, 390 / 844)
    expect(narrow).toBeGreaterThan(wide)
  })

  it.each(viewports)('keeps the whole runner inside the frustum at $name', ({ width, height }) => {
    const framing = frameBox(runnerBox, { width, height })
    const aspect = safeAspect(width, height)
    const camera = { position: { x: 0, y: framing.center.y, z: framing.center.z + framing.distance }, fov: framing.fov, aspect, near: 0.1, far: 100 }
    expect(boxInsideFrustum(runnerBox, camera, { x: 0, y: 0, z: -1 }, { x: 0, y: 1, z: 0 }, 1.01)).toBe(true)
  })

  it.each(viewports)('keeps the runner inside the frustum from every angle at $name', ({ width, height }) => {
    const framing = frameBox(runnerBox, { width, height })
    const aspect = safeAspect(width, height)
    for (const angle of Object.values(VIEW_ANGLES)) {
      // Rotating the model by `angle` is equivalent to orbiting the camera by -angle.
      const camera = {
        position: {
          x: framing.center.x + Math.sin(-angle) * framing.distance,
          y: framing.center.y,
          z: framing.center.z + Math.cos(-angle) * framing.distance,
        },
        fov: framing.fov,
        aspect,
        near: 0.1,
        far: 100,
      }
      const forward = { x: framing.center.x - camera.position.x, y: 0, z: framing.center.z - camera.position.z }
      expect(boxInsideFrustum(runnerBox, camera, forward, { x: 0, y: 1, z: 0 }, 1.01)).toBe(true)
    }
  })

  it('wraps angles and reports the shortest rotation', () => {
    expect(wrapAngle(Math.PI * 3)).toBeCloseTo(Math.PI)
    expect(angleDelta(Math.PI - 0.1, -Math.PI + 0.1)).toBeCloseTo(0.2)
  })
})
