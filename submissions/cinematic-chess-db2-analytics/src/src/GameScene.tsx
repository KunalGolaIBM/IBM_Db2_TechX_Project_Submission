import { Float, Sparkles } from '@react-three/drei'
import { Canvas, type ThreeEvent, useFrame, useThree } from '@react-three/fiber'
import { Bloom, EffectComposer, Vignette } from '@react-three/postprocessing'
import { easing } from 'maath'
import { useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import type { LastMove, Phase, ScenePiece } from './types'
import type { Square } from 'chess.js'

interface SceneProps {
  phase: Phase
  pieces: ScenePiece[]
  selected: Square | null
  legal: Square[]
  lastMove: LastMove | null
  playerColor: 'w' | 'b'
  scrollProgress: number
  inCheck: boolean
  isCheckmate: boolean
  onSquare: (square: Square) => void
}

const files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']

function createAuraTexture() {
  const canvas = document.createElement('canvas')
  canvas.width = 256
  canvas.height = 256
  const context = canvas.getContext('2d')
  if (context) {
    const gradient = context.createRadialGradient(128, 128, 0, 128, 128, 128)
    gradient.addColorStop(0, 'rgba(142, 70, 220, 1)')
    gradient.addColorStop(0.4, 'rgba(142, 70, 220, 0.4)')
    gradient.addColorStop(1, 'rgba(142, 70, 220, 0)')
    context.fillStyle = gradient
    context.fillRect(0, 0, 256, 256)
  }
  return canvas
}



function squarePosition(square: Square, flipped: boolean): [number, number, number] {
  const file = files.indexOf(square[0])
  const rank = Number(square[1]) - 1
  const x = flipped ? 3.5 - file : file - 3.5
  const z = flipped ? rank - 3.5 : 3.5 - rank
  return [x, 0.2, z]
}

function PieceShape({ piece, hovered }: { piece: ScenePiece; hovered: boolean }) {
  const white = piece.color === 'w'
  const color = white ? '#e7e4f2' : '#15101f'
  const emissive = hovered ? '#a865ff' : white ? '#160b2d' : '#4b1682'
  const material = (
    <meshPhysicalMaterial
      color={color}
      emissive={emissive}
      emissiveIntensity={hovered ? 1.8 : 0.18}
      metalness={piece.type === 'r' || piece.type === 'q' ? 0.35 : 0.12}
      roughness={white ? 0.16 : 0.1}
      clearcoat={1}
      clearcoatRoughness={0.08}
      transmission={white ? 0.04 : 0.12}
      thickness={1}
    />
  )
  const crown = {
    p: <mesh position={[0, 0.62, 0]} castShadow><sphereGeometry args={[0.23, 24, 16]} />{material}</mesh>,
    n: <mesh position={[0.08, 0.65, -0.02]} rotation={[0.1, 0, -0.28]} castShadow><coneGeometry args={[0.3, 0.72, 5]} />{material}</mesh>,
    b: <mesh position={[0, 0.72, 0]} rotation={[0, 0, Math.PI / 4]} castShadow><octahedronGeometry args={[0.29, 0]} />{material}</mesh>,
    r: <mesh position={[0, 0.65, 0]} castShadow><cylinderGeometry args={[0.3, 0.36, 0.48, 8]} />{material}</mesh>,
    q: <group position={[0, 0.67, 0]}><mesh castShadow><octahedronGeometry args={[0.34, 0]} />{material}</mesh><mesh position={[0, 0.35, 0]} castShadow><sphereGeometry args={[0.12, 16, 12]} />{material}</mesh></group>,
    k: <group position={[0, 0.72, 0]}><mesh castShadow><dodecahedronGeometry args={[0.3, 0]} />{material}</mesh><mesh position={[0, 0.38, 0]} castShadow><boxGeometry args={[0.1, 0.42, 0.1]} />{material}</mesh><mesh position={[0, 0.43, 0]} castShadow><boxGeometry args={[0.32, 0.09, 0.09]} />{material}</mesh></group>,
  }[piece.type]

  return (
    <group scale={piece.type === 'p' ? 0.82 : piece.type === 'k' ? 1.14 : 1}>
      <mesh castShadow><cylinderGeometry args={[0.38, 0.46, 0.16, 32]} />{material}</mesh>
      <mesh position={[0, 0.3, 0]} castShadow><cylinderGeometry args={[0.22, 0.34, 0.55, 20]} />{material}</mesh>
      {crown}
    </group>
  )
}

function ChessPiece({ piece, flipped, onSquare }: { piece: ScenePiece; flipped: boolean; onSquare: (square: Square) => void }) {
  const ref = useRef<THREE.Group>(null)
  const [x, y, z] = squarePosition(piece.square, flipped)
  const [hovered, setHovered] = useState(false)
  
  useFrame((state) => {
    if (!ref.current) return
    const delta = state.clock.getDelta()
    if (piece.captured) {
      easing.damp(ref.current.position, 'y', -2, 0.2, delta)
      easing.damp3(ref.current.scale, [0, 0, 0], 0.2, delta)
      return
    }
    ref.current.position.y = y + Math.sin(state.clock.elapsedTime * 1.25 + x + z) * 0.025
    ref.current.rotation.y = Math.sin(state.clock.elapsedTime * 0.45 + x) * 0.018
    easing.damp3(ref.current.position, [x, ref.current.position.y, z], 0.16, delta)
    const targetScale = hovered ? 1.04 : 1
    easing.damp(ref.current.scale, 'x', targetScale, 0.18, delta)
    easing.damp(ref.current.scale, 'y', targetScale, 0.18, delta)
    easing.damp(ref.current.scale, 'z', targetScale, 0.18, delta)
  })
  return (
    <group
      ref={ref}
      position={[x, y, z]}
      onClick={(event) => { event.stopPropagation(); onSquare(piece.square) }}
      onPointerOver={(event) => { event.stopPropagation(); setHovered(true); document.body.style.cursor = 'pointer' }}
      onPointerOut={() => { setHovered(false); document.body.style.cursor = 'default' }}
    >
      <PieceShape piece={piece} hovered={hovered} />
    </group>
  )
}

function Arena({ phase, pieces, selected, legal, lastMove, playerColor, scrollProgress, onSquare }: SceneProps) {
  const group = useRef<THREE.Group>(null)
  const isGame = ['setup', 'playing', 'paused', 'gameOver'].includes(phase)
  const flipped = playerColor === 'b' && isGame
  useFrame((state, delta) => {
    if (!group.current) return
    const t = state.clock.elapsedTime
    const targetRotation = isGame ? 0 : -0.32 + scrollProgress * 0.28 + Math.sin(t * 0.08) * 0.08
    easing.damp(group.current.rotation, 'y', targetRotation, 0.35, delta)
    easing.damp(group.current.position, 'y', Math.sin(t * 0.55) * 0.09 - (isGame ? 0.2 : 0), 0.4, delta)
  })
  const squares = useMemo(() => {
    const result: { square: Square; x: number; z: number; dark: boolean }[] = []
    for (let rank = 1; rank <= 8; rank++) {
      for (let file = 0; file < 8; file++) {
        result.push({ square: `${files[file]}${rank}` as Square, x: file - 3.5, z: 3.5 - (rank - 1), dark: (rank + file) % 2 === 0 })
      }
    }
    return result
  }, [])

  return (
    <Float speed={0.55} rotationIntensity={0.025} floatIntensity={0.12}>
      <group ref={group}>
        <mesh position={[0, -0.33, 0]} receiveShadow castShadow>
          <boxGeometry args={[9.35, 0.55, 9.35, 4, 1, 4]} />
          <meshPhysicalMaterial color="#08050e" metalness={0.78} roughness={0.13} clearcoat={1} />
        </mesh>
        <mesh position={[0, -0.03, 0]}>
          <boxGeometry args={[8.55, 0.16, 8.55]} />
          <meshStandardMaterial color="#7c25d8" emissive="#6f1fc2" emissiveIntensity={3.2} toneMapped={false} />
        </mesh>
        {squares.map(({ square, x, z, dark }) => {
          const isSelected = selected === square
          const isLegal = legal.includes(square)
          const isLast = lastMove?.from === square || lastMove?.to === square
          const px = flipped ? -x : x
          const pz = flipped ? -z : z
          return (
            <mesh
              key={square}
              position={[px, 0.09, pz]}
              receiveShadow
              onClick={(event: ThreeEvent<MouseEvent>) => { event.stopPropagation(); onSquare(square) }}
              onPointerOver={() => { document.body.style.cursor = 'pointer' }}
              onPointerOut={() => { document.body.style.cursor = 'default' }}
            >
              <boxGeometry args={[0.965, 0.13, 0.965]} />
              <meshPhysicalMaterial
                color={isSelected ? '#b46cff' : isLegal ? '#50217d' : isLast ? '#48205f' : dark ? '#100c18' : '#272130'}
                emissive={isSelected ? '#7b2ccf' : isLegal ? '#501485' : isLast ? '#38144e' : '#000000'}
                emissiveIntensity={isSelected || isLegal || isLast ? 1.2 : 0}
                metalness={0.18}
                roughness={dark ? 0.1 : 0.2}
                clearcoat={1}
                clearcoatRoughness={0.06}
              />
              {isLegal && <mesh position={[0, 0.085, 0]} rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[0.11, 0.16, 24]} /><meshBasicMaterial color="#d9b7ff" transparent opacity={0.78} toneMapped={false} /></mesh>}
            </mesh>
          )
        })}
        {pieces.map((piece) => <ChessPiece key={piece.id} piece={piece} flipped={flipped} onSquare={onSquare} />)}
        <mesh position={[0, -0.6, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <planeGeometry args={[22, 22]} />
          <meshBasicMaterial transparent opacity={0.65} depthWrite={false} blending={THREE.AdditiveBlending}>
            <canvasTexture attach="map" image={createAuraTexture()} />
          </meshBasicMaterial>
        </mesh>
      </group>
    </Float>
  )
}

function CameraRig({ phase, scrollProgress, inCheck, isCheckmate }: Pick<SceneProps, 'phase' | 'scrollProgress' | 'inCheck' | 'isCheckmate'>) {
  const { camera, pointer, size } = useThree()
  useFrame((state, delta) => {
    const isGame = ['setup', 'playing', 'paused', 'gameOver'].includes(phase)
    const isReview = phase === 'review' || phase === 'analysis'
    const compact = size.width < 760
    
    let targetZ = isGame ? (compact ? 15.8 : 10.9) : 13.8 - scrollProgress * 2.4
    let targetX = isGame ? 0 : 0.65 + pointer.x * 0.35
    let targetY = isGame ? (compact ? 13.4 : 10.2) : 8.1 + scrollProgress * 1.25 + pointer.y * 0.2
    
    if (isReview) {
      targetY = compact ? 15.0 : 12.0
      targetZ = compact ? 12.0 : 8.0
    }
    
    if (isCheckmate) {
      const t = state.clock.elapsedTime
      targetX = Math.sin(t * 0.3) * 12
      targetZ = Math.cos(t * 0.3) * 12
      targetY = 9 + Math.sin(t * 0.15) * 2
    }

    if (inCheck && !isCheckmate) {
      const shake = Math.sin(state.clock.elapsedTime * 40) * 0.05
      targetX += shake
      targetY += shake
    }

    easing.damp3(camera.position, [targetX, targetY, targetZ], 0.38, delta)
    if (camera instanceof THREE.PerspectiveCamera) {
      easing.damp(camera, 'fov', compact && isGame ? 56 : 37, 0.32, delta)
      camera.updateProjectionMatrix()
    }
    camera.lookAt(0, 0, 0)
  })
  return null
}

function SceneContent(props: SceneProps) {
  const { size } = useThree()
  const quality = size.width < 800 ? 'low' : 'high'
  
  return (
    <>
      <ambientLight intensity={0.45} color="#8563b5" />
      <hemisphereLight intensity={0.7} color="#d9c6ff" groundColor="#0c1730" />
      <directionalLight castShadow position={[4, 11, 6]} intensity={3.0} color="#fff5ff" shadow-mapSize={[quality === 'high' ? 2048 : 1024, quality === 'high' ? 2048 : 1024]} />
      
      <pointLight position={[-7, 2, 1]} intensity={58} distance={18} color={props.inCheck ? "#ff2b2b" : "#6c4dff"} />
      <pointLight position={[6, 3, -3]} intensity={48} distance={18} color="#e73cff" />
      <spotLight position={[0, 11, -6]} intensity={75} angle={0.42} penumbra={0.9} color="#8638ff" />
      
      <Sparkles count={quality === 'high' ? 120 : 50} scale={[25, 15, 25]} size={1.5} speed={props.isCheckmate ? 0.8 : props.inCheck ? 0.4 : 0.1} opacity={0.6} color={props.isCheckmate ? "#ffd700" : props.inCheck ? "#ff4444" : "#e0c2ff"} />

      <Arena {...props} />
      <CameraRig phase={props.phase} scrollProgress={props.scrollProgress} inCheck={props.inCheck} isCheckmate={props.isCheckmate} />
      
      <EffectComposer multisampling={quality === 'high' ? 4 : 0}>
        <Bloom intensity={quality === 'high' ? 0.35 : 0.25} luminanceThreshold={0.7} mipmapBlur />
        <Vignette eskil={false} offset={0.12} darkness={0.55} />
      </EffectComposer>
    </>
  )
}

export default function GameScene(props: SceneProps) {
  return (
    <Canvas
      id="chess-canvas"
      dpr={[1, 1.75]}
      camera={{ position: [0, 8, 14], fov: 37, near: 0.1, far: 100 }}
      gl={{ antialias: true, alpha: false, powerPreference: 'high-performance', toneMapping: THREE.ACESFilmicToneMapping }}
      performance={{ min: 0.75 }}
      shadows
    >
      <SceneContent {...props} />
    </Canvas>
  )
}
