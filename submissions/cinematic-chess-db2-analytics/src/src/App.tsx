import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Chess, type Color, type PieceSymbol, type Square } from 'chess.js'
import DotGrid from './DotGrid'
import Db2Hub from './Db2Hub'
import { chooseAiMove } from './ai'
import { playMoveTone, setAmbientMuted, startAmbient, playCheckTone, playGameOverTone } from './audio'
import type { LastMove, Phase, PlayerColor, ScenePiece, TimeMode } from './types'
import { Analyzer, type AnalysisNode } from './analyzer'
import { getOpening, getOpeningName } from './openings'
import { saveGame, type SaveAnalysisInput, type SavedGameDetail } from './api'
import { getCanonicalOutcome, getHistoryFens } from './gameRecord'

const GameScene = lazy(() => import('./GameScene'))

const INITIAL_FEN = new Chess().fen()
const SHOWCASE_ENTER_PROGRESS = 0.18
const SHOWCASE_EXIT_PROGRESS = 0.08

function piecesFrom(game: Chess, previousPieces: ScenePiece[] = []): ScenePiece[] {
  const newPieces: ScenePiece[] = []
  const boardPieces: { square: Square, type: PieceSymbol, color: Color }[] = []
  
  game.board().forEach((row, rowIndex) => {
    row.forEach((p, colIndex) => {
      if (p) boardPieces.push({ square: `${'abcdefgh'[colIndex]}${8 - rowIndex}` as Square, type: p.type, color: p.color })
    })
  })

  const unmatchedBoardPieces = []
  const unmatchedPreviousPieces = previousPieces.filter(p => !p.captured)
  
  // 1. Exact matches (same square, type, color)
  for (const bp of boardPieces) {
    const prevIndex = unmatchedPreviousPieces.findIndex(p => p.square === bp.square && p.type === bp.type && p.color === bp.color)
    if (prevIndex !== -1) {
      newPieces.push({ ...bp, id: unmatchedPreviousPieces[prevIndex].id })
      unmatchedPreviousPieces.splice(prevIndex, 1)
    } else {
      unmatchedBoardPieces.push(bp)
    }
  }

  // 2. Match moved pieces
  for (const bp of unmatchedBoardPieces) {
    const prevIndex = unmatchedPreviousPieces.findIndex(p => p.type === bp.type && p.color === bp.color)
    if (prevIndex !== -1) {
      newPieces.push({ ...bp, id: unmatchedPreviousPieces[prevIndex].id })
      unmatchedPreviousPieces.splice(prevIndex, 1)
    } else {
      const pawnIndex = unmatchedPreviousPieces.findIndex(p => p.type === 'p' && p.color === bp.color)
      if (pawnIndex !== -1) {
         newPieces.push({ ...bp, id: unmatchedPreviousPieces[pawnIndex].id })
         unmatchedPreviousPieces.splice(pawnIndex, 1)
      } else {
         newPieces.push({ ...bp, id: Math.random().toString(36).slice(2) })
      }
    }
  }
  
  // 3. Mark remaining as captured
  for (const p of unmatchedPreviousPieces) {
    newPieces.push({ ...p, captured: true })
  }
  
  return newPieces
}

function resultText(game: Chess) {
  if (game.isCheckmate()) return `${game.turn() === 'w' ? 'Black' : 'White'} wins by checkmate`
  if (game.isStalemate()) return 'Draw by stalemate'
  if (game.isThreefoldRepetition()) return 'Draw by repetition'
  if (game.isInsufficientMaterial()) return 'Draw by insufficient material'
  if (game.isDraw()) return 'Draw'
  return ''
}

function getCapturedPieces(game: Chess) {
  const initial = { p: 8, n: 2, b: 2, r: 2, q: 1 }
  const counts = { w: { p: 0, n: 0, b: 0, r: 0, q: 0 }, b: { p: 0, n: 0, b: 0, r: 0, q: 0 } }
  
  game.board().forEach(row => {
    row.forEach(piece => {
      if (piece && piece.type !== 'k') {
        counts[piece.color][piece.type]++
      }
    })
  })

  const capturedByWhite: PieceSymbol[] = []
  const capturedByBlack: PieceSymbol[] = []
  
  for (const [type, initialCount] of Object.entries(initial)) {
    const key = type as keyof typeof initial
    const missingBlack = initialCount - counts.b[key]
    for (let i = 0; i < missingBlack; i++) capturedByWhite.push(key)
    
    const missingWhite = initialCount - counts.w[key]
    for (let i = 0; i < missingWhite; i++) capturedByBlack.push(key)
  }
  
  return { w: capturedByWhite, b: capturedByBlack }
}

function Icon({ name }: { name: 'sound' | 'mute' | 'pause' | 'play' | 'reset' | 'fullscreen' | 'download' | 'copy' | 'upload' | 'history' | 'home' | 'database' | 'save' }) {
  const icons = {
    sound: <><path d="M4 10h3l4-4v12l-4-4H4z" /><path d="M15 9c1.8 1.7 1.8 4.3 0 6M18 6c3.6 3.3 3.6 8.7 0 12" /></>,
    mute: <><path d="M4 10h3l4-4v12l-4-4H4z" /><path d="m16 10 5 5m0-5-5 5" /></>,
    pause: <><path d="M8 6v12M16 6v12" /></>,
    play: <path d="m9 6 10 6-10 6z" />,
    reset: <><path d="M5 8v5h5" /><path d="M6 13a7 7 0 1 0 2-6" /></>,
    fullscreen: <><path d="M9 4H4v5M15 4h5v5M9 20H4v-5M15 20h5v-5" /></>,
    download: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></>,
    copy: <><rect x="9" y="9" width="13" height="13" rx="2" ry="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></>,
    upload: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></>,
    history: <><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></>,
    home: <><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /><polyline points="9 22 9 12 15 12 15 22" /></>,
    database: <><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5" /><path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" /></>,
    save: <><path d="M5 3h12l2 2v16H5z" /><path d="M8 3v6h8V3M8 21v-7h8v7" /></>,
  }
  return <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">{icons[name]}</svg>
}

