import type { Color, PieceSymbol, Square } from 'chess.js'

export type Phase = 'landing' | 'showcase' | 'transition' | 'setup' | 'playing' | 'paused' | 'gameOver' | 'analysis' | 'review'
export type PlayerColor = Color | 'random'

export type TimeMode = 'unlimited' | 1 | 3 | 5 | 10 | 15

export interface ScenePiece {
  id: string
  square: Square
  type: PieceSymbol
  color: Color
  captured?: boolean
}

export interface LastMove {
  from: Square
  to: Square
}
