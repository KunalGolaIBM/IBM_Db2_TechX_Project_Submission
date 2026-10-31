import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { dirname } from 'node:path'
import { chromium } from 'playwright'
import { Chess } from 'chess.js'

const repoRoot = dirname(fileURLToPath(import.meta.url))
const baseUrl = process.env.CHESS_BASE_URL ?? 'http://127.0.0.1:5173'
const startDevServer = process.env.CHESS_EXTERNAL_SERVER !== '1'

function positiveInteger(value, fallback, label) {
  const parsed = Number(value ?? fallback)
  if (!Number.isInteger(parsed) || parsed < 1) throw new Error(`${label} must be a positive integer`)
  return parsed
}

const gameCount = positiveInteger(process.argv[2] ?? process.env.CHESS_SMOKE_GAMES, 1, 'game count')
const playerMoveTarget = positiveInteger(process.env.CHESS_SMOKE_PLAYER_MOVES, 4, 'player move target')
const stateTimeoutMs = positiveInteger(process.env.CHESS_SMOKE_TIMEOUT_MS, 15_000, 'state timeout')
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

function launchDevServer() {
  const url = new URL(baseUrl)
  const npm = process.platform === 'win32' ? 'npm.cmd' : 'npm'
  const port = url.port || (url.protocol === 'https:' ? '443' : '80')
  const child = spawn(
    npm,
    ['run', 'dev', '--', '--host', url.hostname, '--port', port, '--strictPort'],
    { cwd: repoRoot, stdio: ['ignore', 'pipe', 'pipe'] },
  )
  let output = ''
  const remember = (chunk) => { output = `${output}${chunk}`.slice(-8_000) }
  child.stdout.on('data', remember)
  child.stderr.on('data', remember)
  child.recentOutput = () => output
  return child
}

async function waitForServer(server) {
  const deadline = Date.now() + stateTimeoutMs
  while (Date.now() < deadline) {
    if (server && server.exitCode !== null) {
      throw new Error(`Vite exited before becoming ready.\n${server.recentOutput()}`)
    }
    try {
      const response = await fetch(baseUrl, { signal: AbortSignal.timeout(1_000) })
      if (response.ok) return
    } catch {
      // Startup is still in progress.
    }
    await sleep(100)
  }
  throw new Error(`Timed out waiting for Vite at ${baseUrl}.${server ? `\n${server.recentOutput()}` : ''}`)
}

async function stopServer(server) {
  if (!server || server.exitCode !== null) return
  server.kill('SIGTERM')
  await new Promise((resolve) => {
    const timer = setTimeout(resolve, 3_000)
    server.once('exit', () => {
      clearTimeout(timer)
      resolve()
    })
  })
  if (server.exitCode === null) server.kill('SIGKILL')
}

async function nextPlayableState(page) {
  const handle = await page.waitForFunction(() => {
    const raw = document.documentElement.dataset.gameState
    if (!raw) return false
    try {
      const state = JSON.parse(raw)
      if (state.phase === 'gameOver') return state
      if (state.phase === 'playing' && !state.engineThinking && state.turn === state.playerColor) return state
    } catch {
      return false
    }
    return false
  }, undefined, { timeout: stateTimeoutMs })
  return handle.jsonValue()
}

async function playSmokeGame(page, gameNumber) {
  const browserErrors = []
  page.on('pageerror', (error) => browserErrors.push(error.message))
  page.on('console', (message) => {
    if (message.type() === 'error') browserErrors.push(message.text())
  })

  await page.goto(baseUrl, { waitUntil: 'domcontentloaded' })
  await page.locator('#start-btn').click()
  await page.locator('#begin-match').waitFor({ state: 'visible', timeout: stateTimeoutMs })
  await page.locator('#begin-match').click()
  await page.locator('#chess-canvas').waitFor({ state: 'attached', timeout: stateTimeoutMs })

  let playerMoves = 0
  let result = null
  while (playerMoves < playerMoveTarget) {
    const state = await nextPlayableState(page)
    if (state.phase === 'gameOver') {
      result = state.result ?? 'game over'
      break
    }

    const game = new Chess(state.fen)
    const move = game.moves({ verbose: true })
      .sort((left, right) => `${left.from}${left.to}${left.promotion ?? ''}`.localeCompare(`${right.from}${right.to}${right.promotion ?? ''}`))[0]
    if (!move) throw new Error(`Game ${gameNumber} exposed a player turn without a legal move`)

    await page.evaluate((selectedMove) => {
      document.dispatchEvent(new CustomEvent('codex:move', {
        detail: { from: selectedMove.from, to: selectedMove.to, promotion: selectedMove.promotion },
      }))
    }, move)

    await page.waitForFunction((previousFen) => {
      const raw = document.documentElement.dataset.gameState
      if (!raw) return false
      try {
        const current = JSON.parse(raw)
        return current.phase === 'gameOver' || current.fen !== previousFen
      } catch {
        return false
      }
    }, state.fen, { timeout: stateTimeoutMs })
    playerMoves += 1
  }

  if (browserErrors.length) throw new Error(`Browser errors:\n${browserErrors.join('\n')}`)
  console.log(`Game ${gameNumber}: ${result ? `ended (${result})` : `completed ${playerMoves} deterministic player moves`}`)
}

async function run() {
  let server
  let browser
  let failures = 0

  try {
    if (startDevServer) server = launchDevServer()
    await waitForServer(server)
    browser = await chromium.launch({ headless: true })
    const context = await browser.newContext({ reducedMotion: 'reduce' })

    for (let gameNumber = 1; gameNumber <= gameCount; gameNumber += 1) {
      const page = await context.newPage()
      try {
        await playSmokeGame(page, gameNumber)
      } catch (error) {
        failures += 1
        console.error(`Game ${gameNumber} failed:`, error)
      } finally {
        await page.close()
      }
    }
  } catch (error) {
    failures += 1
    console.error('Browser smoke setup failed:', error)
  } finally {
    await browser?.close().catch(() => undefined)
    await stopServer(server)
  }

  if (failures > 0) {
    console.error(`FAILED: ${failures} browser smoke scenario(s) failed.`)
    process.exitCode = 1
  } else {
    console.log(`SUCCESS: ${gameCount} browser smoke scenario(s) completed.`)
  }
}

await run()
