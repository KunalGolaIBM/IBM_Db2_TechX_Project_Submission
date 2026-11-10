import { useCallback, useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { ArrowLeft, ArrowRight, Award, BarChart3, Coins, Gauge, Heart, Pause, Play, RotateCcw, Sparkles, Trophy, Zap } from 'lucide-react'
import { cloneRunner } from './characterBuilder'
import { characters, missionNames, worlds } from './data'
import { JUMP_SECONDS, SLIDE_SECONDS, jumpArc, laneLean, sampleRunPhase, slideCrouch } from './runnerMath'
import { applyRun, loadProgress, saveProgress, unlockCharacter, unlockWorld } from './progression'
import type { Character, PlayerProgress, Screen, SessionStats, WorldId } from './types'

const laneX = [-3.2, 0, 3.2]
const emptyStats = (characterId: string, world: WorldId): SessionStats => ({ score: 0, coins: 0, chips: 0, combo: 1, distance: 0, speed: 11, powerUp: null, powerUpTime: 0, hits: 0, world, characterId })

function RunnerScene({ lane, jumping, sliding, paused, character, worldId, onCoin, onChip, onHit, onDistance }: { lane: number; jumping: boolean; sliding: boolean; paused: boolean; character: Character; worldId: WorldId; onCoin: () => void; onChip: () => void; onHit: () => void; onDistance: (distance: number) => void }) {
  const mount = useRef<HTMLDivElement>(null)
  const state = useRef({ lane, jumping, sliding, paused })
  state.current = { lane, jumping, sliding, paused }
  useEffect(() => {
    if (!mount.current) return
    const world = worlds.find((item) => item.id === worldId) ?? worlds[0]
    const scene = new THREE.Scene()
    scene.fog = new THREE.Fog(world.colors[0], 22, 115)
    const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 160)
    camera.position.set(0, 6, 12); camera.lookAt(0, 1.6, -30)
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5)); renderer.setClearColor(world.colors[0], 1); mount.current.appendChild(renderer.domElement)
    scene.add(new THREE.HemisphereLight(world.colors[2], 0x101827, 2.4))
    const sun = new THREE.DirectionalLight(0xffffff, 2.5); sun.position.set(-8, 12, 5); scene.add(sun)
    const road = new THREE.Mesh(new THREE.PlaneGeometry(13, 160), new THREE.MeshStandardMaterial({ color: 0x111f2a, roughness: 0.8 }))
    road.rotation.x = -Math.PI / 2; road.position.set(0, -0.15, -50); scene.add(road)
    const lineMaterial = new THREE.MeshBasicMaterial({ color: world.colors[2], transparent: true, opacity: 0.55 })
    for (const x of [-1.6, 1.6]) { const line = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.02, 160), lineMaterial); line.position.set(x, 0, -50); scene.add(line) }
    const grid = new THREE.GridHelper(150, 30, world.colors[1], world.colors[1]); grid.position.y = -0.12; grid.position.z = -50; scene.add(grid)
    const { mesh: player, rig } = cloneRunner(character); player.position.set(0, 0, 5); scene.add(player)
    const objects: { mesh: THREE.Object3D; lane: number; type: 'coin' | 'chip' | 'block'; z: number; active: boolean }[] = []
    const coin = new THREE.Mesh(new THREE.TorusGeometry(0.38, 0.12, 8, 16), new THREE.MeshStandardMaterial({ color: 0xffd166, emissive: 0x9a5b00, emissiveIntensity: 0.4 }))
    const chip = new THREE.Mesh(new THREE.OctahedronGeometry(0.42), new THREE.MeshStandardMaterial({ color: 0x6deaff, emissive: 0x1260a5, emissiveIntensity: 0.7 }))
    const block = new THREE.Mesh(new THREE.BoxGeometry(1.7, 1.6, 1.7), new THREE.MeshStandardMaterial({ color: 0xe85252, emissive: 0x431313, emissiveIntensity: 0.4 }))
    for (let i = 0; i < 12; i += 1) { const type: 'coin' | 'chip' | 'block' = i % 5 === 0 ? 'chip' : i % 3 === 2 ? 'block' : 'coin'; const mesh = (type === 'chip' ? chip : type === 'block' ? block : coin).clone(); const object = { mesh, lane: i % 3, type, z: -18 - i * 13, active: true }; mesh.position.set(laneX[object.lane], type === 'block' ? 0.8 : 1.4, object.z); scene.add(mesh); objects.push(object) }
    let frame = 0; let last = performance.now(); let runTime = 0; let jumpProgress = 1; let slideProgress = 1; let previousJumping = false; let previousSliding = false
    const resize = () => { if (!mount.current) return; const { clientWidth, clientHeight } = mount.current; camera.aspect = clientWidth / Math.max(clientHeight, 1); camera.updateProjectionMatrix(); renderer.setSize(clientWidth, clientHeight, false) }
    const animate = (now: number) => {
      const delta = Math.min((now - last) / 1000, 0.05); last = now; const activeDelta = state.current.paused ? 0 : delta
      runTime += activeDelta; const speed = Math.min(24, 11 + runTime / 10); onDistance(activeDelta * speed)
      if (state.current.jumping && !previousJumping) jumpProgress = 0
      if (state.current.sliding && !previousSliding) slideProgress = 0
      previousJumping = state.current.jumping; previousSliding = state.current.sliding
      jumpProgress = state.current.jumping ? Math.min(1, jumpProgress + activeDelta / JUMP_SECONDS) : 1
      slideProgress = state.current.sliding ? Math.min(1, slideProgress + activeDelta / SLIDE_SECONDS) : 1
      const targetX = laneX[state.current.lane]; player.position.x += (targetX - player.position.x) * Math.min(1, activeDelta * 10)
      const phase = sampleRunPhase(runTime, speed / 13); const jumpHeight = state.current.jumping ? jumpArc(jumpProgress) * 1.15 : 0; const crouch = state.current.sliding ? slideCrouch(slideProgress) : 0
      player.position.y = jumpHeight; player.scale.y = 1 - crouch * 0.4; player.rotation.z = laneLean(player.position.x, targetX, 3.2)
      rig.pelvis.position.y = 1.02 + phase.bob; rig.torso.rotation.x = phase.pitch; rig.torso.rotation.z = phase.roll; rig.head.rotation.x = phase.headPitch
      rig.shoulderL.rotation.z = phase.shoulder; rig.shoulderR.rotation.z = -phase.shoulder; rig.elbowL.rotation.x = phase.elbow; rig.elbowR.rotation.x = -phase.elbow
      rig.hipL.rotation.x = phase.hip; rig.hipR.rotation.x = -phase.hip; rig.kneeL.rotation.x = phase.knee; rig.kneeR.rotation.x = Math.max(0, -phase.knee * 0.7)
      rig.footL.rotation.x = phase.ankle; rig.footR.rotation.x = -phase.ankle; rig.shadow.scale.setScalar(1 - jumpHeight * 0.25)
      for (const object of objects) {
        object.z += speed * activeDelta; object.mesh.position.z = object.z; object.mesh.rotation.y += activeDelta * 3
        if (object.z > 8) { object.z = -95 - Math.random() * 24; object.lane = Math.floor(Math.random() * 3); object.mesh.position.x = laneX[object.lane]; object.active = true }
        if (object.active && object.z > 3.8 && object.z < 5.8 && object.lane === state.current.lane) {
          object.active = false
          if (object.type === 'coin') onCoin(); else if (object.type === 'chip') onChip(); else if (!state.current.jumping && !state.current.sliding) onHit()
        }
      }
      frame = requestAnimationFrame(animate); renderer.render(scene, camera)
    }
    resize(); window.addEventListener('resize', resize); frame = requestAnimationFrame(animate)
    return () => { cancelAnimationFrame(frame); window.removeEventListener('resize', resize); renderer.dispose(); renderer.domElement.remove() }
  }, [character, onChip, onCoin, onDistance, onHit, worldId])
  return <div className="scene" ref={mount} aria-label="Three-dimensional endless runner scene" />
}