export default function App() {
  const gameRef = useRef(new Chess())
  const aiRequest = useRef(0)
  const phaseRef = useRef<Phase>('landing')
  const transitionTimers = useRef<number[]>([])
  const launchLock = useRef(false)
  const reducedMotion = useRef(false)
  const clientGameIdRef = useRef<string>(crypto.randomUUID())
  const playedAtRef = useRef(new Date().toISOString())
  const gameSourceRef = useRef<'played' | 'imported'>('played')
  const [phase, setPhase] = useState<Phase>('landing')
  const [fen, setFen] = useState(INITIAL_FEN)
  const [selected, setSelected] = useState<Square | null>(null)
  const [legal, setLegal] = useState<Square[]>([])
  const [lastMove, setLastMove] = useState<LastMove | null>(null)
  const [playerChoice, setPlayerChoice] = useState<PlayerColor>('w')
  const [playerColor, setPlayerColor] = useState<Color>('w')
  const [elo, setElo] = useState(() => Number(localStorage.getItem('chess-elo')) || 1400)
  const [thinking, setThinking] = useState(false)
  const [muted, setMuted] = useState(() => localStorage.getItem('chess-muted') === 'true')
  const [scrollProgress, setScrollProgress] = useState(0)
  const [transitionLabel, setTransitionLabel] = useState('INITIALIZING ARENA')
  const [promotion, setPromotion] = useState<{ from: Square; to: Square } | null>(null)
  const [timeMode, setTimeMode] = useState<TimeMode>('unlimited')
  const [analysisData, setAnalysisData] = useState<AnalysisNode[]>([])
  const [analysisIndex, setAnalysisIndex] = useState(0)
  const [reviewIndex, setReviewIndex] = useState(0)
  const [showHistory, setShowHistory] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [analysisError, setAnalysisError] = useState<string | null>(null)
  const [showHomeConfirm, setShowHomeConfirm] = useState(false)
  const [showDb2Hub, setShowDb2Hub] = useState(false)
  const [db2RefreshSignal, setDb2RefreshSignal] = useState(0)
  const [saveState, setSaveState] = useState<'idle' | 'analyzing' | 'saving' | 'saved' | 'error'>('idle')
  const [saveMessage, setSaveMessage] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const activeMoveRef = useRef<HTMLButtonElement>(null)
  const analyzerRef = useRef<Analyzer | null>(null)
  const playerTimeRef = useRef<number>(0)
  const aiTimeRef = useRef<number>(0)
  const lastTickRef = useRef<number>(0)
  const playerClockNode = useRef<HTMLDivElement>(null)
  const aiClockNode = useRef<HTMLDivElement>(null)

  const previousPiecesRef = useRef<ScenePiece[]>([])
  const pieces = useMemo(() => {
    let newPieces: ScenePiece[] = []
    if (phase === 'analysis' && analysisData[analysisIndex]) {
      newPieces = piecesFrom(new Chess(analysisData[analysisIndex].fen), previousPiecesRef.current)
    } else if (phase === 'review') {
      const positions = getHistoryFens(gameRef.current)
      const replayGame = new Chess(positions[Math.min(reviewIndex, positions.length - 1)])
      newPieces = piecesFrom(replayGame, previousPiecesRef.current)
    } else {
      newPieces = piecesFrom(gameRef.current, previousPiecesRef.current)
    }
    previousPiecesRef.current = newPieces
    return newPieces
  }, [fen, phase, analysisData, analysisIndex, reviewIndex])
  const isGame = ['playing', 'paused', 'gameOver', 'analysis', 'review'].includes(phase)
  const game = gameRef.current

  useEffect(() => {
    phaseRef.current = phase
  }, [phase])

  useEffect(() => {
    return () => analyzerRef.current?.terminate()
  }, [])

  useEffect(() => {
    if (activeMoveRef.current) {
      activeMoveRef.current.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    }
  }, [reviewIndex, showHistory, phase])

  const pauseMatch = useCallback(() => {
    aiRequest.current++
    setThinking(false)
    setPhase('paused')
  }, [])

  const beginGameRecord = useCallback((source: 'played' | 'imported') => {
    clientGameIdRef.current = crypto.randomUUID()
    playedAtRef.current = new Date().toISOString()
    gameSourceRef.current = source
    setAnalysisData([])
    setAnalysisIndex(0)
    setAnalysisError(null)
    setSaveState('idle')
    setSaveMessage(null)
  }, [])

  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    const syncReducedMotion = () => {
      reducedMotion.current = media.matches
    }
    syncReducedMotion()
    media.addEventListener('change', syncReducedMotion)
    return () => media.removeEventListener('change', syncReducedMotion)
  }, [])

  useEffect(() => {
    const onScroll = () => {
      const max = Math.max(1, document.documentElement.scrollHeight - innerHeight)
      const progress = Math.min(1, Math.max(0, scrollY / max))
      setScrollProgress(progress)
      if (launchLock.current) return
      setPhase((current) => {
        if (current === 'landing' && progress > SHOWCASE_ENTER_PROGRESS) return 'showcase'
        if (current === 'showcase' && progress <= SHOWCASE_EXIT_PROGRESS) return 'landing'
        return current
      })
    }
    addEventListener('scroll', onScroll, { passive: true })
    onScroll()
    return () => removeEventListener('scroll', onScroll)
  }, [])

  const clearTransitionTimers = useCallback(() => {
    transitionTimers.current.forEach((timer) => window.clearTimeout(timer))
    transitionTimers.current = []
  }, [])

  useEffect(() => {
    if (phase !== 'playing' || timeMode === 'unlimited') return
    
    let raf: number
    lastTickRef.current = performance.now()
    
    const tick = () => {
      const now = performance.now()
      const delta = now - lastTickRef.current
      lastTickRef.current = now
      
      const isPlayerTurn = gameRef.current.turn() === playerColor
      
      if (isPlayerTurn) {
        playerTimeRef.current = Math.max(0, playerTimeRef.current - delta)
        if (playerTimeRef.current === 0) {
          setPhase('gameOver')
          return
        }
      } else {
        aiTimeRef.current = Math.max(0, aiTimeRef.current - delta)
        if (aiTimeRef.current === 0) {
          setPhase('gameOver')
          return
        }
      }
      
      const formatTime = (ms: number) => {
        const total = Math.ceil(ms / 1000)
        const m = Math.floor(total / 60)
        const s = total % 60
        return `${m}:${s.toString().padStart(2, '0')}`
      }
      
      if (playerClockNode.current) {
        playerClockNode.current.textContent = formatTime(playerTimeRef.current)
        playerClockNode.current.className = `chess-clock ${isPlayerTurn ? 'clock-active' : ''} ${playerTimeRef.current < 10000 ? 'clock-danger' : playerTimeRef.current < 30000 ? 'clock-warning' : ''}`
      }
      if (aiClockNode.current) {
        aiClockNode.current.textContent = formatTime(aiTimeRef.current)
        aiClockNode.current.className = `chess-clock ${!isPlayerTurn ? 'clock-active' : ''} ${aiTimeRef.current < 10000 ? 'clock-danger' : aiTimeRef.current < 30000 ? 'clock-warning' : ''}`
      }
      
      raf = requestAnimationFrame(tick)
    }
    
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [phase, playerColor, timeMode])

  const makeAiMove = useCallback(async () => {
    const request = ++aiRequest.current
    setThinking(true)
    try {
      const move = await chooseAiMove(gameRef.current.fen(), elo)
      if (request !== aiRequest.current || !move || gameRef.current.isGameOver() || phaseRef.current !== 'playing') {
        return
      }
      const played = gameRef.current.move({ from: move.from, to: move.to, promotion: move.promotion || 'q' })
      setLastMove({ from: played.from, to: played.to })
      setFen(gameRef.current.fen())
      playMoveTone(Boolean(played.captured))
      
      if (gameRef.current.isGameOver()) {
        const isWin = gameRef.current.isCheckmate() && gameRef.current.turn() !== playerColor
        playGameOverTone(isWin)
      } else if (gameRef.current.inCheck()) {
        playCheckTone()
      }
    } catch (err) {
      console.error('AI Move Error:', err)
    } finally {
      if (request === aiRequest.current) {
        setThinking(false)
        if (gameRef.current.isGameOver()) setPhase('gameOver')
      }
    }
  }, [elo, playerColor])

  useEffect(() => {
    if (phase === 'playing' && game.turn() !== playerColor && !game.isGameOver() && !thinking) {
      void makeAiMove()
    }
  }, [fen, phase, playerColor, thinking, game, makeAiMove])

  const completeMove = useCallback((from: Square, to: Square, promotionPiece: PieceSymbol = 'q') => {
    try {
      const played = gameRef.current.move({ from, to, promotion: promotionPiece })
      setSelected(null)
      setLegal([])
      setPromotion(null)
      setLastMove({ from: played.from, to: played.to })
      setFen(gameRef.current.fen())
      playMoveTone(Boolean(played.captured))
      
      if (gameRef.current.isGameOver()) {
        const isWin = gameRef.current.isCheckmate() && gameRef.current.turn() !== playerColor
        playGameOverTone(isWin)
        setPhase('gameOver')
      } else if (gameRef.current.inCheck()) {
        playCheckTone()
      }
    } catch {
      setSelected(null)
      setLegal([])
    }
  }, [])

  const onSquare = useCallback((square: Square) => {
    if (phase !== 'playing' || thinking || gameRef.current.turn() !== playerColor) return
    const piece = gameRef.current.get(square)
    if (!selected) {
      if (!piece || piece.color !== playerColor) return
      setSelected(square)
      setLegal(gameRef.current.moves({ square, verbose: true }).map((move) => move.to))
      return
    }
    if (piece?.color === playerColor) {
      setSelected(square)
      setLegal(gameRef.current.moves({ square, verbose: true }).map((move) => move.to))
      return
    }
    const candidate = gameRef.current.moves({ square: selected, verbose: true }).find((move) => move.to === square)
    if (!candidate) {
      setSelected(null)
      setLegal([])
      return
    }
    if (candidate.flags.includes('p')) setPromotion({ from: selected, to: square })
    else completeMove(selected, square)
  }, [phase, thinking, playerColor, selected, completeMove])

  const enterExperience = async () => {
    clearTransitionTimers()
    launchLock.current = true
    void startAmbient()
    setAmbientMuted(muted)
    setTransitionLabel('INITIALIZING ARENA')
    setPhase('transition')
    window.scrollTo({ top: document.body.scrollHeight, behavior: reducedMotion.current ? 'auto' : 'smooth' })
    if (reducedMotion.current) {
      setTransitionLabel('YOUR MOVE')
      setPhase('setup')
      return
    }
    transitionTimers.current = [
      window.setTimeout(() => setTransitionLabel('CALIBRATING OPPONENT'), 850),
      window.setTimeout(() => setTransitionLabel('YOUR MOVE'), 1550),
      window.setTimeout(() => setPhase('setup'), 2050),
    ]
  }

  const startMatch = () => {
    clearTransitionTimers()
    launchLock.current = false
    aiRequest.current++
    gameRef.current = new Chess()
    beginGameRecord('played')
    const actual = playerChoice === 'random' ? (Math.random() > 0.5 ? 'w' : 'b') : playerChoice
    setPlayerColor(actual)
    setFen(gameRef.current.fen())
    setLastMove(null)
    setSelected(null)
    setLegal([])
    setThinking(false)
    localStorage.setItem('chess-elo', String(elo))
    
    if (timeMode !== 'unlimited') {
      const ms = timeMode * 60 * 1000
      playerTimeRef.current = ms
      aiTimeRef.current = ms
    }
    
    setPhase('playing')
  }

  const resetMatch = () => {
    clearTransitionTimers()
    launchLock.current = false
    aiRequest.current++
    gameRef.current = new Chess()
    beginGameRecord('played')
    setFen(gameRef.current.fen())
    setLastMove(null)
    setSelected(null)
    setLegal([])
    setThinking(false)
    setPhase('setup')
  }

  const goHome = () => {
    if (gameRef.current.history().length > 0 && phase !== 'gameOver') {
      setShowHomeConfirm(true)
    } else {
      gameRef.current = new Chess()
      setFen(gameRef.current.fen())
      setLastMove(null)
      setSelected(null)
      setLegal([])
      setPhase('landing')
    }
  }

  const confirmLeaveGame = () => {
    gameRef.current = new Chess()
    beginGameRecord('played')
    setFen(gameRef.current.fen())
    setLastMove(null)
    setSelected(null)
    setLegal([])
    setShowHomeConfirm(false)
    setPhase('landing')
  }

  const analyzeGamePositions = async (sourceGame: Chess, showPanel: boolean) => {
    if (showPanel) {
      setPhase('analysis')
      setAnalysisIndex(0)
    }
    setAnalyzing(true)
    setAnalysisError(null)
    setAnalysisData([])
    const historyFens = getHistoryFens(sourceGame)

    if (!analyzerRef.current) {
      analyzerRef.current = new Analyzer()
    }

    try {
      const results = await analyzerRef.current.analyzeGame(historyFens, (index, total, node) => {
        setAnalysisData(prev => {
          const next = [...prev]
          next[index] = node
          return next
        })
      })
      setAnalysisData(results)
      return results
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Stockfish analysis failed'
      setAnalysisError(message)
      throw error
    } finally {
      setAnalyzing(false)
    }
  }

  const startAnalysis = async () => {
    try {
      await analyzeGamePositions(gameRef.current, true)
    } catch {
      // The analysis panel renders the actionable error state.
    }
  }

  const stepAnalysis = (offset: number) => {
    const next = Math.max(0, Math.min(analysisData.length - 1, analysisIndex + offset))
    setAnalysisIndex(next)
    setFen(analysisData[next].fen)
  }
  
  const jumpAnalysis = (index: number) => {
    const next = Math.max(0, Math.min(analysisData.length - 1, index))
    setAnalysisIndex(next)
    setFen(analysisData[next].fen)
  }

  const enterReview = (index: number) => {
    setReviewIndex(index)
    setPhase('review')
  }

  const exitReview = () => {
    if (gameRef.current.isGameOver()) {
      setPhase('gameOver')
    } else {
      setPhase('playing')
    }
    setFen(gameRef.current.fen())
  }

  const stepReview = (offset: number) => {
    const historyLength = gameRef.current.history().length
    const next = Math.max(0, Math.min(historyLength, reviewIndex + offset))
    setReviewIndex(next)
  }

  const jumpReview = (index: number) => {
    const historyLength = gameRef.current.history().length
    const next = Math.max(0, Math.min(historyLength, index))
    setReviewIndex(next)
  }

  const copyPGN = async () => {
    try {
      await navigator.clipboard.writeText(gameRef.current.pgn())
      alert('PGN copied to clipboard')
    } catch {
      alert('Failed to copy PGN')
    }
  }

  const downloadPGN = () => {
    const pgn = gameRef.current.pgn()
    const blob = new Blob([pgn], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `game-${new Date().toISOString().slice(0,16).replace(/[:T]/g, '-')}.pgn`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const importPGN = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (e) => {
      try {
        const content = e.target?.result as string
        const newGame = new Chess()
        newGame.loadPgn(content)
        gameRef.current = newGame
        beginGameRecord('imported')
        setFen(newGame.fen())
        setLastMove(null)
        setSelected(null)
        setLegal([])
        setThinking(false)
        setPhase('review')
        setShowHistory(true)
        setReviewIndex(newGame.history().length)
      } catch (err) {
        alert('Invalid PGN file')
      }
    }
    reader.readAsText(file)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const saveCurrentGame = async () => {
    const sourceGame = gameRef.current
    if (sourceGame.history().length === 0 || analyzing || saveState === 'analyzing' || saveState === 'saving') return

    try {
      const historyFens = getHistoryFens(sourceGame)
      let analysis = analysisData
      const analysisMatchesGame = analysis.length === historyFens.length && analysis.every((node, index) => node?.fen === historyFens[index])
      if (!analysisMatchesGame) {
        setSaveState('analyzing')
        setSaveMessage('Stockfish is evaluating the game before it is saved.')
        analysis = await analyzeGamePositions(sourceGame, false)
      }

      setSaveState('saving')
      setSaveMessage('Writing the game and analytics to IBM Db2.')
      const opening = getOpening(sourceGame.history())
      const outcome = getCanonicalOutcome(
        sourceGame,
        playerColor,
        timeMode !== 'unlimited' && playerTimeRef.current === 0,
        timeMode !== 'unlimited' && aiTimeRef.current === 0,
      )
      const analysisPayload: SaveAnalysisInput[] = analysis.map((node, plyNumber) => ({
        ply_number: plyNumber,
        fen: node.fen,
        cp: node.status === 'evaluated' ? node.cp : null,
        mate: node.status === 'evaluated' ? node.mate : null,
        win_probability: node.status === 'evaluated' ? node.winProbability : null,
        classification: node.status === 'evaluated' ? node.classification : null,
        status: node.status === 'engine-error' ? 'error' : node.status,
        depth: node.depth,
        engine: node.engine,
      }))

      const response = await saveGame({
        client_game_id: clientGameIdRef.current,
        source: gameSourceRef.current,
        pgn: sourceGame.pgn(),
        result: outcome.result,
        termination: outcome.termination,
        player_color: gameSourceRef.current === 'imported' ? null : playerColor === 'w' ? 'white' : 'black',
        opponent_elo: gameSourceRef.current === 'played' ? elo : null,
        time_control: timeMode === 'unlimited' ? 'unlimited' : `${timeMode}+0`,
        opening_eco: opening.eco === 'START' ? null : opening.eco,
        opening_name: opening.name,
        played_at: playedAtRef.current,
        analysis: analysisPayload,
      })

      setSaveState('saved')
      setSaveMessage(response.created ? 'Game saved to IBM Db2.' : 'This game was already saved in IBM Db2.')
      setDb2RefreshSignal((value) => value + 1)
    } catch (error) {
      setSaveState('error')
      setSaveMessage(error instanceof Error ? error.message : 'The game could not be saved.')
    }
  }

  const loadSavedGame = (saved: SavedGameDetail) => {
    const loaded = new Chess()
    loaded.loadPgn(saved.pgn)
    aiRequest.current++
    gameRef.current = loaded
    clientGameIdRef.current = saved.game_id
    playedAtRef.current = saved.played_at
    gameSourceRef.current = saved.source
    if (saved.player_color) setPlayerColor(saved.player_color === 'white' ? 'w' : 'b')
    if (saved.opponent_elo) setElo(saved.opponent_elo)
    if (saved.time_control === 'unlimited') setTimeMode('unlimited')
    else {
      const minutes = Number.parseInt(saved.time_control, 10)
      if ([1, 3, 5, 10, 15].includes(minutes)) setTimeMode(minutes as TimeMode)
    }
    const savedAnalysis: AnalysisNode[] = saved.analysis.map((node) => ({
      fen: node.fen,
      cp: node.cp ?? 0,
      mate: node.mate,
      winProbability: node.win_probability ?? 50,
      classification: node.classification as AnalysisNode['classification'],
      status: node.status === 'error' ? 'engine-error' : node.status,
      depth: node.depth,
      engine: node.engine,
    }))
    setAnalysisData(savedAnalysis)
    setAnalysisIndex(Math.max(0, savedAnalysis.length - 1))
    setAnalysisError(null)
    setFen(loaded.fen())
    setLastMove(null)
    setSelected(null)
    setLegal([])
    setThinking(false)
    setShowHistory(true)
    setReviewIndex(loaded.history().length)
    setSaveState('saved')
    setSaveMessage('Loaded from IBM Db2.')
    setPhase('review')
    setShowDb2Hub(false)
    return loaded
  }

  const analyzeSavedGame = async (saved: SavedGameDetail) => {
    const loaded = loadSavedGame(saved)
    try {
      await analyzeGamePositions(loaded, true)
    } catch {
      // The analysis panel renders the actionable error state.
    }
  }

  const openDb2Hub = () => {
    if (phase === 'playing') pauseMatch()
    setShowDb2Hub(true)
  }

  const saveFromHud = () => {
    if (phase === 'playing') pauseMatch()
    void saveCurrentGame()
  }

  const toggleSound = () => {
    const next = !muted
    setMuted(next)
    setAmbientMuted(next)
    localStorage.setItem('chess-muted', String(next))
  }

  const toggleFullscreen = () => {
    if (document.fullscreenElement) void document.exitFullscreen().catch(() => undefined)
    else void document.documentElement.requestFullscreen().catch(() => undefined)
  }

  useEffect(() => clearTransitionTimers, [clearTransitionTimers])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (showDb2Hub) return
      if (event.key.toLowerCase() === 'f') toggleFullscreen()
      if (event.key === 'Escape' && phase === 'paused') setPhase('playing')
      if (event.key === ' ' && isGame) {
        event.preventDefault()
        setPhase((current) => {
          if (current === 'paused') return 'playing'
          if (current === 'playing') {
            aiRequest.current++
            setThinking(false)
            return 'paused'
          }
          return current
        })
      }
    }
    addEventListener('keydown', onKey)
    return () => removeEventListener('keydown', onKey)
  }, [phase, isGame, showDb2Hub])

  useEffect(() => {
    const state = {
      coordinateSystem: 'Standard algebraic chess coordinates: a1 is White’s left corner.',
      phase,
      turn: gameRef.current.turn() === 'w' ? 'white' : 'black',
      playerColor: playerColor === 'w' ? 'white' : 'black',
      fen: gameRef.current.fen(),
      selected,
      legalMoves: legal,
      lastMove,
      engineThinking: thinking,
      elo,
      result: resultText(gameRef.current) || null,
      db2HubOpen: showDb2Hub,
      saveState,
    }

    document.documentElement.dataset.phase = phase
    document.documentElement.dataset.turn = state.turn
    document.documentElement.dataset.playerColor = state.playerColor
    document.documentElement.dataset.thinking = String(thinking)
    document.documentElement.dataset.fen = state.fen
    document.documentElement.dataset.selected = selected ?? ''
    document.documentElement.dataset.legalMoves = legal.join(',')
    document.documentElement.dataset.gameState = JSON.stringify(state)
    const testWindow = window as typeof window & { render_game_to_text?: () => string }
    const renderGameState = () => document.documentElement.dataset.gameState ?? '{}'
    testWindow.render_game_to_text = renderGameState
    return () => {
      if (testWindow.render_game_to_text === renderGameState) delete testWindow.render_game_to_text
    }
  }, [phase, playerColor, selected, legal, lastMove, thinking, elo, fen, showDb2Hub, saveState])

  useEffect(() => {
    if (!import.meta.env.DEV) return

    const playDebugMove = ({ from, to, promotion: requestedPromotion }: { from?: Square; to?: Square; promotion?: PieceSymbol }) => {
      if (!from || !to || phase !== 'playing' || thinking || gameRef.current.turn() !== playerColor) return
      const candidate = gameRef.current.moves({ square: from, verbose: true }).find((move) => move.to === to)
      if (!candidate) return
      if (candidate.flags.includes('p')) completeMove(from, to, requestedPromotion ?? 'q')
      else completeMove(from, to)
    }

    const onMove = (event: Event) => {
      playDebugMove((event as CustomEvent<{ from?: Square; to?: Square; promotion?: PieceSymbol }>).detail ?? {})
    }

    const onReset = () => {
      resetMatch()
    }

    const pollDebugCommands = window.setInterval(() => {
      const payload = document.documentElement.dataset.codexMove
      if (!payload) return
      delete document.documentElement.dataset.codexMove
      try {
        playDebugMove(JSON.parse(payload) as { from?: Square; to?: Square; promotion?: PieceSymbol })
      } catch {
        // Ignore malformed dev commands so the gameplay loop stays untouched.
      }
    }, 120)

    document.addEventListener('codex:move', onMove as EventListener)
    document.addEventListener('codex:reset', onReset)
    return () => {
      document.removeEventListener('codex:move', onMove as EventListener)
      document.removeEventListener('codex:reset', onReset)
      window.clearInterval(pollDebugCommands)
    }
  }, [completeMove, phase, playerColor, resetMatch, thinking])

  const status = phase === 'gameOver'
    ? resultText(game) || (playerTimeRef.current === 0 ? 'MACHINE WINS ON TIME' : aiTimeRef.current === 0 ? 'PLAYER WINS ON TIME' : 'GAME OVER')
    : phase === 'review' || phase === 'analysis'
      ? 'REVIEW MODE'
      : thinking
        ? 'OPPONENT IS THINKING'
        : game.inCheck()
          ? `${game.turn() === 'w' ? 'WHITE' : 'BLACK'} IN CHECK`
          : `${game.turn() === 'w' ? 'WHITE' : 'BLACK'} TO MOVE`

  const captured = useMemo(() => {
    let targetGame = gameRef.current
    if (phase === 'review') {
      const positions = getHistoryFens(gameRef.current)
      targetGame = new Chess(positions[Math.min(reviewIndex, positions.length - 1)])
    } else if (phase === 'analysis' && analysisData[analysisIndex]) {
      targetGame = new Chess(analysisData[analysisIndex].fen)
    }
    return getCapturedPieces(targetGame)
  }, [fen, phase, reviewIndex, analysisIndex, analysisData])

  const renderCaptured = (pieces: PieceSymbol[]) => {
    const pieceChars: Record<PieceSymbol, string> = { p: '♙', n: '♘', b: '♗', r: '♖', q: '♕', k: '♔' }
    return <span className="captured-icons">{pieces.map((p, i) => <i key={i}>{pieceChars[p]}</i>)}</span>
  }

  const moves = game.history()
  const movePairs = []
  for (let i = 0; i < moves.length; i += 2) {
    movePairs.push([moves[i], moves[i + 1]])
  }

  return (
    <main className={`app-shell app-shell--${phase}`}>
      {(phase === 'landing' || phase === 'showcase') && <DotGrid scrollProgress={scrollProgress} />}
      <div className="scene-shell" aria-hidden="true">
        <Suspense fallback={<div className="scene-fallback"><div className="loader-ring"></div><span>RENDERING ARENA</span></div>}>
          <GameScene
            phase={phase}
            pieces={pieces}
            selected={selected}
            legal={legal}
            lastMove={lastMove}
            playerColor={playerColor}
            scrollProgress={scrollProgress}
            inCheck={game.inCheck()}
            isCheckmate={game.isCheckmate()}
            onSquare={onSquare}
          />
        </Suspense>
      </div>
      <div className={`main-wrapper ${isGame ? 'in-game' : ''}`}>

      <section className={`hero ${phase !== 'landing' ? 'hero--scrolled' : ''}`}>
        <nav className="topbar">
          <span className="micro-logo">C/64</span>
          <span className="nav-note">AN INTERACTIVE STUDY<br />OF THE INFINITE GAME</span>
          <div className="topbar-actions">
            <button type="button" className="db2-entry" onClick={openDb2Hub}>MY GAMES / DB2</button>
            <span className="edition">MMXXVI — 01</span>
          </div>
        </nav>
        <div className="hero-copy">
          <p className="eyebrow"><span /> STRATEGY, REIMAGINED</p>
          <h1>CHESS</h1>
          <blockquote className="hero-quote">
            <span className="quote-icon">♜</span> "My queen didn't blunder.<br className="desktop-break" /> She took an unscheduled vacation."
          </blockquote>
          <div className="hero-bottom">
            <button id="start-btn" type="button" className="play-button play-button--dark" onClick={enterExperience}>
              <span>PLAY NOW</span><i>↗</i>
            </button>
          </div>
        </div>
        <div className="scroll-cue"><span>SCROLL TO ENTER</span><i /></div>
      </section>

      <section className={`showcase ${['transition', 'setup', 'playing', 'paused', 'gameOver'].includes(phase) ? 'showcase--hidden' : ''}`} aria-label="Cinematic chess showcase">
        <div className="chapter chapter--one">
          <span className="chapter-index">01 / THE ARENA</span>
          <h2>BUILT FOR<br /><em>FORESIGHT.</em></h2>
          <p>Thirty-two forms. Sixty-four fields.<br />Every decision leaves a trace.</p>
        </div>
        <div className="chapter chapter--two">
          <span className="chapter-index">02 / THE OPPONENT</span>
          <h2>FACE THE<br /><em>MACHINE.</em></h2>
          <p>Choose your strength. Find the line.<br />Make the position yours.</p>
        </div>
        <button type="button" className="play-button play-button--light showcase-play" onClick={enterExperience}>
          <span>ENTER THE ARENA</span><i>↗</i>
        </button>
      </section>

      <footer className={`site-footer ${['transition', 'setup', 'playing', 'paused', 'gameOver'].includes(phase) ? 'site-footer--hidden' : ''}`}>
        <div className="footer-content">
          <h2 className="support-title">☕ Support the Project</h2>
          <p>If you're enjoying this cinematic 3D chess experience and would like to support future updates, AI improvements, new features, and open-source projects, I'd truly appreciate your support.</p>
          <a href="https://buymeacoffee.com/jaygadage" target="_blank" rel="noopener noreferrer" className="support-btn">
            <span>☕ Support the Project</span>
          </a>
          <p className="footer-note">Made with ❤️, React, Three.js, and lots of coffee.</p>
        </div>
      </footer>

      {phase === 'transition' && (
        <div className="transition-screen">
          <div className="transition-mark">C</div>
          <div className="transition-line"><i /></div>
          <p>{transitionLabel}</p>
        </div>
      )}

      {phase === 'setup' && (
        <div className="overlay setup-panel" role="dialog" aria-modal="true" aria-labelledby="setup-title">
          <div className="panel-kicker">MATCH CONFIGURATION / 01</div>
          <h2 id="setup-title">CHOOSE<br /><em>YOUR SIDE.</em></h2>
          <div className="choice-label"><span>COLOR</span><b>{playerChoice === 'w' ? 'WHITE' : playerChoice === 'b' ? 'BLACK' : 'RANDOM'}</b></div>
          <div className="color-options">
            {([['w', 'WHITE'], ['random', 'RANDOM'], ['b', 'BLACK']] as const).map(([value, label]) => (
              <button type="button" key={value} aria-pressed={playerChoice === value} className={playerChoice === value ? 'active' : ''} onClick={() => setPlayerChoice(value)}>{label}</button>
            ))}
          </div>
          <div className="elo-row">
            <div className="choice-label"><span>OPPONENT STRENGTH</span><b>{elo} ELO</b></div>
            <input aria-label="Opponent strength" type="range" min="600" max="2400" step="100" value={elo} onChange={(event) => setElo(Number(event.target.value))} />
            <div className="range-labels"><span>CASUAL</span><span>GRANDMASTER</span></div>
          </div>
          <div className="choice-label"><span>TIME CONTROL</span><b>{timeMode === 'unlimited' ? 'UNLIMITED' : `${timeMode} MIN`}</b></div>
          <div className="time-options">
            {(['unlimited', 1, 3, 5, 10, 15] as TimeMode[]).map((mode) => (
              <button type="button" key={mode} aria-pressed={timeMode === mode} className={timeMode === mode ? 'active' : ''} onClick={() => setTimeMode(mode)}>{mode === 'unlimited' ? '∞' : mode}</button>
            ))}
          </div>
          <button id="begin-match" type="button" className="begin-button" onClick={startMatch}><span>BEGIN MATCH</span><i>→</i></button>
          <p className="setup-hint">SELECT A PIECE TO REVEAL LEGAL MOVES</p>
        </div>
      )}

      {isGame && (
        <div className="game-ui">
          <header className="game-header">
            <span className="game-logo">CHESS<small>/64</small></span>
            <div className="game-meta"><span>VS. MACHINE</span><b>{elo} ELO</b></div>
            {timeMode !== 'unlimited' && (
              <div className="clock-container">
                <div className="player-clock">
                  <span>{playerColor === 'w' ? 'WHITE' : 'BLACK'}</span>
                  <div ref={playerClockNode} className="chess-clock" />
                </div>
                <div className="ai-clock">
                  <span>MACHINE</span>
                  <div ref={aiClockNode} className="chess-clock" />
                </div>
              </div>
            )}
          </header>
          <div className="captured-area">
            <div className="captured-white">{renderCaptured(captured.b)}</div>
            <div className="captured-black">{renderCaptured(captured.w)}</div>
          </div>
          <div className="status-pill" role="status" aria-live="polite"><i className={thinking ? 'thinking' : ''} /><span>{status}</span></div>
          <div className="hud-actions">
            <button type="button" aria-label="Home" onClick={goHome}><Icon name="home" /></button>
            <button type="button" aria-label="My Games and analytics" onClick={openDb2Hub}><Icon name="database" /></button>
            <button
              type="button"
              aria-label="Save game to IBM Db2"
              onClick={saveFromHud}
              disabled={game.history().length === 0 || analyzing || saveState === 'analyzing' || saveState === 'saving'}
            ><Icon name="save" /></button>
            <button type="button" aria-label="Review Mode" onClick={() => phase === 'review' ? exitReview() : enterReview(gameRef.current.history().length)}><Icon name="history" /></button>
            <button type="button" aria-label={muted ? 'Unmute' : 'Mute'} aria-pressed={muted} onClick={toggleSound}><Icon name={muted ? 'mute' : 'sound'} /></button>
            <button type="button" aria-label={phase === 'paused' ? 'Resume' : 'Pause'} aria-pressed={phase === 'paused'} onClick={() => (phase === 'paused' ? setPhase('playing') : pauseMatch())}><Icon name={phase === 'paused' ? 'play' : 'pause'} /></button>
            <button type="button" aria-label="Restart match" onClick={resetMatch}><Icon name="reset" /></button>
            <button type="button" aria-label="Fullscreen" onClick={toggleFullscreen}><Icon name="fullscreen" /></button>
          </div>
          <div className="coordinate-note">{playerColor === 'w' ? 'PLAYING WHITE' : 'PLAYING BLACK'} · F FOR FULLSCREEN</div>
        </div>
      )}

      {phase === 'paused' && !showHomeConfirm && (
        <div className="pause-card" role="dialog" aria-modal="true" aria-labelledby="pause-title">
          <span id="pause-title">MATCH PAUSED</span>
          <button type="button" onClick={() => setPhase('playing')}>RESUME</button>
        </div>
      )}

      {showHomeConfirm && (
        <div className="pause-card" role="dialog" aria-modal="true" aria-labelledby="home-title">
          <span id="home-title" style={{ fontSize: '12px', marginBottom: '20px' }}>Leave the current game?<br /><br />Your progress will be lost.</span>
          <div className="result-actions" style={{ display: 'flex', gap: '10px', justifyContent: 'center' }}>
            <button type="button" onClick={() => setShowHomeConfirm(false)}>Continue Playing</button>
            <button type="button" onClick={confirmLeaveGame}>Leave Game</button>
          </div>
        </div>
      )}

      {phase === 'gameOver' && (
        <div className="result-card" role="alertdialog" aria-modal="true" aria-labelledby="result-title">
          <span>FINAL POSITION</span>
          <h2 id="result-title">{resultText(game) || (playerTimeRef.current === 0 ? 'MACHINE WINS ON TIME' : aiTimeRef.current === 0 ? 'PLAYER WINS ON TIME' : 'GAME OVER')}</h2>
          <div className="result-actions">
            <button type="button" onClick={() => void saveCurrentGame()} disabled={analyzing || saveState === 'analyzing' || saveState === 'saving'}>
              {saveState === 'analyzing' ? 'ANALYZING…' : saveState === 'saving' ? 'SAVING…' : saveState === 'saved' ? 'SAVED TO DB2' : 'SAVE GAME'}
            </button>
            <button type="button" onClick={startAnalysis}>ANALYZE GAME</button>
            <button type="button" onClick={resetMatch}>NEW MATCH <i>→</i></button>
          </div>
        </div>
      )}

      {phase === 'analysis' && (
        <div className="analysis-panel">
          <div className="analysis-header">
            <h2>GAME ANALYSIS</h2>
            <div className="analysis-status">{analysisError ? 'ENGINE ERROR' : analyzing ? 'ANALYZING...' : 'COMPLETE'}</div>
          </div>

          {analysisError && <div className="analysis-error" role="alert">{analysisError}. Exit analysis and retry when the Stockfish worker is available.</div>}
          
          <div className="analysis-opening">
            <span>OPENING</span>
            <b>{getOpeningName(game.history())}</b>
          </div>

          <div className="evaluation-graph-container">
            <svg viewBox={`0 0 ${Math.max(10, analysisData.length - 1) * 10} 100`} className="evaluation-graph" preserveAspectRatio="none">
              <rect width="100%" height="100%" fill="var(--color-surface-dim)" />
              <line x1="0" y1="50" x2="100%" y2="50" stroke="var(--color-text-dim)" strokeWidth="0.5" strokeDasharray="2,2" />
              {analysisData.length > 1 && (
                <polyline
                  fill="none"
                  stroke="var(--color-primary)"
                  strokeWidth="1.5"
                  points={analysisData.map((d, i) => `${i * 10},${100 - d.winProbability}`).join(' ')}
                />
              )}
              {analysisData.length > 0 && (
                <circle cx={analysisIndex * 10} cy={100 - (analysisData[analysisIndex]?.winProbability ?? 50)} r="2" fill="var(--color-primary)" />
              )}
            </svg>
          </div>

          <div className="analysis-metrics">
            {['brilliant', 'great', 'best', 'good', 'inaccuracy', 'mistake', 'blunder', 'missed win'].map(cat => {
              const count = analysisData.filter(d => d.classification === cat).length
              if (count === 0 && cat !== 'blunder' && cat !== 'mistake') return null
              return (
                <div key={cat} className={`metric-badge metric-${cat.replace(' ', '-')}`}>
                  <span>{cat.toUpperCase()}</span>
                  <b>{count}</b>
                </div>
              )
            })}
          </div>

          <div className="analysis-controls">
            <button type="button" onClick={() => jumpAnalysis(0)}>|◀</button>
            <button type="button" onClick={() => stepAnalysis(-1)}>◀</button>
            <span className="analysis-move-number">MOVE {Math.floor((analysisIndex + 1) / 2)}</span>
            <button type="button" onClick={() => stepAnalysis(1)}>▶</button>
            <button type="button" onClick={() => jumpAnalysis(analysisData.length - 1)}>▶|</button>
          </div>
          
          <div className="analysis-footer-actions">
            <button type="button" className="db2-save-analysis-btn" onClick={() => void saveCurrentGame()} disabled={analyzing || saveState === 'analyzing' || saveState === 'saving'}>
              {saveState === 'saving' ? 'SAVING TO DB2…' : saveState === 'saved' ? 'SAVED TO DB2' : 'SAVE GAME TO DB2'}
            </button>
            <button type="button" className="close-analysis-btn" onClick={() => setPhase('gameOver')}>EXIT ANALYSIS</button>
          </div>
        </div>
      )}

      {(showHistory || phase === 'review') && phase !== 'analysis' && (
        <div className="move-history-panel">
          <div className="history-header">
            <h2>MOVE HISTORY</h2>
            <div className="pgn-actions">
              <button type="button" onClick={copyPGN} title="Copy PGN" aria-label="Copy PGN"><Icon name="copy" /></button>
              <button type="button" onClick={downloadPGN} title="Download PGN" aria-label="Download PGN"><Icon name="download" /></button>
              <button type="button" onClick={() => fileInputRef.current?.click()} title="Import PGN" aria-label="Import PGN"><Icon name="upload" /></button>
              <input type="file" ref={fileInputRef} onChange={importPGN} accept=".pgn" style={{ display: 'none' }} />
            </div>
          </div>
          
          <div className="move-list">
            {movePairs.map((pair, i) => (
              <div key={i} className="move-row">
                <span className="move-number">{i + 1}.</span>
                <button
                  className={`move-cell ${reviewIndex === i * 2 + 1 ? 'active' : ''}`}
                  onClick={() => enterReview(i * 2 + 1)}
                  ref={reviewIndex === i * 2 + 1 ? activeMoveRef : null}
                >{pair[0]}</button>
                {pair[1] ? (
                  <button
                    className={`move-cell ${reviewIndex === i * 2 + 2 ? 'active' : ''}`}
                    onClick={() => enterReview(i * 2 + 2)}
                    ref={reviewIndex === i * 2 + 2 ? activeMoveRef : null}
                  >{pair[1]}</button>
                ) : <span className="move-cell empty"></span>}
              </div>
            ))}
          </div>
          
          <div className="review-controls">
            <button onClick={() => jumpReview(0)} aria-label="First Move">|◀</button>
            <button onClick={() => stepReview(-1)} aria-label="Previous Move">◀</button>
            <button onClick={() => stepReview(1)} aria-label="Next Move">▶</button>
            <button onClick={() => jumpReview(game.history().length)} aria-label="Last Move">▶|</button>
          </div>

          {phase === 'review' && (
            <button className="resume-btn" onClick={exitReview}>RESUME GAME</button>
          )}
          {phase === 'playing' && showHistory && (
            <button className="resume-btn" onClick={() => setShowHistory(false)}>CLOSE</button>
          )}
        </div>
      )}

      {saveMessage && (
        <div className={`db2-save-toast db2-save-toast--${saveState}`} role={saveState === 'error' ? 'alert' : 'status'} aria-live="polite">
          <i aria-hidden="true" />
          <span>{saveMessage}</span>
          <button type="button" onClick={() => setSaveMessage(null)} aria-label="Dismiss save status">×</button>
        </div>
      )}

      <Db2Hub
        open={showDb2Hub}
        onClose={() => setShowDb2Hub(false)}
        refreshSignal={db2RefreshSignal}
        onViewGame={loadSavedGame}
        onAnalyzeGame={(saved) => { void analyzeSavedGame(saved) }}
      />

      {promotion && (
        <div className="promotion-card" role="dialog" aria-modal="true" aria-labelledby="promotion-title">
          <span id="promotion-title">PROMOTE PAWN</span>
          <div>{(['q', 'r', 'b', 'n'] as PieceSymbol[]).map((piece) => <button type="button" key={piece} onClick={() => completeMove(promotion.from, promotion.to, piece)}>{piece.toUpperCase()}</button>)}</div>
        </div>
      )}
      </div>
    </main>
  )
}
