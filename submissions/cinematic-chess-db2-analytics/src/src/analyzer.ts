import { Chess } from 'chess.js'

export type MoveClassification = 'best' | 'brilliant' | 'great' | 'good' | 'inaccuracy' | 'mistake' | 'blunder' | 'missed win' | 'book'
export type AnalysisStatus = 'evaluated' | 'timeout' | 'engine-error'

export interface AnalysisNode {
  fen: string
  cp: number
  mate: number | null
  winProbability: number
  classification: MoveClassification | null
  status: AnalysisStatus
  depth: number | null
  engine: string
}

export type AnalysisResult = AnalysisNode[]

export function cpToWinProbability(cp: number): number {
  // Common formula to convert centipawns to win percentage (0 to 100)
  return 50 + 50 * (2 / (1 + Math.exp(-0.00368208 * cp)) - 1)
}

export function classifyMove(prev: AnalysisNode, current: AnalysisNode, isWhite: boolean): MoveClassification | null {
  if (prev.status !== 'evaluated' || current.status !== 'evaluated') return null

  const prevProb = prev.winProbability
  const curProb = current.winProbability
  const delta = isWhite ? curProb - prevProb : prevProb - curProb

  // Extremely rough heuristics for move classification
  if (delta < -20) {
    if (prev.mate !== null && current.mate === null) return 'missed win'
    return 'blunder'
  }
  if (delta < -10) return 'mistake'
  if (delta < -5) return 'inaccuracy'
  if (delta > 15) return 'brilliant'
  if (delta > 5) return 'great'
  if (delta >= -2) return 'best'
  return 'good'
}

export class Analyzer {
  private worker: Worker | null = null
  private resolvers = new Map<string, (result: { cp: number; mate: number | null; status: AnalysisStatus; depth: number | null }) => void>()
  private isReady = false
  private readyPromise: Promise<void> | null = null

  constructor() {
    // Stockfish's loader accepts the WASM URL in the worker fragment.
    this.worker = new Worker('/engine/stockfish.js#/engine/stockfish-18-lite-single.wasm')
    
    this.readyPromise = new Promise((resolve, reject) => {
      if (!this.worker) return
      const readyTimer = window.setTimeout(() => reject(new Error('Stockfish did not become ready')), 5000)
      this.worker.onmessage = (e) => {
        const msg = e.data
        if (msg === 'uciok') {
          window.clearTimeout(readyTimer)
          this.isReady = true
          resolve()
        }
        
        if (typeof msg === 'string' && msg.startsWith('info depth')) {
          const depthMatch = msg.match(/depth (\d+)/)
          const scoreMatch = msg.match(/score (cp|mate) (-?\d+)/)
          
          // We look for depth 10 evaluation
          if (depthMatch && parseInt(depthMatch[1]) >= 10 && scoreMatch) {
            const isMate = scoreMatch[1] === 'mate'
            const value = parseInt(scoreMatch[2])
            
            // Assuming this is for the current analysis task
            const resolver = this.resolvers.get('current')
            if (resolver) {
              resolver({
                cp: isMate ? (value > 0 ? 10000 : -10000) : value,
                mate: isMate ? value : null,
                status: 'evaluated',
                depth: parseInt(depthMatch[1]),
              })
              this.resolvers.delete('current')
            }
          }
        }
      }

      this.worker.onerror = () => {
        if (!this.isReady) {
          window.clearTimeout(readyTimer)
          reject(new Error('Stockfish worker failed to start'))
          return
        }
        const resolver = this.resolvers.get('current')
        if (!resolver) return
        resolver({ cp: 0, mate: null, status: 'engine-error', depth: null })
        this.resolvers.delete('current')
      }
    })
    
    this.worker.postMessage('uci')
  }

  async waitForReady() {
    if (!this.isReady) {
      await this.readyPromise
    }
  }

  private async evaluatePosition(fen: string): Promise<{ cp: number; mate: number | null; status: AnalysisStatus; depth: number | null }> {
    await this.waitForReady()
    
    return new Promise((resolve) => {
      const complete = (result: { cp: number; mate: number | null; status: AnalysisStatus; depth: number | null }) => {
        clearTimeout(timer)
        resolve(result)
      }
      this.resolvers.set('current', complete)
      this.worker?.postMessage(`position fen ${fen}`)
      // Depth 10 is fast enough for near-instant client-side analysis
      this.worker?.postMessage('go depth 10')
      
      // Fallback timeout in case engine hangs
      const timer = setTimeout(() => {
        if (this.resolvers.get('current') === complete) {
          this.resolvers.delete('current')
          resolve({ cp: 0, mate: null, status: 'timeout', depth: null })
        }
      }, 500)
    })
  }

  async analyzeGame(historyFens: string[], onProgress: (index: number, total: number, result: AnalysisNode) => void): Promise<AnalysisResult> {
    const results: AnalysisResult = []
    
    for (let i = 0; i < historyFens.length; i++) {
      const fen = historyFens[i]
      const { cp, mate, status, depth } = await this.evaluatePosition(fen)
      
      const game = new Chess(fen)
      const isWhiteToMove = game.turn() === 'w'
      // If it's black's turn to move now, the *previous* move was made by white.
      const moveWasMadeByWhite = !isWhiteToMove
      
      // stockfish evaluates from the perspective of the side to move
      // cp > 0 means good for side to move. We normalize it to White's perspective.
      const normalizedCp = isWhiteToMove ? cp : -cp
      const normalizedMate = mate !== null ? (isWhiteToMove ? mate : -mate) : null
      
      const winProbability = cpToWinProbability(normalizedCp)
      
      const node: AnalysisNode = {
        fen,
        cp: normalizedCp,
        mate: normalizedMate,
        winProbability,
        classification: null,
        status,
        depth,
        engine: 'stockfish-18-lite',
      }
      
      if (status !== 'evaluated') {
        node.classification = null
      } else if (i <= 5) {
        node.classification = 'book' // First 3 full moves are roughly book
      } else if (i > 0) {
        node.classification = classifyMove(results[i - 1], node, moveWasMadeByWhite)
      }
      
      results.push(node)
      onProgress(i, historyFens.length, node)
    }
    
    return results
  }

  terminate() {
    this.worker?.postMessage('quit')
    this.worker?.terminate()
  }
}