function App() {
  const [screen, setScreen] = useState<Screen>('menu')
  const [progress, setProgress] = useState<PlayerProgress>(() => loadProgress())
  const [lane, setLane] = useState(1); const [jumping, setJumping] = useState(false); const [sliding, setSliding] = useState(false); const [paused, setPaused] = useState(false)
  const character = characters.find((item) => item.id === progress.selectedCharacter) ?? characters[0]
  const [stats, setStats] = useState<SessionStats>(() => emptyStats(character.id, progress.selectedWorld))
  const world = worlds.find((item) => item.id === progress.selectedWorld) ?? worlds[0]
  const updateProgress = (next: PlayerProgress) => { setProgress(next); saveProgress(next) }
  const startGame = () => { setStats(emptyStats(character.id, progress.selectedWorld)); setLane(1); setPaused(false); setScreen('game') }
  const endGame = useCallback(() => { updateProgress(applyRun(progress, stats)); setScreen('results') }, [progress, stats])
  const onDistance = useCallback((distance: number) => setStats((value) => ({ ...value, distance: value.distance + distance, speed: 11 + value.distance / 100 })), [])
  const onCoin = useCallback(() => setStats((value) => ({ ...value, coins: value.coins + 1, score: value.score + 10 * value.combo, combo: Math.min(9, value.combo + 0.1) })), [])
  const onChip = useCallback(() => setStats((value) => ({ ...value, chips: value.chips + 1, score: value.score + 50 * value.combo })), [])
  const onHit = useCallback(() => setStats((value) => { const next = { ...value, hits: value.hits + 1, combo: 1, score: Math.max(0, value.score - 75) }; if (value.hits >= 2) window.setTimeout(endGame, 0); return next }), [endGame])
  useEffect(() => { const key = (event: KeyboardEvent) => { if (screen !== 'game' || paused || event.repeat) return; if (event.key === 'ArrowLeft' || event.key.toLowerCase() === 'a') setLane((v) => Math.max(0, v - 1)); if (event.key === 'ArrowRight' || event.key.toLowerCase() === 'd') setLane((v) => Math.min(2, v + 1)); if (event.key === 'ArrowUp' || event.key.toLowerCase() === 'w' || event.key === ' ') { event.preventDefault(); setJumping(true); window.setTimeout(() => setJumping(false), 600) }; if (event.key === 'ArrowDown' || event.key.toLowerCase() === 's') { event.preventDefault(); setSliding(true); window.setTimeout(() => setSliding(false), 700) }; if (event.key === 'p' || event.key === 'Escape') setPaused(true) }; window.addEventListener('keydown', key); return () => window.removeEventListener('keydown', key) }, [paused, screen])

  if (screen === 'game') return <main className="game-shell"><RunnerScene lane={lane} jumping={jumping} sliding={sliding} paused={paused} character={character} worldId={world.id} onCoin={onCoin} onChip={onChip} onHit={onHit} onDistance={onDistance} /><header className="game-header"><div className="brand compact"><span className="brand-mark"><Zap size={16} /></span> AI CEO EDITION</div><div className="hud-stats"><span><Trophy size={16} /> {Math.floor(stats.score).toLocaleString()}</span><span><Coins size={16} /> {stats.coins}</span><span><Sparkles size={16} /> {stats.chips}</span><span><Heart size={16} /> {Math.max(0, 3 - stats.hits)}</span><span><Gauge size={16} /> {Math.floor(stats.speed)}</span></div><button className="icon-button" onClick={() => setPaused(true)} aria-label="Pause"><Pause size={19} /></button></header><div className="arcade-label"><strong>{character.name}</strong><span>{world.name} · COMBO x{stats.combo.toFixed(1)}</span></div><div className="touch-controls"><button onClick={() => setLane((v) => Math.max(0, v - 1))} aria-label="Move left"><ArrowLeft /></button><button onClick={() => { setJumping(true); window.setTimeout(() => setJumping(false), 600) }} aria-label="Jump"><span>JUMP</span></button><button onClick={() => { setSliding(true); window.setTimeout(() => setSliding(false), 700) }} aria-label="Slide"><span>SLIDE</span></button><button onClick={() => setLane((v) => Math.min(2, v + 1))} aria-label="Move right"><ArrowRight /></button></div>{paused && <div className="modal-backdrop"><div className="pause-card"><span className="eyebrow">RUN PAUSED</span><h2>Hold your line.</h2><p>Your runner and the track are frozen safely.</p><button className="primary-button" onClick={() => setPaused(false)}><Play size={18} /> Resume</button><button className="text-button" onClick={() => setScreen('menu')}>Quit run</button></div></div>}</main>
  if (screen === 'results') return <main className="app-shell results-screen"><div className="results-card"><span className="brand-mark large"><Award /></span><span className="eyebrow">RUN COMPLETE</span><h1>{character.name} cleared {world.name}.</h1><div className="result-grid"><div><strong>{Math.floor(stats.score).toLocaleString()}</strong><span>Score</span></div><div><strong>{Math.floor(stats.distance)}m</strong><span>Distance</span></div><div><strong>{stats.coins}</strong><span>Coins</span></div></div><p className="muted">Personal best: {progress.bestScore.toLocaleString()} · Total runs: {progress.totalRuns}</p><div className="result-actions"><button className="primary-button" onClick={startGame}><RotateCcw size={18} /> Run again</button><button className="text-button" onClick={() => setScreen('menu')}>Return to menu</button></div></div></main>
  if (screen === 'characters' || screen === 'worlds' || screen === 'dashboard') return <main className="app-shell dashboard-screen"><header className="topbar"><div className="brand"><span className="brand-mark"><BarChart3 size={18} /></span><span>AI CEO<br /><strong>EDITION</strong></span></div><button className="text-button" onClick={() => setScreen('menu')}>Back</button></header>{screen === 'characters' && <><div className="dashboard-hero"><div><span className="eyebrow">CHARACTER COLLECTION</span><h1>Choose your CEO.</h1></div></div><div className="collection-grid">{characters.map((item) => { const unlocked = progress.unlockedCharacters.includes(item.id); return <article className={`collection-card ${unlocked ? '' : 'locked'}`} key={item.id}><div className="mini-avatar" style={{ background: `linear-gradient(145deg, ${item.color}, ${item.accent})` }} /><h2>{item.name}</h2><p>{item.role}</p><small>{unlocked ? item.effect : `${item.unlockCost} coins to unlock`}</small><button className="primary-button" onClick={() => unlocked ? updateProgress({ ...progress, selectedCharacter: item.id }) : updateProgress(unlockCharacter(progress, item.id))}>{unlocked && progress.selectedCharacter === item.id ? 'Selected' : unlocked ? 'Select' : 'Unlock'}</button></article> })}</div></>}{screen === 'worlds' && <><div className="dashboard-hero"><div><span className="eyebrow">WORLD SELECT</span><h1>Run the AI world.</h1></div></div><div className="collection-grid">{worlds.map((item) => { const unlocked = progress.unlockedWorlds.includes(item.id); return <article className="collection-card" key={item.id}><div className="world-swatch" style={{ background: `linear-gradient(135deg, #${item.colors[0].toString(16)}, #${item.colors[2].toString(16)})` }} /><h2>{item.name}</h2><p>{item.subtitle}</p><small>{unlocked ? 'Unlocked' : `${item.unlockCost} coins to unlock`}</small><button className="primary-button" onClick={() => unlocked ? updateProgress({ ...progress, selectedWorld: item.id }) : updateProgress(unlockWorld(progress, item.id))}>{unlocked && progress.selectedWorld === item.id ? 'Selected' : unlocked ? 'Select' : 'Unlock'}</button></article> })}</div></>}{screen === 'dashboard' && <><div className="dashboard-hero"><div><span className="eyebrow">PLAYER PROFILE</span><h1>Run history.</h1></div></div><div className="dashboard-grid"><div><strong>{progress.bestScore.toLocaleString()}</strong><span>Personal best</span></div><div><strong>{progress.totalRuns}</strong><span>Total runs</span></div><div><strong>{Math.floor(progress.distance)}m</strong><span>Total distance</span></div><div><strong>{progress.totalCoins}</strong><span>Coins collected</span></div></div><section className="dashboard-panel"><span className="eyebrow">ACHIEVEMENTS</span><p className="muted">{progress.achievements.length ? progress.achievements.join(' · ') : 'Complete runs to unlock achievements.'}</p></section><section className="dashboard-panel"><span className="eyebrow">MISSIONS</span>{missionNames.map((mission) => <div className="topic-row" key={mission}><span>{mission}</span><strong>{progress.missions[mission] ?? 0}</strong></div>)}</section></>}</main>
  return <main className="app-shell"><div className="noise" /><header className="topbar"><div className="brand"><span className="brand-mark"><Zap size={18} /></span><span>BOOTCAMP RUNNER<br /><strong>AI CEO EDITION</strong></span></div><span className="status-pill"><span className="pulse" /> RUN THE AI WORLD</span></header><section className="hero"><div className="hero-copy"><div className="eyebrow"><Sparkles size={14} /> ARCADE MODE</div><h1>Run the AI<br /><em>world.</em></h1><p>Unlock fictionalized CEO-inspired runners, dodge hardware, collect AI chips, and chase your next personal best.</p><button className="primary-button hero-button" onClick={startGame}>Start running <ArrowRight size={18} /></button></div><div className="hero-visual"><div className="orbit-ring ring-one" /><div className="orbit-ring ring-two" /><div className="hero-avatar" style={{ background: `linear-gradient(145deg, ${character.color}, ${character.accent})` }} /><div className="float-stat stat-one"><Trophy size={17} /><strong>{progress.bestScore.toLocaleString()}</strong><span>PERSONAL BEST</span></div><div className="float-stat stat-two"><Coins size={17} /><strong>{progress.totalCoins}</strong><span>COINS BANKED</span></div></div></section><section className="setup-panel"><div className="setup-title"><Gauge size={18} /><div><strong>{character.name} · {world.name}</strong><span>{character.effect}</span></div></div><div className="setup-footer"><span>{progress.unlockedCharacters.length}/{characters.length} runners · {progress.unlockedWorlds.length}/{worlds.length} worlds unlocked</span><div className="menu-actions"><button className="text-button" onClick={() => setScreen('characters')}>Collection</button><button className="text-button" onClick={() => setScreen('worlds')}>Worlds</button><button className="text-button" onClick={() => setScreen('dashboard')}>Stats</button></div></div></section><footer className="footer-note">Keyboard: A/D or arrows move · W/Space jump · S slide · P pause · Touch controls supported</footer></main>
}

export default App
