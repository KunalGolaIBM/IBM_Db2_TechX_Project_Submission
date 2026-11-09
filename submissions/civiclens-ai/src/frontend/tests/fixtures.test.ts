import { describe, expect, it } from 'vitest'
import {
  auditEntrySchema,
  complaintSchema,
  evidenceItemSchema,
  hotspotSchema,
  investigationSchema,
  meSchema,
  overviewSchema,
  recommendationListItemSchema,
  recommendationSchema,
  runResultSchema,
} from '../src/api/schemas'
import { analyst, auditEntry, complaint, evidenceItem, hotspot, investigation, overview, queueItem, recommendation, reviewer, runResult } from './fixtures'

// The fixtures feed every component test, so they must satisfy the SAME schemas the live backend is
// validated against in tests/live: otherwise the mock-based tests could pass on shapes the API never returns.
describe('test fixtures conform to the API contract schemas', () => {
  it.each([
    ['me (analyst)', meSchema, analyst],
    ['me (reviewer)', meSchema, reviewer],
    ['complaint', complaintSchema, complaint()],
    ['hotspot', hotspotSchema, hotspot()],
    ['investigation', investigationSchema, investigation()],
    ['evidence', evidenceItemSchema, evidenceItem()],
    ['recommendation', recommendationSchema, recommendation()],
    ['queue item', recommendationListItemSchema, queueItem()],
    ['audit entry', auditEntrySchema, auditEntry()],
    ['run result', runResultSchema, runResult()],
    ['overview', overviewSchema, overview()],
  ])('%s', (_name, schema, value) => {
    expect(schema.safeParse(value).success).toBe(true)
  })

  it('a malformed value is rejected (the schemas are not vacuous)', () => {
    expect(complaintSchema.safeParse({ ...complaint(), severity: 'high' }).success).toBe(false)
    expect(recommendationSchema.safeParse({ ...recommendation(), generator_type: 'GPT' }).success).toBe(false)
    expect(overviewSchema.safeParse({ ...overview(), system: undefined }).success).toBe(false)
  })
})
