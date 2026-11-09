import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import type { MapViewProps } from '../../src/map/MapView'
import { API, complaint, hotspot, overview } from '../fixtures'
import { authed, server } from '../msw'
import { renderApp } from '../render'

// Leaflet needs a real layout engine, so the map itself is exercised in the Playwright suite. Here MapView is a
// stand-in that reports what the page handed it, which is what the filters and lists are responsible for.
vi.mock('../../src/map/MapView', () => ({
  MapView: (p: MapViewProps) => (
    <div
      data-testid="map-stub"
      data-complaints={p.complaints.length}
      data-hotspots={p.hotspots.length}
      data-synthetic={p.complaints.filter((c) => c.is_synthetic).length}
      data-selected-complaint={p.selectedComplaintId ?? ''}
      data-selected-hotspot={p.selectedHotspotKey ?? ''}
      data-fit={p.fitSignal}
    >
      <button type="button" onClick={() => p.onTileStatus?.('unavailable')}>stub-tiles-fail</button>
      <button type="button" onClick={() => p.complaints[0] && p.onSelectComplaint(p.complaints[0].complaint_id)}>stub-click-marker</button>
      <button type="button" onClick={() => p.hotspots[0] && p.onSelectHotspot(`${p.hotspots[0].geo_cell}|${p.hotspots[0].category}`)}>stub-click-hotspot</button>
    </div>
  ),
}))

const COMPLAINTS = [
  complaint({ complaint_id: 1, category: 'POTHOLE', title: 'Pothole one', is_synthetic: true }),
  complaint({ complaint_id: 2, category: 'POTHOLE', title: 'Pothole two', is_synthetic: true }),
  complaint({ complaint_id: 3, category: 'POTHOLE', title: 'Pothole three (real)', is_synthetic: false }),
  complaint({ complaint_id: 4, category: 'DRAINAGE', title: 'Blocked drain', is_synthetic: true, geo_cell: 'C5497_15536' }),
  complaint({ complaint_id: 5, category: 'GARBAGE', title: 'Overflowing bin', is_synthetic: false, geo_cell: 'C5500_15533' }),
]
const HOTSPOTS = [
  hotspot({ category: 'POTHOLE', geo_cell: 'C5499_15535', complaint_count: 9 }),
  hotspot({ category: 'DRAINAGE', geo_cell: 'C5497_15536', complaint_count: 4 }),
  hotspot({ category: 'GARBAGE', geo_cell: 'C5500_15533', complaint_count: 3 }),
]

function serveMapData(requests: URLSearchParams[] = []) {
  server.use(
    http.get(`${API}/api/complaints`, () => HttpResponse.json(COMPLAINTS)),
    http.get(`${API}/api/hotspots`, ({ request }) => {
      requests.push(new URL(request.url).searchParams)
      return HttpResponse.json(HOTSPOTS)
    }),
  )
}
const stub = () => screen.findByTestId('map-stub')
const countText = () => screen.getByTestId('map-count').textContent

