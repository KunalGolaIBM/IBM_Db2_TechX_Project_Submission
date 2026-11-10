import type { Category, ComplaintStatus, GeneratorType, InvestigationStatus, RecommendationStatus } from '../lib/domain'
import { apiRequest } from './client'
import {
  auditEntrySchema,
  complaintCreatedSchema,
  complaintSchema,
  evidenceItemSchema,
  hotspotSchema,
  investigationSchema,
  listOf,
  meSchema,
  overviewSchema,
  recommendationListItemSchema,
  recommendationSchema,
  runResultSchema,
  type ComplaintCreateInput,
  type DecisionInput,
  type EvidenceCreateInput,
  type InvestigationCreateInput,
  type RecommendationDraftInput,
  type RunRequestInput,
} from './schemas'

export interface ComplaintFilters {
  category?: Category
  status?: ComplaintStatus
  ward?: string
  synthetic?: boolean
  limit?: number
}
export interface HotspotFilters {
  days: number
  minCount: number
  category?: Category
  limit?: number
}
export interface QueueFilters {
  status?: RecommendationStatus
  generator?: GeneratorType
  investigationId?: number
  limit?: number
}

/** The LLM-backed run can legitimately take a while (bounded server-side by AGENT_TIMEOUT_S). */
const RUN_TIMEOUT_MS = 180_000

export const endpoints = {
  me: (token?: string | null, signal?: AbortSignal) => apiRequest('/api/me', { schema: meSchema, token, signal }),
  overview: (signal?: AbortSignal) => apiRequest('/api/overview', { schema: overviewSchema, signal }),

  complaints: (f: ComplaintFilters = {}, signal?: AbortSignal) =>
    apiRequest('/api/complaints', {
      schema: listOf(complaintSchema),
      query: { category: f.category, status: f.status, ward: f.ward, synthetic: f.synthetic, limit: f.limit ?? 200 },
      signal,
    }),
  createComplaint: (body: ComplaintCreateInput) =>
    apiRequest('/api/complaints', { method: 'POST', body, schema: complaintCreatedSchema }),
  hotspots: (f: HotspotFilters, signal?: AbortSignal) =>
    apiRequest('/api/hotspots', {
      schema: listOf(hotspotSchema),
      query: { days: f.days, min_count: f.minCount, category: f.category, limit: f.limit ?? 100 },
      signal,
    }),

  investigations: (status?: InvestigationStatus, signal?: AbortSignal) =>
    apiRequest('/api/investigations', { schema: listOf(investigationSchema), query: { status, limit: 100 }, signal }),
  investigation: (id: number, signal?: AbortSignal) =>
    apiRequest(`/api/investigations/${id}`, { schema: investigationSchema, signal }),
  createInvestigation: (body: InvestigationCreateInput) =>
    apiRequest('/api/investigations', { method: 'POST', body, schema: investigationSchema }),
  evidence: (id: number, signal?: AbortSignal) =>
    apiRequest(`/api/investigations/${id}/evidence`, { schema: listOf(evidenceItemSchema), signal }),
  attachEvidence: (id: number, body: EvidenceCreateInput) =>
    apiRequest(`/api/investigations/${id}/evidence`, { method: 'POST', body, schema: listOf(evidenceItemSchema) }),
  audit: (id: number, signal?: AbortSignal) =>
    apiRequest(`/api/investigations/${id}/audit`, { schema: listOf(auditEntrySchema), query: { limit: 500 }, signal }),
  investigationRecommendations: (id: number, signal?: AbortSignal) =>
    apiRequest(`/api/investigations/${id}/recommendations`, { schema: listOf(recommendationSchema), signal }),
  proposeRecommendation: (id: number, body: RecommendationDraftInput) =>
    apiRequest(`/api/investigations/${id}/recommendations`, { method: 'POST', body, schema: recommendationSchema }),
  run: (id: number, body: RunRequestInput) =>
    apiRequest(`/api/investigations/${id}/run`, {
      method: 'POST',
      body,
      schema: runResultSchema,
      timeoutMs: RUN_TIMEOUT_MS,
    }),

  recommendations: (f: QueueFilters = {}, signal?: AbortSignal) =>
    apiRequest('/api/recommendations', {
      schema: listOf(recommendationListItemSchema),
      query: { status: f.status, generator: f.generator, investigation_id: f.investigationId, limit: f.limit ?? 100 },
      signal,
    }),
  decide: (recommendationId: number, body: DecisionInput) =>
    apiRequest(`/api/recommendations/${recommendationId}/decision`, {
      method: 'POST',
      body,
      schema: recommendationSchema,
    }),
}
