import { apiGet, apiPost, creds, expect, signIn, test, unique } from './fixtures'

interface Audit { action: string; tool_name: string | null; input_json: string | null; actor_id: string }
interface Rec { recommendation_id: number; status: string; generator_type: string; evidence_ids: number[]; model_name: string | null }
interface Evidence { complaint_id: number }

// One investigation travels through the whole workflow; each test continues where the last stopped.
test.describe.serial('investigation workspace: create, attach evidence, run, inspect (real backend + Db2)', () => {
  const title = unique('workflow')
  let id = 0
  let llmConfigured = false
  const open = async (page: import('@playwright/test').Page) => signIn(page, creds.analyst, `/investigations/${id}`)

  test('an analyst creates an investigation (validated first), and Db2 stores it', async ({ page }) => {
    await signIn(page, creds.analyst, '/investigations')
    llmConfigured = (await apiGet<{ system: { llm: { configured: boolean } } }>(page.request, creds.analyst, '/api/overview')).system.llm.configured
    await page.getByRole('button', { name: 'New investigation' }).click()
    const dialog = page.getByRole('dialog', { name: 'New investigation' })
    await dialog.getByRole('button', { name: 'Create investigation' }).click()
    await expect(dialog.getByText(/Title must be at least 3 characters/)).toBeVisible()
    await dialog.getByLabel('Title').fill(title)
    await dialog.getByLabel('Question').fill('Which pothole clusters need a repair crew first?')
    await dialog.getByRole('button', { name: 'Create investigation' }).click()

    await expect(page).toHaveURL(/\/investigations\/\d+$/)
    id = Number(page.url().split('/').pop())
    await expect(page.getByTestId('investigation-title')).toHaveText(title)
    await expect(page.getByTestId('investigation-status')).toHaveAttribute('data-status', 'OPEN')
    const stored = await apiGet<{ title: string; status: string; created_by: string }>(page.request, creds.analyst, `/api/investigations/${id}`)
    expect(stored).toMatchObject({ title, status: 'OPEN', created_by: creds.analyst.id })
  })

  test('evidence is attached from the picker and by ID; an unknown ID is refused by the server (422)', async ({ page }) => {
    await open(page)
    await page.getByRole('button', { name: 'Attach evidence' }).click()
    const dialog = page.getByRole('dialog', { name: 'Attach evidence' })
    const boxes = dialog.locator('[data-testid=picker-checkbox]:not([disabled])')
    await expect(boxes.first()).toBeVisible()
    const picked = [Number(await boxes.nth(0).getAttribute('data-complaint-id')), Number(await boxes.nth(1).getAttribute('data-complaint-id'))]
    await boxes.nth(0).check()
    await boxes.nth(1).check()
    await dialog.getByRole('button', { name: 'Attach 2 selected' }).click()
    await expect(page.getByText('Attached 2 complaints as evidence.')).toBeVisible()
    await expect(page.getByTestId('evidence-row')).toHaveCount(2)
    for (const complaintId of picked) await expect(page.locator(`[data-testid=evidence-row][data-complaint-id="${complaintId}"]`)).toBeVisible()

    // a complaint ID that does not exist: the server's real 422 is shown, naming the ID, and nothing is saved
    await page.getByLabel('Attach by complaint ID').fill('999999999')
    await page.getByRole('button', { name: 'Attach', exact: true }).click()
    const notice = page.getByTestId('error-notice')
    await expect(notice).toBeVisible()
    await expect(notice).toHaveAttribute('data-status', '422')
    await expect(notice).toHaveAttribute('data-code', 'UNKNOWN_COMPLAINT_IDS')
    await expect(notice).toContainText('Complaint #999999999')
    await expect(page.getByTestId('evidence-row')).toHaveCount(2)

    // and by ID with a real complaint
    const all = await apiGet<Array<{ complaint_id: number }>>(page.request, creds.analyst, '/api/complaints?limit=200')
    const extra = all.find((c) => !picked.includes(c.complaint_id))!.complaint_id
    await page.getByLabel('Attach by complaint ID').fill(String(extra))
    await page.getByRole('button', { name: 'Attach', exact: true }).click()
    await expect(page.getByTestId('evidence-row')).toHaveCount(3)

    const stored = await apiGet<Evidence[]>(page.request, creds.analyst, `/api/investigations/${id}/evidence`)
    expect(stored.map((e) => e.complaint_id).sort()).toEqual([...picked, extra].sort())
  })

  test('LLM-only mode is refused (409) when no model is configured, and nothing is consumed', async ({ page }) => {
    test.skip(llmConfigured, 'a language model is configured on this server')
    await open(page)
    await page.getByLabel(/LLM only/).check()
    await expect(page.getByText(/LLM-only mode will be refused with LLM_NOT_CONFIGURED/)).toBeVisible()
    await page.getByRole('button', { name: 'Run investigation' }).click()
    const notice = page.getByTestId('error-notice')
    await expect(notice).toHaveAttribute('data-status', '409')
    await expect(notice).toHaveAttribute('data-code', 'LLM_NOT_CONFIGURED')
    await expect(page.getByTestId('run-result')).toHaveCount(0)
    await expect(page.getByTestId('investigation-status')).toHaveAttribute('data-status', 'OPEN')
  })

  test('the rule-based run is labelled as rule-based and proposes recommendations grounded in the evidence', async ({ page }) => {
    await open(page)
    await page.getByLabel(/Rule-based only/).check()
    await page.getByLabel('Look-back window (days)').fill('365')
    await page.getByRole('button', { name: 'Run investigation' }).click()

    const result = page.getByTestId('run-result')
    await expect(result).toBeVisible()
    await expect(result.getByTestId('generator-badge')).toHaveText('Rule-based · no LLM')
    await expect(result.getByTestId('run-notice')).toContainText('NO LLM WAS USED')
    await expect(result.getByTestId('run-result-status')).toHaveAttribute('data-status', 'PENDING_REVIEW')
    await expect(result).not.toContainText('AI model (LLM)')
    await expect(page.getByTestId('investigation-status')).toHaveAttribute('data-status', 'PENDING_REVIEW')

    const cards = page.getByTestId('recommendations-card').getByTestId('recommendation')
    await expect(cards.first()).toBeVisible()
    const stored = await apiGet<Rec[]>(page.request, creds.analyst, `/api/investigations/${id}/recommendations`)
    expect(stored.length).toBeGreaterThan(0)
    await expect(cards).toHaveCount(stored.length)
    for (const rec of stored) {
      expect(rec).toMatchObject({ status: 'PROPOSED', generator_type: 'DETERMINISTIC_FALLBACK' })
      const card = page.locator(`[data-testid=recommendation][data-recommendation-id="${rec.recommendation_id}"]`)
      await expect(card.getByTestId('generator-badge')).toHaveText('Rule-based · no LLM')
      await expect(card).not.toContainText('AI model')
      await expect(card.getByTestId('recommendation-rationale')).toContainText('[RULE-BASED, NO LLM]')
      await expect(card.getByTestId('evidence-ids').getByRole('listitem')).toHaveCount(rec.evidence_ids.length)
    }
    // every cited complaint is attached evidence in Db2 (the agent can only cite what it retrieved)
    const evidence = (await apiGet<Evidence[]>(page.request, creds.analyst, `/api/investigations/${id}/evidence`)).map((e) => e.complaint_id)
    for (const rec of stored) for (const cited of rec.evidence_ids) expect(evidence).toContain(cited)
  })

  test('the audit history lists each tool call and who issued them, and matches the database', async ({ page }) => {
    await open(page)
    const audit = await apiGet<Audit[]>(page.request, creds.analyst, `/api/investigations/${id}/audit`)
    const toolCalls = audit.filter((a) => a.action === 'TOOL_CALL')
    expect(toolCalls.length).toBeGreaterThan(0)
    await expect(page.getByTestId('audit-entry')).toHaveCount(audit.length)
    await expect(page.getByTestId('audit-summary')).toContainText(`${audit.length} audit entries · ${toolCalls.length} tool ${toolCalls.length === 1 ? 'call' : 'calls'}`)
    expect(audit.map((a) => a.tool_name)).toContain('hotspot_summary')

    const origin = page.getByTestId('tool-activity-origin')
    await expect(origin).toContainText('Rule-based · no LLM')
    await expect(origin).toContainText('not made by a language model')

    await page.getByLabel('Tool activity only').check()
    await expect(page.getByTestId('audit-entry')).toHaveCount(toolCalls.length)
    const shown = await page.getByTestId('audit-entry').evaluateAll((els) => els.map((e) => e.getAttribute('data-tool')))
    expect(shown).toEqual(toolCalls.map((t) => t.tool_name))
    // the actors in the log are the real ones
    expect(audit.find((a) => a.action === 'INVESTIGATION_CREATED')!.actor_id).toBe(creds.analyst.id)
  })

  test('an analyst can propose a manual recommendation, which is labelled manual (not AI, not rules)', async ({ page }) => {
    await open(page)
    await page.getByRole('button', { name: 'Propose manually' }).click()
    const dialog = page.getByRole('dialog', { name: 'Propose a recommendation' })
    await dialog.getByRole('button', { name: 'Propose' }).click()
    await expect(dialog.getByText('Select at least one piece of attached evidence.')).toBeVisible() // validated first
    await dialog.getByLabel('Summary').fill('Inspect the junction drain before the monsoon')
    await dialog.getByLabel('Explanation').fill('Written by an analyst from the cited complaints; no automated analysis was used.')
    await dialog.getByLabel('Priority').selectOption('2')
    await dialog.getByRole('checkbox').first().check()
    await dialog.getByRole('button', { name: 'Propose' }).click()
    await expect(page.getByText('Manual recommendation proposed. It is awaiting review.')).toBeVisible()

    const manual = page.locator('[data-testid=recommendation][data-generator=MANUAL]')
    await expect(manual).toHaveCount(1)
    await expect(manual.getByTestId('generator-badge')).toHaveText('Manual · analyst-written')
    await expect(manual).not.toContainText('Rule-based')
    const stored = await apiGet<Rec[]>(page.request, creds.analyst, `/api/investigations/${id}/recommendations`)
    expect(stored.filter((r) => r.generator_type === 'MANUAL')).toHaveLength(1)
  })

  test('the investigation shows in the list and is counted on the overview', async ({ page }) => {
    await signIn(page, creds.analyst, '/investigations')
    await expect(page.locator(`[data-testid=investigation-row][data-investigation-id="${id}"]`)).toContainText(title)
    await expect(page.locator(`[data-testid=investigation-row][data-investigation-id="${id}"]`).getByTestId('investigation-status')).toHaveAttribute('data-status', 'PENDING_REVIEW')
    await page.getByRole('link', { name: 'Intelligence overview' }).click()
    const o = await apiGet<{ investigations: { active: number }; recommendations: { pending_review: number } }>(page.request, creds.analyst, '/api/overview')
    await expect(page.getByTestId('kpi-investigations-value')).toHaveText(String(o.investigations.active))
    await expect(page.getByTestId('kpi-pending-value')).toHaveText(String(o.recommendations.pending_review))
  })
})

