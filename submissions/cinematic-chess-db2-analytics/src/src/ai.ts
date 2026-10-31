import { Chess, type Move } from 'chess.js'

const values: Record<string, number> = { p: 100, n: 320, b: 330, r: 500, q: 900, k: 20000 }

function moveScore(game: Chess, move: Move, elo: number) {
  let score = move.captured ? values[move.captured] - values[move.piece] * 0.08 : 0
  if (move.promotion) score += values[move.promotion]
  game.move(move)
  if (game.isCheckmate()) score += 100000
  else if (game.inCheck()) score += 65
  const replies = game.moves().length
  game.undo()
  score -= replies * 0.3
  const accuracy = Math.max(0.1, Math.min(1, (elo - 500) / 2000))
  return score * accuracy + Math.random() * (140 * (1 - accuracy) + 4)
}

export async function chooseAiMove(fen: string, elo: number): Promise<Move | null> {
  const game = new Chess(fen)
  const moves = game.moves({ verbose: true })
  if (!moves.length) return null
  await new Promise((resolve) => setTimeout(resolve, 420 + Math.random() * 420))
  return moves.sort((a, b) => moveScore(game, b, elo) - moveScore(game, a, elo))[0]
}
