import { useCallback, useEffect, useId, useRef, useState, type CSSProperties, type KeyboardEvent } from 'react'
import {
  ApiError,
  getAnalyticsSummary,
  getGame,
  getHealth,
  listGames,
  requestCoaching,
  type AnalyticsSummary,
  type CoachingResponse,
  type HealthResponse,
  type SavedGameDetail,
  type SavedGameList,
  type SavedGameSummary,
} from './api'
import './db2.css'

type HubTab = 'games' | 'analytics' | 'coach'
type GameAction = 'view' | 'analyze'

export interface Db2HubProps {
  open: boolean
  onClose: () => void
  refreshSignal?: string | number
  onViewGame: (game: SavedGameDetail) => void
  onAnalyzeGame: (game: SavedGameDetail) => void
}

const PAGE_SIZE = 12
const TABS: { id: HubTab; label: string; index: string }[] = [
  { id: 'games', label: 'My Games', index: '01' },
  { id: 'analytics', label: 'Analytics', index: '02' },
  { id: 'coach', label: 'Coach', index: '03' },
]

function errorMessage(error: unknown) {
  return error instanceof ApiError ? error.message : 'The request could not be completed.'
}

function formatDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'DATE UNKNOWN'
  return new Intl.DateTimeFormat(undefined, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date).toUpperCase()
}

function outcomeLabel(game: SavedGameSummary) {
  if (!game.player_outcome) return game.result === '*' ? 'UNKNOWN' : game.result
  return game.player_outcome.toUpperCase()
}

function LoadState({ label }: { label: string }) {
  return (
    <div className="db2hub-loading" role="status" aria-live="polite">
      <span className="db2hub-loader" aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="db2hub-state db2hub-state--error" role="alert">
      <span className="db2hub-state-code">LINK / INTERRUPTED</span>
      <h3>Data channel unavailable</h3>
      <p>{message}</p>
      <button type="button" className="db2hub-action" onClick={onRetry}>RETRY CONNECTION</button>
    </div>
  )
}