// "Auto" is what the run form selects by default, so it is the path most users take: it must stay honest when no model exists.
test('Auto mode, with no language model configured, falls back to the labelled rule-based run and says why', async ({ page, request }) => {
  const overview = await apiGet<{ system: { llm: { configured: boolean } } }>(request, creds.analyst, '/api/overview')
  test.skip(overview.system.llm.configured, 'a language model is configured on this server')
  const inv = await apiPost<{ investigation_id: number }>(request, creds.analyst, '/api/investigations', {
    title: unique('auto mode'),
    question: 'Does Auto mode stay honest when no language model is configured?',
  })
  await signIn(page, creds.analyst, `/investigations/${inv.investigation_id}`)
  await expect(page.getByLabel(/^Auto/)).toBeChecked() // the default
  await expect(page.getByText('No language model is configured on this server')).toBeVisible() // said before running, not after
  await page.getByRole('button', { name: 'Run investigation' }).click()

  const result = page.getByTestId('run-result')
  await expect(result).toBeVisible()
  await expect(result.getByTestId('generator-badge')).toHaveText('Rule-based · no LLM')
  await expect(result.getByTestId('run-notice')).toContainText('NO LLM WAS USED')
  await expect(result.getByTestId('fallback-reason')).toContainText('Why the fallback was used')
  await expect(result).not.toContainText('AI model (LLM)')
  await expect(page.getByTestId('audit-card')).toContainText(/mode\s*auto/) // the audit trail records what was asked for

  // what Db2 stored agrees with what the screen said
  const stored = await apiGet<Rec[]>(request, creds.analyst, `/api/investigations/${inv.investigation_id}/recommendations`)
  expect(stored.length).toBeGreaterThan(0)
  for (const rec of stored) expect(rec).toMatchObject({ generator_type: 'DETERMINISTIC_FALLBACK', status: 'PROPOSED' })
})
