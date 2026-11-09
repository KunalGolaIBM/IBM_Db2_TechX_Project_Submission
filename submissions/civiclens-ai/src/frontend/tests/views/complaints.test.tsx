import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { API, complaint } from '../fixtures'
import { apiError, authed, server } from '../msw'
import { renderApp } from '../render'

const many = Array.from({ length: 25 }, (_, i) =>
  complaint({
    complaint_id: i + 1,
    title: i === 6 ? 'Streetlight out near school' : `Complaint number ${i + 1}`,
    category: i === 6 ? 'STREETLIGHT' : i % 2 ? 'DRAINAGE' : 'POTHOLE',
    severity: (i % 5) + 1,
    is_synthetic: i !== 3,
    reported_at: `2026-11-${String(25 - i).padStart(2, '0')}T10:00:00`,
    ward: `Ward ${(i % 3) + 1}`,
  }),
)
const serve = (rows = many) => server.use(http.get(`${API}/api/complaints`, () => HttpResponse.json(rows)))
const ids = () => screen.getAllByTestId('complaint-row').map((r) => Number(r.getAttribute('data-complaint-id')))

describe('Complaint browsing', () => {
  it('pages through the loaded complaints, 20 at a time, newest first', async () => {
    serve()
    const { user } = await renderApp('/complaints', { as: 'analyst' })
    await screen.findAllByTestId('complaint-row')
    expect(ids()).toHaveLength(20)
    expect(ids()[0]).toBe(1) // reported 25 Nov: the newest
    expect(screen.getByTestId('page-indicator')).toHaveTextContent('Page 1 of 2')
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(ids()).toHaveLength(5)
    expect(screen.getByTestId('page-indicator')).toHaveTextContent('Page 2 of 2')
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
  })

  it('searches titles, and finds a complaint by its ID', async () => {
    serve()
    const { user } = await renderApp('/complaints', { as: 'analyst' })
    await screen.findAllByTestId('complaint-row')
    await user.type(screen.getByTestId('complaint-search'), 'streetlight')
    expect(ids()).toEqual([7])
    expect(screen.getByTestId('complaint-count')).toHaveTextContent('1 of 25 loaded complaints')
    await user.clear(screen.getByTestId('complaint-search'))
    await user.type(screen.getByTestId('complaint-search'), '#12')
    expect(ids()).toEqual([12])
    await user.clear(screen.getByTestId('complaint-search'))
    await user.type(screen.getByTestId('complaint-search'), '2') // a bare number is an ID, not "any title containing 2"
    expect(ids()).toEqual([2])
  })

  it('a search from another page (?q=) is applied on arrival', async () => {
    serve()
    await renderApp('/complaints?q=7', { as: 'analyst' })
    await screen.findAllByTestId('complaint-row')
    expect(ids()).toEqual([7])
  })

  it('filters by category, status, record type and sorts', async () => {
    serve()
    const { user } = await renderApp('/complaints', { as: 'analyst' })
    await screen.findAllByTestId('complaint-row')
    await user.selectOptions(screen.getByLabelText('Category'), 'STREETLIGHT')
    expect(ids()).toEqual([7])
    await user.selectOptions(screen.getByLabelText('Category'), 'all')
    await user.selectOptions(screen.getByLabelText('Record type'), 'real')
    expect(ids()).toEqual([4]) // the only non-synthetic record
    expect(within(screen.getAllByTestId('complaint-row')[0]).getByText('Real report')).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Record type'), 'all')
    await user.selectOptions(screen.getByLabelText('Status'), 'RESOLVED')
    expect(await screen.findByText('No complaints match your filters')).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Status'), 'all')
    await user.selectOptions(screen.getByLabelText('Sort by'), 'severity')
    expect(complaintSeverities()).toEqual([...complaintSeverities()].sort((a, b) => b - a))
  })

  it('marks every synthetic record, on every row', async () => {
    serve()
    await renderApp('/complaints', { as: 'analyst' })
    const rows = await screen.findAllByTestId('complaint-row')
    const synthetic = rows.filter((r) => within(r).queryByTestId('synthetic-badge'))
    expect(synthetic).toHaveLength(19) // 20 on the page, one of which (#4) is real
    expect(screen.getByTestId('synthetic-banner')).toHaveTextContent('24 of 25 complaints are SYNTHETIC')
  })

  it('opens the full record in a dialog, closes with Escape, and returns focus', async () => {
    serve()
    const { user } = await renderApp('/complaints', { as: 'analyst' })
    const title = await screen.findByRole('button', { name: 'Streetlight out near school' })
    await user.click(title)
    const dialog = await screen.findByRole('dialog', { name: 'Complaint #7' })
    expect(within(dialog).getByTestId('complaint-detail')).toHaveTextContent('Streetlight out near school')
    expect(within(dialog).getByRole('link', { name: 'Show on map' })).toHaveAttribute('href', '/map?complaint=7')
    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(title).toHaveFocus()
  })

  it('shows complaint text literally: markup in a title never becomes elements (XSS)', async () => {
    serve([complaint({ complaint_id: 1, title: '<img src=x onerror="window.__pwned=1"> <b>bold</b>', description: '<script>window.__pwned=1</script>' })])
    const { user } = await renderApp('/complaints', { as: 'analyst' })
    const title = await screen.findByRole('button', { name: /<img src=x/ })
    expect(title.textContent).toContain('<b>bold</b>')
    await user.click(title)
    const dialog = await screen.findByRole('dialog')
    expect(dialog.querySelector('img, script, b')).toBeNull()
    expect(dialog).toHaveTextContent('<script>window.__pwned=1</script>')
    expect(document.querySelector('img[src="x"]')).toBeNull()
  })

  it('reviewers can browse but not add complaints', async () => {
    serve()
    await renderApp('/complaints', { as: 'reviewer' })
    await screen.findAllByTestId('complaint-row')
    expect(screen.queryByRole('button', { name: 'Report a complaint' })).toBeNull()
    expect(screen.getByText('Read-only for your role')).toBeInTheDocument()
  })
})

