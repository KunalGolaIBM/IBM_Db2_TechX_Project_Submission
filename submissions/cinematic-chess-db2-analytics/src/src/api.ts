export type GameResult = '1-0' | '0-1' | '1/2-1/2' | '*'
export type PlayerColor = 'white' | 'black' | null
export type PlayerOutcome = 'win' | 'loss' | 'draw' | null

export interface SaveAnalysisInput {
  ply_number: number
  fen: string
  cp: number | null
  mate: number | null
  win_probability: number | null
  classification: string | null
  status: 'evaluated' | 'timeout' | 'error'
  depth: number | null
  engine: string
}

export interface SaveGameRequest {
  client_game_id: string
  source: 'played' | 'imported'
  pgn: string
  result: GameResult
  player_color: PlayerColor
  termination: string
  opponent_elo: number | null
  time_control: string
  opening_eco: string | null
  opening_name: string
  played_at: string
  analysis?: SaveAnalysisInput[]
}

export interface SavedMove {
  ply_number: number
  san: string
  uci: string
  fen_after: string
}

export interface SavedAnalysis {
  ply_number: number
  fen: string
  cp: number | null
  mate: number | null
  win_probability: number | null
  classification: string | null
  status: 'evaluated' | 'timeout' | 'error'
  depth: number | null
  engine: string
}

export interface SavedGameSummary {
  game_id: string
  source: 'played' | 'imported'
  played_at: string
  created_at: string
  result: GameResult
  player_color: PlayerColor
  player_outcome: PlayerOutcome
  termination: string
  opponent_elo: number | null
  time_control: string
  opening_eco: string | null
  opening_name: string
  move_count: number
}

export interface SavedGameDetail extends SavedGameSummary {
  pgn: string
  moves: SavedMove[]
  analysis: SavedAnalysis[]
}

export interface SavedGameList {
  items: SavedGameSummary[]
  total: number
  limit: number
  offset: number
}

export interface TopOpening {
  opening_eco: string | null
  opening_name: string
  total_games: number
  wins: number
  draws: number
  losses: number
  unknown: number
}

export interface AnalyticsSummary {
  total_games: number
  wins: number
  losses: number
  draws: number
  unknown: number
  most_played_openings: TopOpening[]
}

export interface CoachingRequest {
  game_id?: string
}

export interface CoachingResponse {
  provider: string
  model: string
  advice: string
}

export interface HealthResponse {
  status: 'ok' | 'unavailable'
  database: 'ok' | 'unavailable'
  coaching_enabled?: boolean
  llm_provider?: string | null
}

export interface SaveGameResponse {
  created: boolean
  game: SavedGameDetail
}

interface BackendErrorShape {
  code?: unknown
  message?: unknown
  detail?: unknown
  error?: unknown
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: unknown
  readonly retryable: boolean

  constructor(message: string, status: number, code: string, details?: unknown, retryable = false) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
    this.retryable = retryable
  }
}

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim()
export const API_BASE_URL = (configuredBaseUrl || 'http://localhost:8000/api/v1').replace(/\/$/, '')
const DEFAULT_TIMEOUT_MS = 10_000

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function backendError(payload: unknown, fallback: string) {
  if (typeof payload === 'string' && payload.trim()) return { code: 'request_failed', message: payload, details: payload }
  if (!isRecord(payload)) return { code: 'request_failed', message: fallback, details: payload }

  const body = payload as BackendErrorShape
  const nested = isRecord(body.error) ? body.error : undefined
  const detail = body.detail
  const detailRecord = isRecord(detail) ? detail : undefined
  const validationMessage = Array.isArray(detail) && isRecord(detail[0]) && typeof detail[0].msg === 'string' ? detail[0].msg : undefined
  const message = [nested?.message, nested?.detail, body.message, detailRecord?.message, typeof detail === 'string' ? detail : undefined, validationMessage]
    .find((value): value is string => typeof value === 'string' && value.length > 0) ?? fallback
  const code = [nested?.code, body.code, detailRecord?.code]
    .find((value): value is string => typeof value === 'string' && value.length > 0) ?? 'request_failed'

  return { code, message, details: detail ?? nested ?? payload }
}

async function requestJson<T>(path: string, init: RequestInit = {}, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<T> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeoutMs)
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers, signal: controller.signal })
    const contentType = response.headers.get('content-type') ?? ''
    const text = response.status === 204 ? '' : await response.text()
    let payload: unknown

    if (text) {
      if (!contentType.toLowerCase().includes('application/json')) {
        if (response.ok) {
          throw new ApiError('The server returned an unsupported response.', 502, 'invalid_content_type', { content_type: contentType }, true)
        }
        payload = text
      } else {
        try {
          payload = JSON.parse(text) as unknown
        } catch {
          throw new ApiError('The server returned invalid JSON.', 502, 'invalid_json', undefined, true)
        }
      }
    }

    if (!response.ok) {
      const parsed = backendError(payload, `Request failed with status ${response.status}.`)
      throw new ApiError(parsed.message, response.status, parsed.code, parsed.details, response.status >= 500 || response.status === 429)
    }

    return payload as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('The request timed out. Check the backend connection and try again.', 408, 'request_timeout', undefined, true)
    }
    throw new ApiError('The analytics service is unreachable. Ordinary gameplay is still available.', 0, 'network_error', error, true)
  } finally {
    window.clearTimeout(timer)
  }
}

export function saveGame(input: SaveGameRequest) {
  return requestJson<SaveGameResponse>('/games', { method: 'POST', body: JSON.stringify(input) }, 20_000)
}

export function listGames({ limit = 12, offset = 0 }: { limit?: number; offset?: number } = {}) {
  const query = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  return requestJson<SavedGameList>(`/games?${query.toString()}`, { cache: 'no-store' })
}

export function getGame(gameId: string) {
  return requestJson<SavedGameDetail>(`/games/${encodeURIComponent(gameId)}`, { cache: 'no-store' })
}

export function getAnalyticsSummary() {
  return requestJson<AnalyticsSummary>('/analytics/summary', { cache: 'no-store' })
}

export function requestCoaching(input: CoachingRequest = {}) {
  return requestJson<CoachingResponse>('/coaching', { method: 'POST', body: JSON.stringify(input) }, 30_000)
}

export function getHealth() {
  return requestJson<HealthResponse>('/health', { cache: 'no-store' }, 5_000)
}
