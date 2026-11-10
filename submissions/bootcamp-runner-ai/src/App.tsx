import { useCallback, useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { ArrowLeft, ArrowRight, Award, BarChart3, ChevronDown, CircleHelp, Coins, Gauge, Heart, Pause, Play, RotateCcw, Sparkles, Trophy, Zap } from 'lucide-react'
import { characters, difficultySettings, modeSettings, samplePacks } from './data'
import { isGameOver, laneAfterMove, scoreAnswer } from './gameMath'
import { fetchDashboard, saveAttempt, type LearningDashboard } from './learningApi'
import type { Character, Difficulty, Mode, Screen, SessionStats } from './types'

const laneX = [-3.2, 0, 3.2]
const emptyStats: SessionStats = { score: 0, coins: 0, correct: 0, answered: 0, bestStreak: 0, distance: 0 }

function RunnerScene({ lane, jumping, sliding, color, onCoin }: { lane: number; jumping: boolean; sliding: boolean; color: string; onCoin: () => void }) {
  const mount = useRef<HTMLDivElement>(null)
  const state = useRef({ lane, jumping, sliding })
  state.current = { lane, jumping, sliding }

  useEffect(() => {
    if (!mount.current) return
    const scene = new THREE.Scene()
    scene.fog = new THREE.Fog(0x071016, 22, 115)
    const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 160)
    camera.position.set(0, 6, 12)
    camera.lookAt(0, 2, -30)
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5))
    renderer.setClearColor(0x071016, 1)
    mount.current.appendChild(renderer.domElement)
    const ambient = new THREE.HemisphereLight(0x8eeaff, 0x101827, 2.4)
    scene.add(ambient)
    const sun = new THREE.DirectionalLight(0xffffff, 2.5)
    sun.position.set(-8, 12, 5)
    scene.add(sun)

    const road = new THREE.Mesh(new THREE.PlaneGeometry(13, 160), new THREE.MeshStandardMaterial({ color: 0x111f2a, roughness: 0.8 }))
    road.rotation.x = -Math.PI / 2
    road.position.set(0, -0.15, -50)
    scene.add(road)
    const lineMaterial = new THREE.MeshBasicMaterial({ color: 0x2c90a8, transparent: true, opacity: 0.55 })
    for (const x of [-1.6, 1.6]) {
      const line = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.02, 160), lineMaterial)
      line.position.set(x, 0, -50)
      scene.add(line)
    }
    const grid = new THREE.GridHelper(150, 30, 0x164456, 0x102a39)
    grid.position.y = -0.12
    grid.position.z = -50
    scene.add(grid)
    const player = new THREE.Group()
    const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.62, 1.4, 4, 10), new THREE.MeshStandardMaterial({ color }))
    body.position.y = 1.5
    player.add(body)
    const visor = new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.28, 0.1), new THREE.MeshBasicMaterial({ color: 0xe5fbff }))
    visor.position.set(0, 1.85, -0.58)
    player.add(visor)
    const pack = new THREE.Mesh(new THREE.BoxGeometry(0.8, 0.7, 0.28), new THREE.MeshStandardMaterial({ color: 0x172c46 }))
    pack.position.set(0, 1.35, 0.45)
    player.add(pack)
    player.position.set(0, 0, 5)
    scene.add(player)

    const objects: { mesh: THREE.Object3D; lane: number; type: 'coin' | 'block'; z: number; active: boolean }[] = []
    const reusableCoin = new THREE.Mesh(new THREE.TorusGeometry(0.38, 0.12, 8, 16), new THREE.MeshStandardMaterial({ color: 0xffd166, emissive: 0x9a5b00, emissiveIntensity: 0.4 }))
    const reusableBlock = new THREE.Mesh(new THREE.BoxGeometry(1.7, 1.6, 1.7), new THREE.MeshStandardMaterial({ color: 0xe85252, emissive: 0x431313, emissiveIntensity: 0.4 }))
    for (let i = 0; i < 9; i += 1) {
      const isCoin = i % 3 !== 2
      const mesh = (isCoin ? reusableCoin : reusableBlock).clone()
      const object = { mesh, lane: i % 3, type: isCoin ? 'coin' as const : 'block' as const, z: -18 - i * 13, active: true }
      mesh.position.set(laneX[object.lane], isCoin ? 1.4 : 0.8, object.z)
      scene.add(mesh)
      objects.push(object)
    }

    let frame = 0
    let last = performance.now()
    const resize = () => {
      if (!mount.current) return
      const { clientWidth, clientHeight } = mount.current
      camera.aspect = clientWidth / Math.max(clientHeight, 1)
      camera.updateProjectionMatrix()
      renderer.setSize(clientWidth, clientHeight, false)
    }
    const animate = (now: number) => {
      const delta = Math.min((now - last) / 1000, 0.05)
      last = now
      const speed = 11
      player.position.x += (laneX[state.current.lane] - player.position.x) * Math.min(1, delta * 10)
      player.position.y = state.current.jumping ? 1.15 : 0
      player.scale.y = state.current.sliding ? 0.55 : 1
      player.rotation.z = Math.sin(now / 120) * 0.025
      for (const object of objects) {
        object.z += speed * delta
        object.mesh.position.z = object.z
        object.mesh.rotation.y += delta * 3
        if (object.z > 8) {
          object.z = -95 - Math.random() * 24
          object.lane = Math.floor(Math.random() * 3)
          object.mesh.position.x = laneX[object.lane]
          object.active = true
        }
        if (object.active && object.z > 3.8 && object.z < 5.8 && object.lane === state.current.lane) {
          if (object.type === 'coin') {
            object.active = false
            onCoin()
          } else if (!state.current.jumping && !state.current.sliding) {
            object.active = false
          }
        }
      }
      frame = requestAnimationFrame(animate)
      renderer.render(scene, camera)
    }
    resize()
    window.addEventListener('resize', resize)
    frame = requestAnimationFrame(animate)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('resize', resize)
      renderer.dispose()
      scene.traverse((object) => {
        if (object instanceof THREE.Mesh) {
          object.geometry.dispose()
          if (Array.isArray(object.material)) object.material.forEach((material) => material.dispose())
          else object.material.dispose()
        }
      })
      renderer.domElement.remove()
    }
  }, [color, onCoin])

  return <div className="scene" ref={mount} aria-label="Three-dimensional runner scene" />
}