const complaintSeverities = () =>
  screen.getAllByTestId('complaint-row').map((r) => Number(within(r).getByRole('img', { name: /Severity \d of 5/ }).getAttribute('aria-label')!.match(/Severity (\d)/)![1]))

describe('Reporting a complaint (analyst only)', () => {
  const open = async () => {
    serve([complaint({ complaint_id: 1 })])
    const utils = await renderApp('/complaints', { as: 'analyst' })
    await utils.user.click(await screen.findByRole('button', { name: 'Report a complaint' }))
    return { ...utils, dialog: await screen.findByRole('dialog', { name: 'Report a complaint' }) }
  }

  it('validates in the browser first and sends nothing while invalid', async () => {
    let posted = 0
    const { user, dialog } = await open()
    server.use(http.post(`${API}/api/complaints`, authed(() => { posted += 1; return HttpResponse.json({}, { status: 201 }) })))
    await user.click(within(dialog).getByRole('button', { name: 'Create complaint' }))
    expect(within(dialog).getByText(/Title must be at least 3 characters/)).toBeInTheDocument()
    expect(within(dialog).getByText(/Description must be at least 3 characters/)).toBeInTheDocument()
    expect(within(dialog).getByText('Latitude is required.')).toBeInTheDocument()
    expect(within(dialog).getByText('Longitude is required.')).toBeInTheDocument()
    expect(posted).toBe(0)
  })

  it('creates the complaint as SYNTHETIC by default and shows Db2 duplicate candidates', async () => {
    let body: Record<string, unknown> | null = null
    const { user, dialog } = await open()
    server.use(
      http.post(`${API}/api/complaints`, authed(async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(
          {
            complaint: complaint({ complaint_id: 99, title: 'New streetlight fault', geo_cell: 'C5499_15535' }),
            duplicate_candidates: [{ complaint_id: 12, title: 'Streetlight out near school', distance_m: 14.2, text_similarity: 0.6, score: 0.73 }],
          },
          { status: 201 },
        )
      })),
    )
    await user.selectOptions(within(dialog).getByLabelText('Category'), 'STREETLIGHT')
    await user.type(within(dialog).getByLabelText('Title'), 'New streetlight fault')
    await user.type(within(dialog).getByLabelText('Description'), 'Light is out again near the school gate.')
    await user.type(within(dialog).getByLabelText('Latitude'), '27.4964')
    await user.type(within(dialog).getByLabelText('Longitude'), '77.6767')
    expect(within(dialog).getByLabelText('Mark as a synthetic demonstration record')).toBeChecked()
    await user.click(within(dialog).getByRole('button', { name: 'Create complaint' }))

    const created = await within(dialog).findByTestId('complaint-created')
    expect(created).toHaveTextContent('Complaint #99 created')
    expect(created).toHaveTextContent('marked SYNTHETIC')
    const candidates = within(created).getByTestId('duplicate-candidates')
    expect(candidates).toHaveTextContent('#12')
    expect(candidates).toHaveTextContent('14 m away')
    expect(candidates).toHaveTextContent('text similarity 60%')
    expect(body).toEqual({
      category: 'STREETLIGHT', title: 'New streetlight fault', description: 'Light is out again near the school gate.',
      latitude: 27.4964, longitude: 77.6767, ward: null, severity: 3, source: 'DASHBOARD', is_synthetic: true,
    }) // fmt: skip
  })

  it('records a real report when the synthetic box is unticked', async () => {
    let body: Record<string, unknown> | null = null
    const { user, dialog } = await open()
    server.use(
      http.post(`${API}/api/complaints`, authed(async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json({ complaint: complaint({ complaint_id: 100, is_synthetic: false }), duplicate_candidates: [] }, { status: 201 })
      })),
    )
    await user.type(within(dialog).getByLabelText('Title'), 'Real fault')
    await user.type(within(dialog).getByLabelText('Description'), 'A genuine report.')
    await user.type(within(dialog).getByLabelText('Latitude'), '1')
    await user.type(within(dialog).getByLabelText('Longitude'), '2')
    await user.click(within(dialog).getByLabelText('Mark as a synthetic demonstration record'))
    await user.click(within(dialog).getByRole('button', { name: 'Create complaint' }))
    expect(await within(dialog).findByText('No likely duplicates were found.')).toBeInTheDocument()
    expect(body).toMatchObject({ is_synthetic: false })
  })

  it('shows the server error when intake is refused (403) and keeps the form', async () => {
    const { user, dialog } = await open()
    server.use(http.post(`${API}/api/complaints`, authed(() => apiError(403, 'FORBIDDEN', "Role 'analyst' may not do this."))))
    await user.type(within(dialog).getByLabelText('Title'), 'Some fault')
    await user.type(within(dialog).getByLabelText('Description'), 'Some description.')
    await user.type(within(dialog).getByLabelText('Latitude'), '1')
    await user.type(within(dialog).getByLabelText('Longitude'), '2')
    await user.click(within(dialog).getByRole('button', { name: 'Create complaint' }))
    const notice = await within(dialog).findByTestId('error-notice')
    expect(notice).toHaveAttribute('data-status', '403')
    expect(within(dialog).getByLabelText('Title')).toHaveValue('Some fault')
  })
})
