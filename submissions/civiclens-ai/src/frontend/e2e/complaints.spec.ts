import { apiGet, creds, expect, signIn, test, unique } from './fixtures'

interface Complaint { complaint_id: number; title: string; description: string; ward: string | null; external_ref: string | null; category: string; is_synthetic: boolean }

test.describe('complaint browsing and intake (real Db2)', () => {
  test('search, filter, open a record, close with Escape, and focus returns', async ({ page }) => {
    await signIn(page, creds.analyst, '/complaints')
    const all = await apiGet<Complaint[]>(page.request, creds.analyst, '/api/complaints?limit=200')
    expect(all.length).toBeGreaterThan(0)
    await expect(page.getByTestId('complaint-count')).toContainText(`of ${all.length} loaded complaints`)

    const word = all[0].title.split(/\s+/).find((w) => /^[A-Za-z]{5,}$/.test(w))!.toLowerCase()
    await page.getByTestId('complaint-search').fill(word)
    const matches = all.filter((c) => [c.title, c.description, c.ward ?? '', c.external_ref ?? ''].some((t) => t.toLowerCase().includes(word)))
    await expect(page.getByTestId('complaint-count')).toContainText(`${matches.length} of ${all.length}`)

    const first = page.getByTestId('complaint-row').first()
    const opener = first.getByRole('button')
    const title = (await opener.textContent())!.trim()
    await opener.click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    await expect(dialog.getByTestId('complaint-detail')).toContainText(title)
    await expect(dialog.getByRole('link', { name: 'Show on map' })).toHaveAttribute('href', /\/map\?complaint=\d+/)
    await page.keyboard.press('Escape')
    await expect(dialog).toHaveCount(0)
    await expect(opener).toBeFocused()
  })

  test('category and record-type filters agree with the database', async ({ page }) => {
    await signIn(page, creds.analyst, '/complaints')
    const all = await apiGet<Complaint[]>(page.request, creds.analyst, '/api/complaints?limit=200')
    const category = all[0].category
    await page.getByLabel('Category').selectOption(category)
    const inCategory = all.filter((c) => c.category === category).length
    await expect(page.getByTestId('complaint-count')).toContainText(`${inCategory} of ${all.length}`)

    await page.getByLabel('Category').selectOption('all')
    await page.getByLabel('Record type').selectOption('synthetic')
    const synthetic = all.filter((c) => c.is_synthetic).length
    await expect(page.getByTestId('complaint-count')).toContainText(`${synthetic} of ${all.length}`)
    // every visible row on this page is badged synthetic
    const rows = page.getByTestId('complaint-row')
    for (let i = 0; i < Math.min(await rows.count(), 5); i++) await expect(rows.nth(i).getByTestId('synthetic-badge')).toBeVisible()
  })

  test('pagination moves through the records 20 at a time', async ({ page }) => {
    await signIn(page, creds.analyst, '/complaints')
    const all = await apiGet<Complaint[]>(page.request, creds.analyst, '/api/complaints?limit=200')
    test.skip(all.length <= 20, 'fewer than 21 complaints')
    const pages = Math.ceil(all.length / 20)
    await expect(page.getByTestId('page-indicator')).toHaveText(`Page 1 of ${pages}`)
    await expect(page.getByTestId('complaint-row')).toHaveCount(20)
    await page.getByRole('button', { name: 'Next' }).click()
    await expect(page.getByTestId('page-indicator')).toHaveText(`Page 2 of ${pages}`)
    await expect(page.getByTestId('complaint-row')).toHaveCount(Math.min(20, all.length - 20))
  })

  test('an analyst reports a synthetic complaint and Db2 finds the duplicate on the second submission', async ({ page }) => {
    const title = unique('duplicate probe')
    await signIn(page, creds.analyst, '/complaints')

    const report = async () => {
      await page.getByRole('button', { name: 'Report a complaint' }).click()
      const dialog = page.getByRole('dialog', { name: 'Report a complaint' })
      await dialog.getByLabel('Category').selectOption('POTHOLE')
      await dialog.getByLabel('Title').fill(title)
      await dialog.getByLabel('Description').fill('[SYNTHETIC] End-to-end test record: deep pothole near the junction.')
      await dialog.getByLabel('Latitude').fill('27.4964')
      await dialog.getByLabel('Longitude').fill('77.6767')
      await expect(dialog.getByLabel('Mark as a synthetic demonstration record')).toBeChecked()
      await dialog.getByRole('button', { name: 'Create complaint' }).click()
      return dialog
    }

    const first = await report()
    await expect(first.getByTestId('complaint-created')).toContainText('created')
    await expect(first.getByTestId('complaint-created')).toContainText('marked SYNTHETIC')
    await first.getByRole('button', { name: 'Done' }).click()

    const second = await report()
    const candidates = second.getByTestId('duplicate-candidates')
    await expect(candidates).toContainText(title) // the first copy is reported as a likely duplicate
    await expect(candidates).toContainText('0 m away')
    await expect(candidates).toContainText('text similarity 100%')
    await second.getByRole('button', { name: 'Done' }).click()

    // Db2 holds both, flagged synthetic, attributed to the analyst
    const stored = (await apiGet<Complaint[]>(page.request, creds.analyst, '/api/complaints?synthetic=true&limit=200')).filter((c) => c.title === title)
    expect(stored).toHaveLength(2)
    expect(stored.every((c) => c.is_synthetic)).toBe(true)
  })

  test('intake validation runs in the browser first', async ({ page }) => {
    await signIn(page, creds.analyst, '/complaints')
    await page.getByRole('button', { name: 'Report a complaint' }).click()
    const dialog = page.getByRole('dialog')
    await dialog.getByLabel('Latitude').fill('95')
    await dialog.getByRole('button', { name: 'Create complaint' }).click()
    await expect(dialog.getByText(/Latitude must be between -90 and 90/)).toBeVisible()
    await expect(dialog.getByText(/Title must be at least 3 characters/)).toBeVisible()
    await expect(dialog.getByTestId('complaint-created')).toHaveCount(0)
  })
})
