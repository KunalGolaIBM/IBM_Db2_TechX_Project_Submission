import { apiGet, creds, expect, signIn, test, TILE_URL } from './fixtures'

interface Complaint { complaint_id: number; category: string; is_synthetic: boolean; title: string }
interface Hotspot { geo_cell: string; category: string; complaint_count: number }

test.describe('geographic intelligence (real Leaflet, real complaints from Db2)', () => {
  test('one marker per complaint, synthetic ones ringed with a dashed outline', async ({ page }) => {
    await signIn(page, creds.analyst, '/map')
    const complaints = await apiGet<Complaint[]>(page.request, creds.analyst, '/api/complaints?limit=200')
    expect(complaints.length).toBeGreaterThan(0)
    const synthetic = complaints.filter((c) => c.is_synthetic).length

    await expect(page.getByTestId('map')).toHaveAttribute('data-marker-count', String(complaints.length))
    await expect(page.locator('path.cl-marker')).toHaveCount(complaints.length)
    await expect(page.locator('path.cl-marker[data-synthetic="true"]')).toHaveCount(synthetic)
    if (synthetic > 0) {
      const dash = await page.locator('path.cl-marker[data-synthetic="true"]').first().getAttribute('stroke-dasharray')
      expect(dash).toMatch(/^2[ ,]3$/) // dashed ring = synthetic
    }
    if (synthetic < complaints.length) {
      expect(await page.locator('path.cl-marker[data-synthetic="false"]').first().getAttribute('stroke-dasharray')).toBeNull()
    }
    await expect(page.getByTestId('legend-synthetic')).toContainText(`(${synthetic})`)
    await expect(page.getByTestId('legend-real')).toContainText(`(${complaints.length - synthetic})`)
    await expect(page.getByTestId('synthetic-banner')).toBeVisible()
  })

  test('hotspot cells are the grid rectangles Db2 aggregated, with their counts', async ({ page }) => {
    await signIn(page, creds.analyst, '/map')
    const spots = await apiGet<Hotspot[]>(page.request, creds.analyst, '/api/hotspots?days=30&min_count=3&limit=100')
    expect(spots.length, 'the demo data should contain hotspots').toBeGreaterThan(0)
    await expect(page.getByTestId('map')).toHaveAttribute('data-hotspot-count', String(spots.length))
    await expect(page.locator('path.cl-hotspot')).toHaveCount(spots.length)
    const labels = await page.locator('.cl-hotspot-count').allTextContents()
    expect(labels.map(Number).sort((a, b) => a - b)).toEqual(spots.map((s) => s.complaint_count).sort((a, b) => a - b))
    await expect(page.getByTestId('hotspot-item')).toHaveCount(spots.length)
  })

  test('the category filter narrows the markers, hotspots and lists together', async ({ page }) => {
    await signIn(page, creds.analyst, '/map')
    const complaints = await apiGet<Complaint[]>(page.request, creds.analyst, '/api/complaints?limit=200')
    const spots = await apiGet<Hotspot[]>(page.request, creds.analyst, '/api/hotspots?days=30&min_count=3&limit=100')
    const category = spots[0].category // a category that has a hotspot
    const label = category[0] + category.slice(1).toLowerCase().replace(/_/g, ' ')
    const group = page.getByRole('group', { name: 'Filter by category' })

    await group.getByRole('button', { name: new RegExp(`^${label}`) }).click()
    const expectedComplaints = complaints.filter((c) => c.category === category).length
    const expectedSpots = spots.filter((s) => s.category === category).length
    await expect(page.getByTestId('map')).toHaveAttribute('data-marker-count', String(expectedComplaints))
    await expect(page.getByTestId('map')).toHaveAttribute('data-hotspot-count', String(expectedSpots))
    await expect(page.locator('path.cl-marker')).toHaveCount(expectedComplaints)
    await expect(page.getByTestId('map-count')).toContainText(
      `Showing ${expectedComplaints} ${expectedComplaints === 1 ? 'complaint' : 'complaints'} and ${expectedSpots} ${expectedSpots === 1 ? 'hotspot' : 'hotspots'}`,
    )

    await group.getByRole('button', { name: 'All' }).click()
    await expect(page.locator('path.cl-marker')).toHaveCount(complaints.length)
  })

  test('selecting a hotspot highlights its cell; a marker opens the complaint behind it', async ({ page }) => {
    await signIn(page, creds.analyst, '/map')
    const complaints = await apiGet<Complaint[]>(page.request, creds.analyst, '/api/complaints?limit=200')
    await expect(page.locator('path.cl-hotspot').first()).toBeVisible()

    await page.getByTestId('hotspot-item').first().click()
    await expect(page.getByTestId('hotspot-item').first()).toHaveAttribute('aria-pressed', 'true')
    await expect(page.locator('path.cl-hotspot[stroke-width="3"]')).toHaveCount(1) // the selected cell is drawn heavier

    const marker = page.locator('path.cl-marker').filter({ visible: true }).first()
    const id = Number(await marker.getAttribute('data-complaint-id'))
    await marker.dispatchEvent('click')
    const detail = page.getByTestId('selected-complaint')
    await expect(detail).toBeVisible()
    await expect(detail).toContainText(complaints.find((c) => c.complaint_id === id)!.title)
    await expect(detail).toContainText(`#${id}`)
  })

  test('a deep link from the overview lands on the right hotspot', async ({ page }) => {
    await signIn(page, creds.analyst)
    await page.getByTestId('hotspot-row').first().getByRole('link').click()
    await expect(page).toHaveURL(/\/map\?hotspot=/)
    await expect(page.getByTestId('hotspot-item').first()).toHaveAttribute('aria-pressed', 'true')
  })

  test('the hotspot window and minimum cluster re-query Db2', async ({ page }) => {
    await signIn(page, creds.analyst, '/map')
    const loose = await apiGet<Hotspot[]>(page.request, creds.analyst, '/api/hotspots?days=365&min_count=2&limit=100')
    await page.getByLabel('Hotspot window').selectOption('365')
    await page.getByLabel('Min. cluster').selectOption('2')
    await expect(page.getByTestId('map')).toHaveAttribute('data-hotspot-count', String(loose.length))
  })

  test('if the basemap cannot load, the user is told and the data is still plotted', async ({ page }) => {
    await page.route(TILE_URL, (route) => route.abort()) // overrides the fixture's stub
    await signIn(page, creds.analyst, '/map')
    await expect(page.getByText('Basemap tiles are unavailable')).toBeVisible()
    // markers inside the viewport (a stray far-away record is outside the initial view, by design)
    await expect(page.locator('path.cl-marker').filter({ visible: true }).first()).toBeVisible()
  })

  test('zoom controls and keyboard-reachable lists are present (the map has a text alternative)', async ({ page }) => {
    await signIn(page, creds.analyst, '/map')
    await expect(page.getByRole('button', { name: 'Zoom in' })).toBeVisible()
    await expect(page.getByTestId('map')).toHaveAttribute('role', 'region')
    await page.getByRole('tab', { name: /Complaints \(/ }).click()
    await expect(page.getByTestId('complaint-item').first()).toBeVisible()
    await page.getByTestId('complaint-item').first().focus()
    await expect(page.getByTestId('complaint-item').first()).toBeFocused()
  })
})
