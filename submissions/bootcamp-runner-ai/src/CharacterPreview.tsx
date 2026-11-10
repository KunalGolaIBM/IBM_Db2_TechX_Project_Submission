import { useCallback, useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { RotateCcw } from 'lucide-react'
import { cloneRunner, measureRunner } from './characterBuilder'
import { VIEW_ANGLES, angleDelta, damp, frameBox, renderPixelRatio, safeAspect, wrapAngle, type ViewName } from './cameraFraming'
import { sampleRunPhase } from './runnerMath'
import type { Character } from './types'

const VIEW_LABELS: { id: ViewName; label: string }[] = [
  { id: 'front', label: 'Front' },
  { id: 'threeQuarter', label: '3/4' },
  { id: 'right', label: 'Right' },
  { id: 'back', label: 'Back' },
  { id: 'left', label: 'Left' },
]

/** Radians of yaw per CSS pixel dragged. */
const DRAG_SENSITIVITY = 0.011
/** How quickly the model eases toward the requested yaw (per second). */
const ROTATION_SMOOTHING = 9
/** Idle sway amplitude, in radians. */
const IDLE_SWAY = 0.16

interface Props {
  character: Character
  /** Called with the current yaw so the parent can show the angle readout. */
  onAngleChange?: (degrees: number) => void
}

/**
 * Renders one runner in its own canvas, framed from its measured bounding box
 * and re-framed on every resize. The model can be dragged through a full 360°
 * and always stays fully inside the viewport.
 */
export function CharacterPreview({ character, onAngleChange }: Props) {
  const mount = useRef<HTMLDivElement>(null)
  const stage = useRef<HTMLDivElement>(null)
  const [activeView, setActiveView] = useState<ViewName | null>('front')
  const [dragging, setDragging] = useState(false)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Mutable state shared with the render loop without re-rendering React.
  const control = useRef({ targetYaw: 0, yaw: 0, dragging: false, lastPointerX: 0, pointerId: -1, reset: false })
  const angleRef = useRef(onAngleChange)
  angleRef.current = onAngleChange

  const setView = useCallback((view: ViewName) => {
    control.current.targetYaw = VIEW_ANGLES[view]
    control.current.reset = false
    setActiveView(view)
  }, [])

  const resetCamera = useCallback(() => {
    control.current.targetYaw = 0
    control.current.reset = true
    setActiveView('front')
  }, [])

  useEffect(() => {
    const host = mount.current
    const stageEl = stage.current
    if (!host || !stageEl) return

    let renderer: THREE.WebGLRenderer
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' })
    } catch {
      setError('WebGL is unavailable in this browser, so the 3D preview cannot be shown.')
      return
    }
    renderer.setClearColor(0x000000, 0)
    renderer.outputColorSpace = THREE.SRGBColorSpace
    renderer.domElement.className = 'preview-canvas'
    host.appendChild(renderer.domElement)

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 100)

    // Lighting is attached to the camera so the character is lit from every
    // angle: a fixed world light would leave the back view in shadow.
    const key = new THREE.DirectionalLight(0xffffff, 2.6)
    key.position.set(2.2, 3.4, 4.2)
    const fill = new THREE.DirectionalLight(0x8fd8ff, 1.5)
    fill.position.set(-3.2, 1.4, -2.6)
    const rim = new THREE.DirectionalLight(0xffffff, 1.1)
    rim.position.set(0, 2.2, -4.5)
    camera.add(key, fill, rim)
    scene.add(camera)
    scene.add(new THREE.HemisphereLight(0xbfe9ff, 0x0a1620, 1.5))

    const { mesh, rig } = cloneRunner(character)
    scene.add(mesh)

    // Ground disc + contact shadow give the character a floor to stand on.
    const floor = new THREE.Mesh(
      new THREE.CircleGeometry(1.5, 48),
      new THREE.MeshBasicMaterial({ color: 0x0d2530, transparent: true, opacity: 0.55, depthWrite: false })
    )
    floor.rotation.x = -Math.PI / 2
    floor.position.y = -0.002
    scene.add(floor)
    const ring = new THREE.Mesh(
      new THREE.RingGeometry(1.42, 1.5, 64),
      new THREE.MeshBasicMaterial({ color: new THREE.Color(character.color), transparent: true, opacity: 0.5, side: THREE.DoubleSide })
    )
    ring.rotation.x = -Math.PI / 2
    ring.position.y = 0.001
    scene.add(ring)

    // Measure the rest pose once: the idle animation only ever shrinks the
    // silhouette, so this box is a safe frame for every frame of the loop.
    const restBox = measureRunner(mesh)
    const restHeight = Math.max(0.5, restBox.max.y - restBox.min.y)
    const restCenterY = (restBox.max.y + restBox.min.y) / 2
    // The model spins, so the widest silhouette is the box's horizontal
    // diagonal. Framing against it means no angle can ever crop the body.
    const spinBox = new THREE.Box3(
      new THREE.Vector3(-Math.hypot(restBox.max.x, restBox.max.z), restBox.min.y, -Math.hypot(restBox.max.x, restBox.max.z)),
      new THREE.Vector3(Math.hypot(restBox.max.x, restBox.max.z), restBox.max.y, Math.hypot(restBox.max.x, restBox.max.z))
    )

    let width = 0
    let height = 0
    let distance = 4
    let fov = 40

    const applySize = () => {
      const rect = host.getBoundingClientRect()
      const nextWidth = Math.max(1, Math.round(rect.width))
      const nextHeight = Math.max(1, Math.round(rect.height))
      if (nextWidth === width && nextHeight === height) return
      width = nextWidth
      height = nextHeight
      renderer.setPixelRatio(renderPixelRatio(window.devicePixelRatio))
      renderer.setSize(width, height, false)
      camera.aspect = safeAspect(width, height)
      const framing = frameBox(spinBox, { width, height }, { padding: 1.12 })
      distance = framing.distance
      fov = framing.fov
      camera.fov = fov
      camera.near = Math.max(0.05, distance * 0.05)
      camera.far = distance * 6 + 20
      camera.updateProjectionMatrix()
      setReady(true)
    }

    applySize()

    // ResizeObserver catches container changes that `window.resize` misses
    // (side panels, orientation changes, CSS grid reflow).
    const observer = new ResizeObserver(applySize)
    observer.observe(host)
    window.addEventListener('resize', applySize)
    window.addEventListener('orientationchange', applySize)

    // --- pointer drag: 360° yaw -------------------------------------------
    const onPointerDown = (event: PointerEvent) => {
      if (event.button !== 0 && event.pointerType === 'mouse') return
      control.current.dragging = true
      control.current.pointerId = event.pointerId
      control.current.lastPointerX = event.clientX
      control.current.reset = false
      stageEl.setPointerCapture(event.pointerId)
      setDragging(true)
      setActiveView(null)
    }
    const onPointerMove = (event: PointerEvent) => {
      if (!control.current.dragging || event.pointerId !== control.current.pointerId) return
      const dx = event.clientX - control.current.lastPointerX
      control.current.lastPointerX = event.clientX
      control.current.targetYaw = wrapAngle(control.current.targetYaw + dx * DRAG_SENSITIVITY)
    }
    const endDrag = (event: PointerEvent) => {
      if (event.pointerId !== control.current.pointerId) return
      control.current.dragging = false
      control.current.pointerId = -1
      if (stageEl.hasPointerCapture(event.pointerId)) stageEl.releasePointerCapture(event.pointerId)
      setDragging(false)
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'ArrowLeft') {
        event.preventDefault()
        control.current.targetYaw = wrapAngle(control.current.targetYaw - 0.25)
        setActiveView(null)
      } else if (event.key === 'ArrowRight') {
        event.preventDefault()
        control.current.targetYaw = wrapAngle(control.current.targetYaw + 0.25)
        setActiveView(null)
      } else if (event.key === 'Home') {
        event.preventDefault()
        resetCamera()
      }
    }
    stageEl.addEventListener('pointerdown', onPointerDown)
    stageEl.addEventListener('pointermove', onPointerMove)
    stageEl.addEventListener('pointerup', endDrag)
    stageEl.addEventListener('pointercancel', endDrag)
    stageEl.addEventListener('keydown', onKeyDown)

    // --- render loop -------------------------------------------------------
    let frame = 0
    let last = performance.now()
    let elapsed = 0
    let lastReported = Number.NaN

    const animate = (now: number) => {
      const delta = Math.min((now - last) / 1000, 0.05)
      last = now
      elapsed += delta

      const state = control.current
      if (state.reset) {
        // Reset eases back to the front instead of snapping.
        state.targetYaw = 0
        if (Math.abs(state.yaw) < 0.01) state.reset = false
      }
      state.yaw = wrapAngle(state.yaw + angleDelta(state.yaw, state.targetYaw) * damp(delta, ROTATION_SMOOTHING))

      // Idle: a slow breathing sway plus a gentle run-in-place cycle, so the
      // character reads as alive without ever leaving the framed box.
      const phase = sampleRunPhase(elapsed * 0.55, 0.55)
      const sway = Math.sin(elapsed * 0.9) * IDLE_SWAY
      mesh.rotation.y = state.yaw + sway
      mesh.position.y = 0
      rig.pelvis.position.y = 1.02 + phase.bob * 0.5
      rig.torso.rotation.x = 0.05 + phase.pitch * 0.35
      rig.torso.rotation.z = phase.roll * 0.6
      rig.head.rotation.x = phase.headPitch * 0.5
      rig.head.rotation.y = Math.sin(elapsed * 0.6) * 0.12
      rig.shoulderL.rotation.z = (rig.shoulderL.userData.restZ ?? 0) + phase.shoulder * 0.35
      rig.shoulderR.rotation.z = (rig.shoulderR.userData.restZ ?? 0) - phase.shoulder * 0.35
      rig.elbowL.rotation.x = (rig.elbowL.userData.restX ?? 0) + phase.elbow * 0.4
      rig.elbowR.rotation.x = (rig.elbowR.userData.restX ?? 0) - phase.elbow * 0.4
      rig.hipL.rotation.x = phase.hip * 0.18
      rig.hipR.rotation.x = -phase.hip * 0.18
      rig.kneeL.rotation.x = phase.knee * 0.12
      rig.kneeR.rotation.x = Math.max(0, -phase.knee * 0.1)
      rig.footL.rotation.x = phase.ankle * 0.3
      rig.footR.rotation.x = -phase.ankle * 0.3
      rig.shadow.scale.setScalar(1)

      // Orbit the camera around the measured centre at the framed distance.
      // The camera sits slightly above the centre and looks down a little, so
      // the feet and the top of the head are both inside the frame.
      camera.position.set(0, restCenterY + restHeight * 0.1, distance)
      camera.lookAt(0, restCenterY, 0)

      const degrees = Math.round((((state.yaw * 180) / Math.PI) % 360 + 360) % 360)
      if (degrees !== lastReported) {
        lastReported = degrees
        angleRef.current?.(degrees)
      }

      renderer.render(scene, camera)
      frame = requestAnimationFrame(animate)
    }
    frame = requestAnimationFrame(animate)

    return () => {
      cancelAnimationFrame(frame)
      observer.disconnect()
      window.removeEventListener('resize', applySize)
      window.removeEventListener('orientationchange', applySize)
      stageEl.removeEventListener('pointerdown', onPointerDown)
      stageEl.removeEventListener('pointermove', onPointerMove)
      stageEl.removeEventListener('pointerup', endDrag)
      stageEl.removeEventListener('pointercancel', endDrag)
      stageEl.removeEventListener('keydown', onKeyDown)
      // The runner's geometry and materials are shared with the character
      // cache, so only the preview's own floor/ring are disposed here.
      floor.geometry.dispose()
      ;(floor.material as THREE.Material).dispose()
      ring.geometry.dispose()
      ;(ring.material as THREE.Material).dispose()
      renderer.dispose()
      renderer.forceContextLoss()
      renderer.domElement.remove()
    }
  }, [character, resetCamera])

  return (
    <div className="preview">
      <div
        className={`preview-stage ${dragging ? 'is-dragging' : ''}`}
        ref={stage}
        tabIndex={0}
        role="img"
        aria-label={`${character.name} 3D preview. Drag horizontally to rotate, or use the arrow keys.`}
      >
        <div className="preview-canvas-host" ref={mount} />
        {!ready && !error && <span className="preview-status">Loading model…</span>}
        {error && <span className="preview-status error">{error}</span>}
        <span className="preview-hint">Drag to rotate · 360°</span>
      </div>
      <div className="preview-controls">
        <div className="view-buttons" role="group" aria-label="Camera angle">
          {VIEW_LABELS.map((view) => (
            <button
              key={view.id}
              type="button"
              className={activeView === view.id ? 'active' : ''}
              aria-pressed={activeView === view.id}
              onClick={() => setView(view.id)}
            >
              {view.label}
            </button>
          ))}
        </div>
        <button type="button" className="reset-button" onClick={resetCamera} aria-label="Reset camera">
          <RotateCcw size={15} /> Reset
        </button>
      </div>
    </div>
  )
}