describe('Geographic intelligence: filters', () => {
  it('starts with everything shown and labels the data as synthetic', async () => {
    serveMapData()
    await renderApp('/map', { as: 'analyst' })
    const map = await stub()
    expect(map).toHaveAttribute('data-complaints', '5')
    expect(map).toHaveAttribute('data-hotspots', '3')
    expect(countText()).toMatch(/Showing 5 complaints and 3 hotspots/)
    expect(screen.getByTestId('synthetic-banner')).toHaveTextContent('3 of 5 complaints are SYNTHETIC')
  })

  it('the filter panel can be collapsed (phones), says how many filters are active, and keeps the count visible', async () => {
    serveMapData()
    const { user } = await renderApp('/map', { as: 'analyst' })
    await stub()
    const toggle = screen.getByTestId('filters-toggle')
    expect(toggle).toHaveAttribute('aria-expanded', 'false') // collapsed by default so the map is not pushed below the fold
    expect(toggle).toHaveAttribute('aria-controls', 'map-filter-fields')
    expect(document.getElementById('map-filter-fields')).toContainElement(screen.getByRole('group', { name: 'Filter by category' }))
    expect(screen.getByTestId('map-count')).toBeInTheDocument() // outside the collapsible part

    await user.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(within(toggle).queryByLabelText(/active/)).toBeNull() // nothing filtered yet
    await user.click(within(screen.getByRole('group', { name: 'Filter by category' })).getByRole('button', { name: /Pothole/ }))
    await user.selectOptions(screen.getByLabelText('Hotspot window'), '90')
    expect(within(toggle).getByLabelText('2 active')).toBeInTheDocument()
  })

  it('uses singular words for a single complaint or hotspot ("1 hotspots" is wrong)', async () => {
    serveMapData()
    const { user } = await renderApp('/map', { as: 'analyst' })
    await stub()
    await user.click(within(screen.getByRole('group', { name: 'Filter by category' })).getByRole('button', { name: /Drainage/ }))
    expect(countText()).toMatch(/Showing 1 complaint and 1 hotspot\b(?!s)/)
    expect(countText()).not.toMatch(/1 complaints|1 hotspots/)
  })

  it('category chips filter complaints and hotspots together, and show per-category counts', async () => {
    serveMapData()
    const { user } = await renderApp('/map', { as: 'analyst' })
    await stub()
    const filters = screen.getByRole('group', { name: 'Filter by category' })
    expect(within(filters).getByRole('button', { name: /Pothole\s*3/ })).toBeInTheDocument()
    expect(within(filters).getByRole('button', { name: /Road damage\s*0/ })).toBeInTheDocument()

    await user.click(within(filters).getByRole('button', { name: /Pothole/ }))
    expect(screen.getByTestId('map-stub')).toHaveAttribute('data-complaints', '3')
    expect(screen.getByTestId('map-stub')).toHaveAttribute('data-hotspots', '1')
    expect(within(filters).getByRole('button', { name: /Pothole/ })).toHaveAttribute('aria-pressed', 'true')
    expect(within(filters).getByRole('button', { name: 'All' })).toHaveAttribute('aria-pressed', 'false')

    await user.click(within(filters).getByRole('button', { name: /Drainage/ })) // multi-select
    expect(screen.getByTestId('map-stub')).toHaveAttribute('data-complaints', '4')
    expect(screen.getByTestId('map-stub')).toHaveAttribute('data-hotspots', '2')

    await user.click(within(filters).getByRole('button', { name: 'All' }))
    expect(screen.getByTestId('map-stub')).toHaveAttribute('data-complaints', '5')
  })

  it('the record-type filter separates synthetic from real, and the legend counts what is visible', async () => {
    serveMapData()
    const { user } = await renderApp('/map', { as: 'analyst' })
    await stub()
    expect(screen.getByTestId('legend-synthetic')).toHaveTextContent('Dashed ring: SYNTHETIC demonstration record')
    expect(screen.getByTestId('legend-synthetic')).toHaveTextContent('(3)')
    expect(screen.getByTestId('legend-real')).toHaveTextContent('(2)')

    await user.selectOptions(screen.getByLabelText('Records'), 'synthetic')
    expect(screen.getByTestId('map-stub')).toHaveAttribute('data-complaints', '3')
    expect(screen.getByTestId('map-stub')).toHaveAttribute('data-synthetic', '3')
    expect(screen.getByTestId('legend-real')).toHaveTextContent('(0)')

    await user.selectOptions(screen.getByLabelText('Records'), 'real')
    expect(screen.getByTestId('map-stub')).toHaveAttribute('data-complaints', '2')
    expect(screen.getByTestId('legend-synthetic')).toHaveTextContent('(0)')
  })

  it('the hotspot window and minimum cluster are sent to the server', async () => {
    const requests: URLSearchParams[] = []
    serveMapData(requests)
    const { user } = await renderApp('/map', { as: 'analyst' })
    await stub()
    expect(requests[0].get('days')).toBe('30')
    expect(requests[0].get('min_count')).toBe('3')
    await user.selectOptions(screen.getByLabelText('Hotspot window'), '90')
    await user.selectOptions(screen.getByLabelText('Min. cluster'), '5')
    await waitFor(() => expect(requests.at(-1)?.get('days')).toBe('90'))
    await waitFor(() => expect(requests.at(-1)?.get('min_count')).toBe('5'))
  })

  it('Reset restores the defaults and asks the map to refit', async () => {
    serveMapData()
    const { user } = await renderApp('/map', { as: 'analyst' })
    await stub()
    await user.click(within(screen.getByRole('group', { name: 'Filter by category' })).getByRole('button', { name: /Pothole/ }))
    await user.selectOptions(screen.getByLabelText('Records'), 'real')
    await user.click(screen.getByRole('button', { name: 'Reset' }))
    const map = screen.getByTestId('map-stub')
    expect(map).toHaveAttribute('data-complaints', '5')
    expect(map).toHaveAttribute('data-fit', '1')
    await user.click(screen.getByRole('button', { name: 'Fit to data' }))
    expect(screen.getByTestId('map-stub')).toHaveAttribute('data-fit', '2')
  })

  it('says when only the latest complaints were loaded out of a larger total', async () => {
    serveMapData()
    const o = overview()
    server.use(http.get(`${API}/api/overview`, authed(() => HttpResponse.json({ ...o, complaints: { ...o.complaints, total: 500 } }))))
    await renderApp('/map', { as: 'analyst' })
    await stub()
    await waitFor(() => expect(countText()).toMatch(/latest 5 of 500 complaints loaded/))
  })
})

