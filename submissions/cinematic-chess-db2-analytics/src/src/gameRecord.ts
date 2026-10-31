import { Chess, type Color } from 'chess.js'

export type CanonicalResult = '1-0' | '0-1' | '1/2-1/2' | '*'
export type GameTermination =
  | 'checkmate'
  | 'time_forfeit'
  | 'stalemate'
  | 'repetition'
  | 'insufficient_material'
  | 'fifty_move_rule'
  | 'resignation'
  | 'abandonment'
  | 'agreement'
  | 'draw'
  | 'unknown'
  | 'unfinished'

export interface CanonicalOutcome {
  result: CanonicalResult
  termination: GameTermination
}

function winResult(winner: Color): CanonicalResult {
  return winner === 'w' ? '1-0' : '0-1'
}

function importedOutcome(game: Chess): CanonicalOutcome | null {
  const headers = game.getHeaders()
  const result = headers.Result
  if (result !== '1-0' && result !== '0-1' && result !== '1/2-1/2') return null

  const normalized = (headers.Termination ?? '').trim().toLowerCase().replace(/[ -]+/g, '_')
  const decisive = new Set<GameTermination>(['time_forfeit', 'resignation', 'abandonment', 'unknown'])
  const drawn = new Set<GameTermination>(['repetition', 'fifty_move_rule', 'agreement', 'draw', 'unknown'])
  const allowed = result === '1/2-1/2' ? drawn : decisive
  const termination = allowed.has(normalized as GameTermination) ? normalized as GameTermination : 'unknown'
  return { result, termination }
}

export function getCanonicalOutcome(
  game: Chess,
  playerColor: Color,
  playerTimedOut: boolean,
  opponentTimedOut: boolean,
): CanonicalOutcome {
  if (playerTimedOut) return { result: winResult(playerColor === 'w' ? 'b' : 'w'), termination: 'time_forfeit' }
  if (opponentTimedOut) return { result: winResult(playerColor), termination: 'time_forfeit' }
  if (game.isCheckmate()) return { result: winResult(game.turn() === 'w' ? 'b' : 'w'), termination: 'checkmate' }
  if (game.isStalemate()) return { result: '1/2-1/2', termination: 'stalemate' }
  if (game.isThreefoldRepetition()) return { result: '1/2-1/2', termination: 'repetition' }
  if (game.isInsufficientMaterial()) return { result: '1/2-1/2', termination: 'insufficient_material' }
  if (game.isDrawByFiftyMoves()) return { result: '1/2-1/2', termination: 'fifty_move_rule' }
  if (game.isDraw()) return { result: '1/2-1/2', termination: 'draw' }
  const headerOutcome = importedOutcome(game)
  if (headerOutcome) return headerOutcome
  return { result: '*', termination: 'unfinished' }
}

export function getHistoryFens(game: Chess): string[] {
  const moves = game.history({ verbose: true })
  if (moves.length === 0) return [game.fen()]
  return [moves[0].before, ...moves.map((move) => move.after)]
}
