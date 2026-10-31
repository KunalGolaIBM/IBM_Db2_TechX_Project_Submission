import assert from 'node:assert/strict'
import test from 'node:test'
import { Chess } from 'chess.js'
import { getCanonicalOutcome, getHistoryFens } from '../src/gameRecord.ts'

test('records the checkmating side with canonical PGN result notation', () => {
  const game = new Chess()
  for (const move of ['f3', 'e5', 'g4', 'Qh4#']) game.move(move)
  assert.deepEqual(getCanonicalOutcome(game, 'w', false, false), {
    result: '0-1',
    termination: 'checkmate',
  })
})

test('records an opponent timeout from the human player perspective', () => {
  assert.deepEqual(getCanonicalOutcome(new Chess(), 'b', false, true), {
    result: '0-1',
    termination: 'time_forfeit',
  })
})

test('creates one FEN for the initial position plus every played ply', () => {
  const game = new Chess()
  game.move('e4')
  game.move('c5')
  const fens = getHistoryFens(game)
  assert.equal(fens.length, 3)
  assert.equal(new Chess(fens[2]).history().length, 0)
  assert.match(fens[2], /^rnbqkbnr\/pp1ppppp/)
})

test('preserves a custom PGN starting position when building analysis FENs', () => {
  const game = new Chess('8/8/8/8/8/8/4K3/7k w - - 0 1')
  game.move('Kf3')
  const fens = getHistoryFens(game)
  assert.match(fens[0], /^8\/8\/8\/8\/8\/8\/4K3\/7k w/)
  assert.match(fens[1], /^8\/8\/8\/8\/8\/5K2\/8\/7k b/)
})

test('preserves the declared result of an imported nonterminal PGN', () => {
  const game = new Chess()
  game.loadPgn('[Result "1-0"]\n[Termination "resignation"]\n\n1. e4 e5 1-0')
  assert.deepEqual(getCanonicalOutcome(game, 'w', false, false), {
    result: '1-0',
    termination: 'resignation',
  })
})

test('uses an honest unknown termination when imported PGN omits it', () => {
  const game = new Chess()
  game.loadPgn('[Result "0-1"]\n\n1. d4 d5 0-1')
  assert.deepEqual(getCanonicalOutcome(game, 'w', false, false), {
    result: '0-1',
    termination: 'unknown',
  })
})