describe('Geographic intelligence: browsing', () => {
  it('lists hotspots with counts, and selecting one hands it to the map', async () => {
    serveMapData()
    const { user } = await renderApp('/map', { as: 'analyst' })
    await stub()
    const items = within(screen.getByTestId('hotspot-list')).getAllByTestId('hotspot-item')
    expect(items).toHaveLength(3)
    expect(items[0]).toHaveTextContent('Pothole')
    expect(items[0]).toHaveTextContent('9')
    await user.click(items[1])
    expect(screen.getByTestId('map-stub')).toHaveAttribute('data-selected-hotspot', 'C5497_15536|DRAINAGE')
    expect(screen.getAllByTestId('hotspot-item')[1]).toHaveAttribute('aria-pressed', 'true')
  })

  it('a hotspot deep link (from the overview) preselects it', async () => {
    serveMapData()
    await renderApp('/map?hotspot=C5499_15535%7CPOTHOLE', { as: 'analyst' })
    expect(await stub()).toHaveAttribute('data-selected-hotspot', 'C5499_15535|POTHOLE')
    expect(screen.getAllByTestId('hotspot-item')[0]).toHaveAttribute('aria-pressed', 'true')
  })

  it('a complaint deep link opens its details, marked synthetic', async () => {
    serveMapData()
    await renderApp('/map?complaint=2', { as: 'analyst' })
    const detail = await screen.findByTestId('selected-complaint')
    expect(detail).toHaveTextContent('Pothole two')
    expect(within(detail).getByTestId('synthetic-badge')).toBeInTheDocument()
    expect(within(detail).getByRole('link', { name: 'Open in complaint browser' })).toHaveAttribute('href', '/complaints?q=2')
    expect(screen.getByTestId('map-stub')).toHaveAttribute('data-selected-complaint', '2')
  })

  it('clicking a marker selects that complaint; a real report is not badged synthetic', async () => {
    serveMapData()
    const { user } = await renderApp('/map?complaint=3', { as: 'analyst' })
    const detail = await screen.findByTestId('selected-complaint')
    expect(detail).toHaveTextContent('Pothole three (real)')
    expect(within(detail).queryByTestId('synthetic-badge')).toBeNull()
    await user.click(screen.getByRole('button', { name: 'stub-click-marker' }))
    expect(screen.getByTestId('map-stub')).toHaveAttribute('data-selected-complaint', '1')
  })

  it('the complaints tab lists the same records the map shows, each marked or not as synthetic', async () => {
    serveMapData()
    const { user } = await renderApp('/map', { as: 'analyst' })
    await stub()
    await user.click(screen.getByRole('tab', { name: /Complaints \(5\)/ }))
    const items = within(screen.getByTestId('complaint-list')).getAllByTestId('complaint-item')
    expect(items).toHaveLength(5)
    expect(items.filter((i) => within(i).queryByTestId('synthetic-badge'))).toHaveLength(3)
  })

  it('tells the user when the basemap cannot load, while data stays plotted', async () => {
    serveMapData()
    const { user } = await renderApp('/map', { as: 'analyst' })
    await stub()
    expect(screen.queryByText('Basemap tiles are unavailable')).toBeNull()
    await user.click(screen.getByRole('button', { name: 'stub-tiles-fail' }))
    expect(screen.getByText('Basemap tiles are unavailable')).toBeInTheDocument()
    expect(screen.getByText(/still plotted at their real coordinates/)).toBeInTheDocument()
  })

  it('shows the error when complaints cannot be loaded', async () => {
    server.use(http.get(`${API}/api/complaints`, () => HttpResponse.json({ detail: { code: 'DB_UNAVAILABLE', message: 'down' } }, { status: 503 })))
    await renderApp('/map', { as: 'analyst' })
    expect(await screen.findByTestId('error-notice')).toHaveAttribute('data-status', '503')
  })
})
