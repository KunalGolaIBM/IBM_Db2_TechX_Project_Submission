import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import type { Overview } from '../../src/api/schemas'
import { API, overview } from '../fixtures'
import { apiError, authed, server } from '../msw'
import { renderApp } from '../render'

const serve = (o: Overview) => server.use(http.get(`${API}/api/overview`, authed(() => HttpResponse.json(o))))

describe('Intelligence overview', () => {
  const a = overview()
  const b = overview({
    complaints: { ...a.complaints, total: 1234, synthetic: 1200, real: 34, last_7d: 56, last_30d: 789 },
    investigations: { total: 21, active: 5, by_status: { OPEN: 2, RUNNING: 0, PENDING_REVIEW: 3, CLOSED: 16, FAILED: 0 } },
    recommendations: {
      total: 40,
      pending_review: 7,
      by_status: { PROPOSED: 7, APPROVED: 25, REJECTED: 8, NEEDS_INFO: 0 },
      by_generator: { LLM: 10, DETERMINISTIC_FALLBACK: 20, MANUAL: 9, UNKNOWN: 1 },
    },
    hotspots: { ...a.hotspots, total: 42 },
  })

  it('shows the figures the API returned: the same UI shows different numbers for different payloads', async () => {
    serve(a)
    const first = await renderApp('/', { as: 'analyst' })
    expect(await screen.findByTestId('kpi-complaints-value')).toHaveTextContent('52')
    expect(screen.getByTestId('kpi-investigations-value')).toHaveTextContent('2')
    expect(screen.getByTestId('kpi-pending-value')).toHaveTextContent('1')
    expect(screen.getByTestId('kpi-hotspots-value')).toHaveTextContent('12')
    first.unmount()

    serve(b)
    await renderApp('/', { as: 'analyst' })
    expect(await screen.findByTestId('kpi-complaints-value')).toHaveTextContent('1,234')
    expect(screen.getByTestId('kpi-investigations-value')).toHaveTextContent('5')
    expect(screen.getByTestId('kpi-pending-value')).toHaveTextContent('7')
    expect(screen.getByTestId('kpi-hotspots-value')).toHaveTextContent('42')
    expect(screen.getByTestId('provenance-split')).toHaveTextContent('1,200 synthetic, 34 real')
    expect(screen.getByTestId('rec-status-APPROVED')).toHaveTextContent('25')
    expect(screen.getByTestId('rec-status-REJECTED')).toHaveTextContent('8')
  })

  it('shows the true hotspot total, not just the number listed', async () => {
    serve(a) // 12 qualifying hotspots, only 2 listed
    await renderApp('/', { as: 'analyst' })
    expect(await screen.findByTestId('kpi-hotspots-value')).toHaveTextContent('12')
    expect(screen.getAllByTestId('hotspot-row')).toHaveLength(2)
  })

  it('explains how a hotspot is found, with the configured threshold and window', async () => {
    serve(a)
    await renderApp('/', { as: 'analyst' })
    const note = await screen.findByTestId('hotspot-method')
    expect(note).toHaveTextContent(`${a.hotspots.min_count} or more complaints in the last ${a.hotspots.window_days} days`)
    expect(note).toHaveTextContent('It counts reports; it does not predict anything.')
  })

  it('labels synthetic data and says how much of it there is', async () => {
    serve(a)
    await renderApp('/', { as: 'analyst' })
    expect(await screen.findByTestId('synthetic-banner')).toHaveTextContent('All 52 complaints in this database are SYNTHETIC')
  })

  it('says "x of y" when synthetic and real records are mixed, and shows no banner without synthetic data', async () => {
    serve(b)
    const mixed = await renderApp('/', { as: 'analyst' })
    expect(await screen.findByTestId('synthetic-banner')).toHaveTextContent('1200 of 1234 complaints are SYNTHETIC')
    mixed.unmount()
    serve(overview({ complaints: { ...a.complaints, total: 10, synthetic: 0, real: 10 } }))
    await renderApp('/', { as: 'analyst' })
    await screen.findByTestId('overview')
    expect(screen.queryByTestId('synthetic-banner')).toBeNull()
  })

  it('states that no recommendation came from a language model when none did', async () => {
    serve(a)
    await renderApp('/', { as: 'analyst' })
    expect(await screen.findByTestId('no-llm-note')).toHaveTextContent('None of the 3 recommendations were written by a language model')
  })

  it('uses singular wording when there is exactly one recommendation or one complaint', async () => {
    serve(overview({
      complaints: { ...a.complaints, total: 1, synthetic: 1, real: 0 },
      recommendations: { ...a.recommendations, total: 1, by_generator: { LLM: 0, DETERMINISTIC_FALLBACK: 1, MANUAL: 0, UNKNOWN: 0 } },
    }))
    await renderApp('/', { as: 'analyst' })
    expect(await screen.findByTestId('no-llm-note')).toHaveTextContent('The one recommendation was not written by a language model.')
    expect(screen.getByTestId('synthetic-banner')).toHaveTextContent('The only complaint in this database is SYNTHETIC')
  })

  it('does not make that claim when language-model recommendations exist', async () => {
    serve(b)
    await renderApp('/', { as: 'analyst' })
    await screen.findByTestId('overview')
    expect(screen.queryByTestId('no-llm-note')).toBeNull()
    const card = screen.getByTestId('chart-provenance')
    expect(within(card).getByText('AI model (LLM)')).toBeInTheDocument()
  })

  it('reports an unconfigured language model as a warning, with the fallback explained', async () => {
    serve(overview({ system: { ...a.system, llm: { configured: false, provider: 'anthropic', model: null, problem: 'LLM_MODEL is not set.' } } }))
    await renderApp('/', { as: 'analyst' })
    const row = await screen.findByTestId('status-llm')
    expect(row).toHaveAttribute('data-tone', 'warn')
    expect(row).toHaveTextContent('No language model configured')
    expect(row).toHaveTextContent('LLM_MODEL is not set.')
    expect(row).toHaveTextContent('labelled “no LLM”')
  })

  it('reports a configured model without claiming its connectivity was tested', async () => {
    serve(overview({ system: { ...a.system, llm: { configured: true, provider: 'anthropic', model: 'a-model', problem: null } } }))
    await renderApp('/', { as: 'analyst' })
    const row = await screen.findByTestId('status-llm')
    expect(row).toHaveAttribute('data-tone', 'info')
    expect(row).toHaveTextContent('Language model configured: anthropic')
    expect(row).toHaveTextContent('does not test connectivity')
  })

  it('shows the database product and version reported by the live system', async () => {
    serve(a)
    await renderApp('/', { as: 'analyst' })
    const row = await screen.findByTestId('status-db')
    expect(row).toHaveTextContent('DB2/LINUXX8664 12.01.0500')
    expect(row).toHaveTextContent('CIVICDB')
    expect(screen.getByTestId('connection-pill')).toHaveTextContent('Db2 connected')
  })

  it('every chart has a table twin with the same numbers', async () => {
    serve(a)
    const { user } = await renderApp('/', { as: 'analyst' })
    const card = await screen.findByTestId('chart-category')
    await user.click(within(card).getByRole('button', { name: 'View as table' }))
    const table = within(card).getByRole('table', { name: 'Complaints by category' })
    expect(table).toHaveTextContent('Pothole')
    expect(table).toHaveTextContent('13')
  })

  it('links each hotspot to the map with a deep link', async () => {
    serve(a)
    await renderApp('/', { as: 'analyst' })
    const [first] = await screen.findAllByTestId('hotspot-row')
    expect(within(first).getByRole('link').getAttribute('href')).toBe('/map?hotspot=C5499_15535%7CPOTHOLE')
  })

  it('is read-only information: reviewers see the same overview', async () => {
    serve(a)
    await renderApp('/', { as: 'reviewer' })
    expect(await screen.findByTestId('kpi-complaints-value')).toHaveTextContent('52')
    expect(screen.getByTestId('user-role')).toHaveTextContent('reviewer')
  })

  it('shows the pending-review count in the navigation', async () => {
    serve(a)
    await renderApp('/', { as: 'reviewer' })
    expect(await screen.findByTestId('nav-pending-count')).toHaveTextContent('1')
  })

  it('refetches on demand and shows when it was last updated', async () => {
    let calls = 0
    server.use(
      http.get(`${API}/api/overview`, authed(() => {
        calls += 1
        return HttpResponse.json(a)
      })),
    )
    const { user } = await renderApp('/', { as: 'analyst' })
    expect(await screen.findByTestId('updated-at')).toHaveTextContent('Updated 10:09:01 UTC')
    const before = calls
    await user.click(screen.getByRole('button', { name: 'Refresh' }))
    await waitFor(() => expect(calls).toBeGreaterThan(before))
  })

  it('503 database outage: explains it, offers Retry, and recovers', async () => {
    let healthy = false
    server.use(
      http.get(`${API}/api/overview`, authed(() => (healthy ? HttpResponse.json(a) : apiError(503, 'DB_UNAVAILABLE', 'The database is temporarily unavailable.')))),
    )
    const { user } = await renderApp('/', { as: 'analyst' })
    const notice = await screen.findByTestId('error-notice')
    expect(notice).toHaveAttribute('data-status', '503')
    expect(notice).toHaveTextContent('Database unavailable')
    expect(screen.getByTestId('connection-pill')).toHaveTextContent('Backend issue')
    healthy = true
    await user.click(within(notice).getByRole('button', { name: 'Retry' }))
    expect(await screen.findByTestId('kpi-complaints-value')).toHaveTextContent('52')
  })

  it('refuses to render a payload that does not match the contract', async () => {
    server.use(http.get(`${API}/api/overview`, authed(() => HttpResponse.json({ ...a, complaints: { ...a.complaints, total: 'many' } }))))
    await renderApp('/', { as: 'analyst' })
    const notice = await screen.findByTestId('error-notice')
    expect(notice).toHaveAttribute('data-code', 'CONTRACT_MISMATCH')
    expect(screen.queryByTestId('kpi-complaints-value')).toBeNull() // wrong numbers are never shown
  })
})