export default function Db2Hub({ open, onClose, refreshSignal, onViewGame, onAnalyzeGame }: Db2HubProps) {
  const titleId = useId()
  const tabPrefix = useId()
  const dialogRef = useRef<HTMLElement>(null)
  const closeRef = useRef<HTMLButtonElement>(null)
  const previousFocusRef = useRef<HTMLElement | null>(null)
  const gamesRequestRef = useRef(0)
  const [tab, setTab] = useState<HubTab>('games')
  const [page, setPage] = useState(0)
  const [games, setGames] = useState<SavedGameList | null>(null)
  const [gamesLoading, setGamesLoading] = useState(false)
  const [gamesError, setGamesError] = useState<string | null>(null)
  const [detailBusy, setDetailBusy] = useState<string | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null)
  const [analyticsLoading, setAnalyticsLoading] = useState(false)
  const [analyticsError, setAnalyticsError] = useState<string | null>(null)
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [healthLoading, setHealthLoading] = useState(false)
  const [healthError, setHealthError] = useState<string | null>(null)
  const [coaching, setCoaching] = useState<CoachingResponse | null>(null)
  const [coachingLoading, setCoachingLoading] = useState(false)
  const [coachingError, setCoachingError] = useState<string | null>(null)
  const [coachingDisabledReason, setCoachingDisabledReason] = useState<string | null>(null)

  const loadGames = useCallback(async () => {
    const requestId = ++gamesRequestRef.current
    setGamesLoading(true)
    setGamesError(null)
    try {
      const result = await listGames({ limit: PAGE_SIZE, offset: page * PAGE_SIZE })
      if (requestId === gamesRequestRef.current) setGames(result)
    } catch (error) {
      if (requestId === gamesRequestRef.current) setGamesError(errorMessage(error))
    } finally {
      if (requestId === gamesRequestRef.current) setGamesLoading(false)
    }
  }, [page])

  const loadAnalytics = useCallback(async () => {
    setAnalyticsLoading(true)
    setAnalyticsError(null)
    try {
      setAnalytics(await getAnalyticsSummary())
    } catch (error) {
      setAnalyticsError(errorMessage(error))
    } finally {
      setAnalyticsLoading(false)
    }
  }, [])

  const loadHealth = useCallback(async () => {
    setHealthLoading(true)
    setHealthError(null)
    try {
      const result = await getHealth()
      setHealth(result)
      if (result.coaching_enabled !== false) setCoachingDisabledReason(null)
    } catch (error) {
      setHealth(null)
      setHealthError(errorMessage(error))
    } finally {
      setHealthLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!open) return
    void loadGames()
  }, [open, refreshSignal, loadGames])

  useEffect(() => {
    if (!open) return
    void loadAnalytics()
    void loadHealth()
  }, [open, refreshSignal, loadAnalytics, loadHealth])

  useEffect(() => {
    if (!open) return
    previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const frame = window.requestAnimationFrame(() => closeRef.current?.focus())
    const onEscape = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onEscape)
    return () => {
      document.removeEventListener('keydown', onEscape)
      window.cancelAnimationFrame(frame)
      document.body.style.overflow = previousOverflow
      previousFocusRef.current?.focus()
    }
  }, [open, onClose])

  const handleDialogKeys = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key !== 'Tab') return
    const focusable = Array.from(dialogRef.current?.querySelectorAll<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ) ?? []).filter((element) => !element.hasAttribute('hidden'))
    if (!focusable.length) return
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  const handleTabKeys = (event: KeyboardEvent<HTMLButtonElement>, current: number) => {
    let next = current
    if (event.key === 'ArrowRight') next = (current + 1) % TABS.length
    else if (event.key === 'ArrowLeft') next = (current - 1 + TABS.length) % TABS.length
    else if (event.key === 'Home') next = 0
    else if (event.key === 'End') next = TABS.length - 1
    else return
    event.preventDefault()
    setTab(TABS[next].id)
    document.getElementById(`${tabPrefix}-tab-${TABS[next].id}`)?.focus()
  }

  const handleGameAction = async (gameId: string, action: GameAction) => {
    const busyKey = `${gameId}:${action}`
    setDetailBusy(busyKey)
    setDetailError(null)
    let detail: SavedGameDetail
    try {
      detail = await getGame(gameId)
    } catch (error) {
      setDetailError(errorMessage(error))
      setDetailBusy(null)
      return
    }
    setDetailBusy(null)
    if (action === 'view') onViewGame(detail)
    else onAnalyzeGame(detail)
    onClose()
  }

  const loadCoaching = async () => {
    setCoachingLoading(true)
    setCoachingError(null)
    try {
      setCoaching(await requestCoaching())
    } catch (error) {
      if (error instanceof ApiError && ['coaching_disabled', 'llm_not_configured'].includes(error.code)) {
        setCoachingDisabledReason(error.message)
      } else {
        setCoachingError(errorMessage(error))
      }
    } finally {
      setCoachingLoading(false)
    }
  }

  if (!open) return null

  const pageCount = Math.max(1, Math.ceil((games?.total ?? 0) / PAGE_SIZE))
  const coachingDisabled = health?.coaching_enabled === false || coachingDisabledReason !== null
  const databaseStatus = healthLoading
    ? 'CHECKING LINK'
    : health?.database === 'ok'
      ? 'DB2 ONLINE'
      : healthError
        ? 'DB2 OFFLINE'
        : 'DB2 DEGRADED'

  return (
    <div className="db2hub-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <section
        ref={dialogRef}
        className="db2hub-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onKeyDown={handleDialogKeys}
      >
        <aside className="db2hub-rail" aria-hidden="true">
          <span className="db2hub-rail-mark">IBM</span>
          <div className="db2hub-rail-trace"><i /><i /><i /><i /></div>
          <strong>DB2</strong>
          <span>TECHX / 2026</span>
        </aside>

        <div className="db2hub-body">
          <header className="db2hub-header">
            <div>
              <span className="db2hub-kicker">PERSISTENT MATCH INTELLIGENCE</span>
              <h2 id={titleId}>GAME MEMORY</h2>
            </div>
            <div className="db2hub-header-tools">
              <span className={`db2hub-link ${health?.database === 'ok' ? 'is-online' : ''}`}>
                <i aria-hidden="true" />{databaseStatus}
              </span>
              <button ref={closeRef} type="button" className="db2hub-close" onClick={onClose} aria-label="Close game memory">×</button>
            </div>
          </header>

          <div className="db2hub-demo-note">
            <span>DEMO SCOPE / SINGLE USER</span>
            <p>This TechX build uses one IBM Db2 game library. No account or private-user boundary is implied.</p>
          </div>

          <nav className="db2hub-tabs" role="tablist" aria-label="Game memory sections">
            {TABS.map((item, index) => (
              <button
                key={item.id}
                id={`${tabPrefix}-tab-${item.id}`}
                type="button"
                role="tab"
                aria-selected={tab === item.id}
                aria-controls={`${tabPrefix}-panel-${item.id}`}
                tabIndex={tab === item.id ? 0 : -1}
                onClick={() => setTab(item.id)}
                onKeyDown={(event) => handleTabKeys(event, index)}
              >
                <span>{item.index}</span>{item.label}
              </button>
            ))}
          </nav>

          <div className="db2hub-content">
            {tab === 'games' && (
              <section
                id={`${tabPrefix}-panel-games`}
                className="db2hub-tabpanel"
                role="tabpanel"
                aria-labelledby={`${tabPrefix}-tab-games`}
                aria-busy={gamesLoading}
              >
                <div className="db2hub-section-heading">
                  <div><span>ARCHIVE INDEX</span><h3>Saved matches</h3></div>
                  <b>{String(games?.total ?? 0).padStart(2, '0')} GAMES</b>
                </div>

                {detailError && <div className="db2hub-inline-error" role="alert">{detailError}</div>}
                {gamesLoading && <LoadState label="READING GAME RECORDS" />}
                {!gamesLoading && gamesError && <ErrorState message={gamesError} onRetry={() => void loadGames()} />}
                {!gamesLoading && !gamesError && games?.items.length === 0 && (
                  <div className="db2hub-state">
                    <span className="db2hub-state-code">ARCHIVE / EMPTY</span>
                    <h3>No saved games yet</h3>
                    <p>Finish a match and choose Save Game. The first record will appear here.</p>
                  </div>
                )}
                {!gamesLoading && !gamesError && games && games.items.length > 0 && (
                  <>
                    <ol className="db2hub-game-list">
                      {games.items.map((game, index) => (
                        <li key={game.game_id}>
                          <article className="db2hub-game-row">
                            <div className="db2hub-game-index">{String(games.offset + index + 1).padStart(2, '0')}</div>
                            <div className="db2hub-game-primary">
                              <span>{game.opening_eco ?? '—'} / {game.source.toUpperCase()}</span>
                              <h4>{game.opening_name || 'Unclassified opening'}</h4>
                              <p>{formatDate(game.played_at)} · {game.move_count} PLY · {game.time_control.toUpperCase()}</p>
                            </div>
                            <div className={`db2hub-outcome is-${game.player_outcome}`}>{outcomeLabel(game)}</div>
                            <div className="db2hub-row-actions">
                              <button
                                type="button"
                                disabled={detailBusy !== null}
                                onClick={() => void handleGameAction(game.game_id, 'view')}
                              >{detailBusy === `${game.game_id}:view` ? 'LOADING' : 'VIEW'}</button>
                              <button
                                type="button"
                                disabled={detailBusy !== null}
                                onClick={() => void handleGameAction(game.game_id, 'analyze')}
                              >{detailBusy === `${game.game_id}:analyze` ? 'LOADING' : 'ANALYZE'} <i>↗</i></button>
                            </div>
                          </article>
                        </li>
                      ))}
                    </ol>
                    {pageCount > 1 && (
                      <div className="db2hub-pagination" aria-label="Saved games pages">
                        <button type="button" disabled={page === 0 || gamesLoading} onClick={() => setPage((value) => Math.max(0, value - 1))}>← PREV</button>
                        <span>PAGE {page + 1} / {pageCount}</span>
                        <button type="button" disabled={page + 1 >= pageCount || gamesLoading} onClick={() => setPage((value) => value + 1)}>NEXT →</button>
                      </div>
                    )}
                  </>
                )}
              </section>
            )}

            {tab === 'analytics' && (
              <section
                id={`${tabPrefix}-panel-analytics`}
                className="db2hub-tabpanel"
                role="tabpanel"
                aria-labelledby={`${tabPrefix}-tab-analytics`}
                aria-busy={analyticsLoading}
              >
                <div className="db2hub-section-heading">
                  <div><span>QUERY / LIVE</span><h3>Performance record</h3></div>
                  <b>IBM DB2</b>
                </div>
                {analyticsLoading && <LoadState label="CALCULATING MATCH TOTALS" />}
                {!analyticsLoading && analyticsError && <ErrorState message={analyticsError} onRetry={() => void loadAnalytics()} />}
                {!analyticsLoading && !analyticsError && analytics && (
                  <>
                    <div className="db2hub-scoreline" aria-label="Game statistics">
                      {[
                        ['TOTAL', analytics.total_games],
                        ['WINS', analytics.wins],
                        ['LOSSES', analytics.losses],
                        ['DRAWS', analytics.draws],
                      ].map(([label, value]) => (
                        <div key={label}><span>{label}</span><strong>{String(value).padStart(2, '0')}</strong></div>
                      ))}
                    </div>
                    {analytics.total_games === 0 ? (
                      <div className="db2hub-state">
                        <span className="db2hub-state-code">QUERY / NO ROWS</span>
                        <h3>Statistics start with game one</h3>
                        <p>Saved results will become the source for wins, losses, draws and opening frequency.</p>
                      </div>
                    ) : (
                      <div className="db2hub-openings">
                        <div className="db2hub-subhead"><span>MOST PLAYED OPENINGS</span><span>SHARE</span></div>
                        {analytics.most_played_openings.length === 0 ? (
                          <p className="db2hub-muted">No classified openings are available yet.</p>
                        ) : (
                          <ol>
                            {analytics.most_played_openings.map((opening, index) => {
                              const percentage = analytics.total_games > 0 ? (opening.total_games / analytics.total_games) * 100 : 0
                              return <li key={`${opening.opening_eco ?? 'unknown'}-${opening.opening_name}`}>
                                <span className="db2hub-opening-rank">{String(index + 1).padStart(2, '0')}</span>
                                <div>
                                  <span>{opening.opening_eco ?? '—'}</span>
                                  <strong>{opening.opening_name}</strong>
                                  <i style={{ '--db2-share': `${Math.max(0, Math.min(100, percentage))}%` } as CSSProperties} />
                                </div>
                                <b>{opening.total_games}<small> / {percentage.toFixed(0)}%</small></b>
                              </li>
                            })}
                          </ol>
                        )}
                      </div>
                    )}
                  </>
                )}
              </section>
            )}

            {tab === 'coach' && (
              <section
                id={`${tabPrefix}-panel-coach`}
                className="db2hub-tabpanel"
                role="tabpanel"
                aria-labelledby={`${tabPrefix}-tab-coach`}
                aria-busy={coachingLoading || healthLoading}
              >
                <div className="db2hub-section-heading">
                  <div><span>OPTIONAL LAYER</span><h3>AI coaching</h3></div>
                  <b>{coaching?.provider.toUpperCase() ?? health?.llm_provider?.toUpperCase() ?? 'NO PAID API REQUIRED'}</b>
                </div>

                {healthLoading && <LoadState label="CHECKING COACH CONFIGURATION" />}
                {!healthLoading && healthError && !health && <ErrorState message={healthError} onRetry={() => void loadHealth()} />}
                {!healthLoading && !healthError && coachingDisabled && (
                  <div className="db2hub-coach-disabled">
                    <span aria-hidden="true">◇</span>
                    <div>
                      <p>COACH / STANDBY</p>
                      <h3>Optional by design</h3>
                      <p>{coachingDisabledReason || 'No LLM provider is configured. Db2 history, analytics and ordinary gameplay remain fully available.'}</p>
                    </div>
                  </div>
                )}
                {!healthLoading && !healthError && !coachingDisabled && coachingLoading && <LoadState label="BUILDING COACHING NOTES FROM DB2" />}
                {!healthLoading && !healthError && !coachingDisabled && !coachingLoading && coachingError && <ErrorState message={coachingError} onRetry={() => void loadCoaching()} />}
                {!healthLoading && !healthError && !coachingDisabled && !coachingLoading && !coachingError && !coaching && (
                  <div className="db2hub-coach-ready">
                    <div className="db2hub-coach-orbit" aria-hidden="true"><i /><i /><i /></div>
                    <div>
                      <span>STATISTICS → PATTERNS → GUIDANCE</span>
                      <h3>Read the shape of your games</h3>
                      <p>The coach uses saved Db2 results and opening frequency. It never blocks gameplay or database features.</p>
                      <button type="button" className="db2hub-action" onClick={() => void loadCoaching()}>GENERATE COACHING NOTES</button>
                    </div>
                  </div>
                )}
                {!healthLoading && !healthError && !coachingLoading && coaching && (
                  <div className="db2hub-coach-report">
                    <div className="db2hub-coach-summary">
                      <span>COACH SUMMARY</span>
                      <p>{coaching.advice || 'No coaching advice was returned.'}</p>
                    </div>
                    <div className="db2hub-recommendations"><span>MODEL TRACE</span><p>{coaching.provider} / {coaching.model}</p></div>
                    <button type="button" className="db2hub-text-action" onClick={() => void loadCoaching()}>REFRESH FROM LATEST STATS ↗</button>
                  </div>
                )}
              </section>
            )}
          </div>
        </div>
      </section>
    </div>
  )
}
