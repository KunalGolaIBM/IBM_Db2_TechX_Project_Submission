import assert from 'node:assert/strict'
import test from 'node:test'
import { classifyMove, type AnalysisNode } from '../src/analyzer.ts'

function node(winProbability: number, overrides: Partial<AnalysisNode> = {}): AnalysisNode {
  return {
    fen: '8/8/8/8/8/8/8/K6k w - - 0 1',
    cp: 0,
    mate: null,
    winProbability,
    classification: null,
    status: 'evaluated',
    depth: 10,
    engine: 'stockfish-18-lite',
    ...overrides,
  }
}

test('classifies a large positive swing as brilliant before great', () => {
  assert.equal(classifyMove(node(50), node(70), true), 'brilliant')
})

test('does not propagate the book label beyond the opening window', () => {
  assert.equal(classifyMove(node(50, { classification: 'book' }), node(50), true), 'best')
})

test('does not classify timed-out engine output as a chess evaluation', () => {
  assert.equal(classifyMove(node(50), node(50, { status: 'timeout', depth: null }), true), null)
})