function App() {
  const [screen, setScreen] = useState<Screen>('menu')
  const [character, setCharacter] = useState<Character>(characters[0])
  const [mode, setMode] = useState<Mode>('Explore')
  const [difficulty, setDifficulty] = useState<Difficulty>('Normal')
  const [packId, setPackId] = useState(samplePacks[0].id)
  const [lane, setLane] = useState(1)
  const [questionIndex, setQuestionIndex] = useState(0)
  const [stats, setStats] = useState(emptyStats)
  const [lives, setLives] = useState(difficultySettings.Normal.lives)
  const [jumping, setJumping] = useState(false)
  const [sliding, setSliding] = useState(false)
  const [paused, setPaused] = useState(false)
  const [feedback, setFeedback] = useState<'correct' | 'wrong' | null>(null)
  const [customPack, setCustomPack] = useState<typeof samplePacks[number] | null>(null)
  const [dashboard, setDashboard] = useState<LearningDashboard | null>(null)
  const [dashboardError, setDashboardError] = useState<string | null>(null)
  const pack = customPack?.id === packId ? customPack : samplePacks.find((item) => item.id === packId) ?? samplePacks[0]
  const question = pack.questions[questionIndex % pack.questions.length]
  const saveKey = 'bootcamp-runner-progress-v1'
  const learnerId = 'local-learner'

  const loadDashboard = useCallback(async () => {
    setDashboardError(null)
    try {
      setDashboard(await fetchDashboard(learnerId))
    } catch {
      setDashboardError('AI learning service is offline. Local play is still available.')
    }
  }, [])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (screen !== 'game' || paused) return
      if (event.repeat) return
      if (event.key === 'ArrowLeft' || event.key.toLowerCase() === 'a') setLane((value) => laneAfterMove(value, -1))
      if (event.key === 'ArrowRight' || event.key.toLowerCase() === 'd') setLane((value) => laneAfterMove(value, 1))
      if (event.key === 'ArrowUp' || event.key.toLowerCase() === 'w' || event.key === ' ') {
        event.preventDefault()
        setJumping(true)
        window.setTimeout(() => setJumping(false), 600)
      }
      if (event.key === 'ArrowDown' || event.key.toLowerCase() === 's') {
        event.preventDefault()
        setSliding(true)
        window.setTimeout(() => setSliding(false), 700)
      }
      if (event.key === 'Escape' || event.key.toLowerCase() === 'p') setPaused(true)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [paused, screen])

  const startGame = () => {
    const recommended = dashboard?.latest_recommendation?.recommended_difficulty
    const launchDifficulty = mode === 'Flow' && recommended
      ? (recommended[0].toUpperCase() + recommended.slice(1).toLowerCase()) as Difficulty
      : difficulty
    setStats(emptyStats)
    setDifficulty(launchDifficulty)
    setLives(difficultySettings[launchDifficulty].lives)
    setQuestionIndex(0)
    setLane(1)
    setFeedback(null)
    setPaused(false)
    setScreen('game')
  }
  const answer = useCallback((index: number) => {
    if (feedback || paused) return
    const correct = index === question.correctIndex
    const nextStats = scoreAnswer(stats, correct, difficulty)
    setStats(nextStats)
    void saveAttempt({
      learner_id: learnerId,
      topic: question.topic,
      score: correct ? 100 : 0,
      difficulty: question.difficulty === 'normal' ? 'medium' : question.difficulty,
      questions_count: 1,
    }).catch(() => undefined)
    setFeedback(correct ? 'correct' : 'wrong')
    if (!correct) setLives((value) => value - 1)
    window.setTimeout(() => {
      if (!correct && isGameOver(lives - 1)) {
        localStorage.setItem(saveKey, JSON.stringify({ bestScore: nextStats.score }))
        setScreen('results')
      } else {
        setQuestionIndex((value) => value + 1)
        setFeedback(null)
      }
    }, 1100)
  }, [difficulty, feedback, lives, paused, question, stats])
  const onCoin = useCallback(() => setStats((value) => ({ ...value, coins: value.coins + 1, score: value.score + 10 })), [])
  const onFile = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      try {
        const parsed = JSON.parse(String(reader.result)) as typeof samplePacks[number]
        if (!parsed.id || !parsed.title || !Array.isArray(parsed.questions) || parsed.questions.length === 0) throw new Error('Pack needs an id, title and at least one question.')
        if (parsed.questions.some((item) => !item.id || !item.question || !Array.isArray(item.options) || item.options.length < 3 || !Number.isInteger(item.correctIndex) || item.correctIndex < 0 || item.correctIndex >= item.options.length)) throw new Error('Every question needs an id, text, three options and a valid correctIndex.')
        setCustomPack(parsed)
        setPackId(parsed.id)
      } catch (error) {
        window.alert(error instanceof Error ? error.message : 'This question pack could not be read.')
      }
    }
    reader.readAsText(file)
  }

  if (screen === 'game') {
    return <main className="game-shell">
      <RunnerScene lane={lane} jumping={jumping} sliding={sliding} color={character.color} onCoin={onCoin} />
      <header className="game-header">
        <div className="brand compact"><span className="brand-mark"><Zap size={16} /></span> BOOTCAMP RUNNER</div>
        <div className="hud-stats"><span><Trophy size={16} /> {stats.score.toLocaleString()}</span><span><Coins size={16} /> {stats.coins}</span><span><Heart size={16} /> {lives}</span></div>
        <button className="icon-button" onClick={() => setPaused(true)} aria-label="Pause"><Pause size={19} /></button>
      </header>
      <section className="question-card">
        <div className="eyebrow"><span>QUESTION {questionIndex + 1}</span><span>{question.topic.toUpperCase()} / {question.difficulty.toUpperCase()}</span></div>
        <h1>{question.question}</h1>
        <div className="answer-row">{question.options.map((option, index) => <button key={option} className={`answer-option ${lane === index ? 'selected' : ''}`} onClick={() => answer(index)}><b>{String.fromCharCode(65 + index)}</b><span>{option}</span><ChevronDown size={15} /></button>)}</div>
        <p className="hint">Change lanes to line up with a gate, or use the answer cards above.</p>
      </section>
      <div className="touch-controls"><button onClick={() => setLane((value) => laneAfterMove(value, -1))} aria-label="Move left"><ArrowLeft /></button><button onClick={() => { setJumping(true); window.setTimeout(() => setJumping(false), 600) }} aria-label="Jump"><ChevronDown className="jump-icon" /></button><button onClick={() => setLane((value) => laneAfterMove(value, 1))} aria-label="Move right"><ArrowRight /></button></div>
      {feedback && <div className={`feedback ${feedback}`}><strong>{feedback === 'correct' ? 'NICE LINE!' : 'KEEP LEARNING'}</strong><span>{feedback === 'correct' ? '+ points and +5 coins' : `The answer was ${question.options[question.correctIndex]}`}</span><small>{question.explanation}</small></div>}
      {paused && <div className="modal-backdrop"><div className="pause-card"><span className="eyebrow">RUN PAUSED</span><h2>Ready for another lap?</h2><p>Your progress is safe. Take a breath, then get back in the flow.</p><button className="primary-button" onClick={() => setPaused(false)}><Play size={18} /> Resume run</button><button className="text-button" onClick={() => setScreen('menu')}>Quit to menu</button></div></div>}
    </main>
  }
  if (screen === 'results') {
    return <main className="app-shell results-screen"><div className="results-card"><span className="brand-mark large"><Award /></span><span className="eyebrow">SESSION COMPLETE</span><h1>Knowledge in motion.</h1><p className="muted">You kept moving through {pack.title}.</p><div className="result-grid"><div><strong>{stats.score.toLocaleString()}</strong><span>Final score</span></div><div><strong>{stats.correct}/{stats.answered}</strong><span>Accuracy</span></div><div><strong>{stats.coins}</strong><span>Coins collected</span></div></div><p className="muted">Keep practicing {dashboard?.weakest_topics?.slice(0, 2).join(' and ') || 'your weakest topics'} in your next run.</p><div className="result-actions"><button className="primary-button" onClick={startGame}><RotateCcw size={18} /> Run it back</button><button className="text-button" onClick={() => { void loadDashboard(); setScreen('dashboard') }}><BarChart3 size={16} /> View learning report</button><button className="text-button" onClick={() => setScreen('menu')}>Return to menu</button></div></div></main>
  }
  if (screen === 'dashboard') {
    const report = dashboard
    return <main className="app-shell dashboard-screen"><header className="topbar"><div className="brand"><span className="brand-mark"><BarChart3 size={18} /></span><span>LEARNING<br /><strong>DASHBOARD</strong></span></div><button className="text-button" onClick={() => setScreen('menu')}>Back to menu</button></header><section className="dashboard-hero"><div><span className="eyebrow">ADAPTIVE LEARNING REPORT</span><h1>Your momentum map.</h1><p className="muted">Performance-backed guidance from your saved quiz attempts.</p></div><button className="icon-button" onClick={() => void loadDashboard()} aria-label="Refresh learning dashboard"><BarChart3 size={18} /></button></section>{dashboardError && <p className="offline-note">{dashboardError}</p>}{report ? <><div className="dashboard-grid"><div><strong>{report.total_questions}</strong><span>Questions answered</span></div><div><strong>{Math.round(report.accuracy * 100)}%</strong><span>Overall accuracy</span></div><div><strong>{report.strongest_topics[0] || 'Building'}</strong><span>Strongest topic</span></div><div><strong>{report.weakest_topics[0] || 'Discovering'}</strong><span>Practice next</span></div></div><section className="dashboard-panel"><span className="eyebrow">TOPIC PROGRESS</span>{report.progress.length ? report.progress.map((topic) => <div className="topic-row" key={topic.topic}><span>{topic.topic}</span><div className="progress-track"><span style={{ width: `${Math.round(topic.accuracy * 100)}%` }} /></div><strong>{Math.round(topic.accuracy * 100)}%</strong></div>) : <p className="muted">Answer a few questions to unlock topic progress.</p>}</section>{report.latest_recommendation && <section className="recommendation-card"><span className="eyebrow">AI COACH · {report.latest_recommendation.recommended_difficulty.toUpperCase()}</span><p>{report.latest_recommendation.recommendation_text}</p><small>Focus: {report.latest_recommendation.weak_topics.join(', ') || 'keep your current route'}</small></section>}</> : <section className="dashboard-panel"><p className="muted">No database-backed report is available yet. Start a local run, then connect the learning service to sync your history.</p></section>}<button className="primary-button hero-button" onClick={() => setScreen('menu')}>Continue learning <ArrowRight size={18} /></button></main>
  }
  return <main className="app-shell"><div className="noise" /><header className="topbar"><div className="brand"><span className="brand-mark"><Zap size={18} /></span><span>BOOTCAMP<br /><strong>RUNNER AI</strong></span></div><div className="menu-actions"><span className="status-pill"><span className="pulse" /> LOCAL + AI READY</span><button className="text-button" onClick={() => { void loadDashboard(); setScreen('dashboard') }}><BarChart3 size={15} /> Learning dashboard</button></div></header><section className="hero"><div className="hero-copy"><div className="eyebrow"><Sparkles size={14} /> LEARN BY DOING</div><h1>Turn your<br /><em>knowledge</em> into momentum.</h1><p>Run the track. Make the call. Build your streak. AI adapts your next lap around the topics that need more practice.</p><button className="primary-button hero-button" onClick={startGame}>Start a run <ArrowRight size={18} /></button></div><div className="hero-visual"><div className="orbit-ring ring-one" /><div className="orbit-ring ring-two" /><div className="hero-avatar" style={{ background: `linear-gradient(145deg, ${character.color}, ${character.accent})` }}><div className="avatar-visor" /></div><div className="float-stat stat-one"><Trophy size={17} /><strong>+125</strong><span>STREAK BONUS</span></div><div className="float-stat stat-two"><Gauge size={17} /><strong>03</strong><span>LANES AHEAD</span></div></div></section><section className="setup-panel"><div className="setup-title"><CircleHelp size={18} /><div><strong>Set your route</strong><span>Customize your session before you launch.</span></div></div><div className="setup-fields"><label>Runner<select value={character.id} onChange={(event) => setCharacter(characters.find((item) => item.id === event.target.value) ?? characters[0])}>{characters.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.role}</option>)}</select></label><label>Question pack<select value={packId} onChange={(event) => setPackId(event.target.value)}>{samplePacks.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}{customPack && <option value={customPack.id}>{customPack.title} · imported</option>}</select></label><label>Mode<select value={mode} onChange={(event) => setMode(event.target.value as Mode)}>{Object.keys(modeSettings).map((item) => <option key={item}>{item}</option>)}</select></label><label>Difficulty<select value={difficulty} onChange={(event) => setDifficulty(event.target.value as Difficulty)}>{Object.keys(difficultySettings).map((item) => <option key={item}>{item}</option>)}</select></label></div><div className="setup-footer"><span>{modeSettings[mode].label} · {difficultySettings[difficulty].label}</span><label className="import-button">Import JSON pack<input type="file" accept=".json,application/json" onChange={onFile} /></label></div></section><footer className="footer-note">A small original learning game · Keyboard: A/D or arrows to move, W/Space to jump, S to slide, P to pause</footer></main>
}

export default App
