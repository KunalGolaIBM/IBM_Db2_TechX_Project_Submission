/**
 * Runtime schemas for every API response. They mirror the FastAPI models, and the live contract test
 * (tests/live) runs them against the real backend, so a drifting server fails loudly instead of rendering
 * wrong numbers. Unknown extra fields are ignored; missing or mistyped ones are errors.
 */
import { z } from 'zod'
import {
  CATEGORIES,
  COMPLAINT_STATUSES,
  GENERATOR_TYPES,
  INVESTIGATION_STATUSES,
  RECOMMENDATION_STATUSES,
} from '../lib/domain'

const ts = z.string() // naive-UTC ISO timestamp from the server
const id = z.number().int()

export const categorySchema = z.enum(CATEGORIES)
export const complaintStatusSchema = z.enum(COMPLAINT_STATUSES)
export const investigationStatusSchema = z.enum(INVESTIGATION_STATUSES)
export const recommendationStatusSchema = z.enum(RECOMMENDATION_STATUSES)
export const generatorTypeSchema = z.enum(GENERATOR_TYPES)

export const meSchema = z.object({
  user_id: z.string(),
  role: z.enum(['analyst', 'reviewer']),
  capabilities: z.array(z.string()),
})
export type Me = z.infer<typeof meSchema>

export const complaintSchema = z.object({
  complaint_id: id,
  external_ref: z.string().nullable(),
  category: categorySchema,
  title: z.string(),
  description: z.string(),
  latitude: z.number(),
  longitude: z.number(),
  geo_cell: z.string(),
  ward: z.string().nullable(),
  severity: z.number().int(),
  status: complaintStatusSchema,
  source: z.string(),
  duplicate_of: id.nullable(),
  is_synthetic: z.boolean(),
  reported_at: ts,
  created_at: ts,
})
export type Complaint = z.infer<typeof complaintSchema>

export const duplicateCandidateSchema = z.object({
  complaint_id: id,
  title: z.string(),
  distance_m: z.number(),
  text_similarity: z.number(),
  score: z.number(),
})
export const complaintCreatedSchema = z.object({
  complaint: complaintSchema,
  duplicate_candidates: z.array(duplicateCandidateSchema),
})
export type ComplaintCreated = z.infer<typeof complaintCreatedSchema>

export const hotspotSchema = z.object({
  geo_cell: z.string(),
  category: categorySchema,
  complaint_count: z.number().int(),
  avg_severity: z.number(),
  center_latitude: z.number(),
  center_longitude: z.number(),
  first_reported_at: ts,
  last_reported_at: ts,
})
export type Hotspot = z.infer<typeof hotspotSchema>

export const investigationSchema = z.object({
  investigation_id: id,
  title: z.string(),
  question: z.string(),
  status: investigationStatusSchema,
  created_by: z.string(),
  created_at: ts,
  closed_at: ts.nullable(),
})
export type Investigation = z.infer<typeof investigationSchema>

export const evidenceItemSchema = z.object({
  investigation_id: id,
  complaint_id: id,
  relevance: z.number(),
  note: z.string().nullable(),
  added_at: ts,
  title: z.string(),
  category: categorySchema,
  geo_cell: z.string(),
  severity: z.number().int(),
  reported_at: ts,
  is_synthetic: z.boolean(),
})
export type EvidenceItem = z.infer<typeof evidenceItemSchema>

export const reviewDecisionSchema = z.object({
  decision_id: id,
  recommendation_id: id,
  reviewer: z.string(),
  decision: z.enum(['APPROVED', 'REJECTED', 'NEEDS_INFO']),
  comment: z.string().nullable(),
  decided_at: ts,
})
export type ReviewDecision = z.infer<typeof reviewDecisionSchema>

export const recommendationSchema = z.object({
  recommendation_id: id,
  investigation_id: id,
  summary: z.string(),
  rationale: z.string(),
  priority: z.number().int(),
  confidence: z.number(),
  evidence_ids: z.array(id),
  generator_type: generatorTypeSchema,
  model_name: z.string().nullable(),
  status: recommendationStatusSchema,
  created_at: ts,
  review: reviewDecisionSchema.nullable(),
})
export type Recommendation = z.infer<typeof recommendationSchema>

export const recommendationListItemSchema = recommendationSchema.extend({
  investigation_title: z.string(),
  investigation_status: investigationStatusSchema,
  investigation_created_by: z.string(),
})
export type RecommendationListItem = z.infer<typeof recommendationListItemSchema>

export const auditEntrySchema = z.object({
  audit_id: id,
  actor_type: z.string(),
  actor_id: z.string(),
  action: z.string(),
  tool_name: z.string().nullable(),
  input_json: z.string().nullable(),
  output_summary: z.string().nullable(),
  success: z.boolean(),
  created_at: ts,
})
export type AuditEntry = z.infer<typeof auditEntrySchema>

export const runResultSchema = z.object({
  investigation_id: id,
  status: investigationStatusSchema,
  generator: generatorTypeSchema,
  model_name: z.string().nullable(),
  llm_configured: z.boolean(),
  fallback_reason: z.string().nullable(),
  steps: z.number().int(),
  tool_calls: z.number().int(),
  recommendation_ids: z.array(id),
  notice: z.string(),
})
export type RunResult = z.infer<typeof runResultSchema>

export const overviewSchema = z.object({
  generated_at: ts,
  complaints: z.object({
    total: z.number().int(),
    synthetic: z.number().int(),
    real: z.number().int(),
    last_7d: z.number().int(),
    last_30d: z.number().int(),
    by_category: z.array(
      z.object({ category: categorySchema, count: z.number().int(), avg_severity: z.number(), synthetic: z.number().int() }),
    ),
    by_status: z.array(z.object({ status: complaintStatusSchema, count: z.number().int() })),
    by_severity: z.array(z.object({ severity: z.number().int(), count: z.number().int() })),
    trend_days: z.number().int(),
    trend: z.array(z.object({ date: z.string(), count: z.number().int() })),
  }),
  investigations: z.object({
    total: z.number().int(),
    active: z.number().int(),
    by_status: z.record(z.string(), z.number().int()),
  }),
  recommendations: z.object({
    total: z.number().int(),
    pending_review: z.number().int(),
    by_status: z.record(z.string(), z.number().int()),
    by_generator: z.record(z.string(), z.number().int()),
  }),
  hotspots: z.object({
    window_days: z.number().int(),
    min_count: z.number().int(),
    total: z.number().int(),
    items: z.array(hotspotSchema),
  }),
  recent_agent_activity: z.array(
    z.object({
      audit_id: id,
      investigation_id: id.nullable(),
      action: z.string(),
      tool_name: z.string().nullable(),
      success: z.boolean(),
      output_summary: z.string().nullable(),
      created_at: ts,
    }),
  ),
  system: z.object({
    environment: z.string(),
    database: z.object({
      status: z.literal('ok'),
      product: z.string(),
      version: z.string(),
      database: z.string(),
      schema_name: z.string(),
    }),
    llm: z.object({
      configured: z.boolean(),
      provider: z.string(),
      model: z.string().nullable(),
      problem: z.string().nullable(),
    }),
    agent: z.object({ max_steps: z.number().int(), timeout_s: z.number().int(), tools: z.array(z.string()) }),
  }),
})
export type Overview = z.infer<typeof overviewSchema>
export type AgentActivity = Overview['recent_agent_activity'][number]

export const listOf = <T extends z.ZodType>(schema: T) => z.array(schema)

// ---- request bodies ------------------------------------------------------------------------------
export interface ComplaintCreateInput {
  category: z.infer<typeof categorySchema>
  title: string
  description: string
  latitude: number
  longitude: number
  ward?: string | null
  severity: number
  source?: string
  is_synthetic: boolean
}
export interface InvestigationCreateInput {
  title: string
  question: string
}
export interface EvidenceCreateInput {
  complaint_ids: number[]
  note?: string | null
}
export interface RecommendationDraftInput {
  summary: string
  rationale: string
  priority: number
  confidence: number
  evidence_ids: number[]
}
export interface RunRequestInput {
  mode: 'auto' | 'llm' | 'fallback'
  days: number
  category?: z.infer<typeof categorySchema> | null
  max_hotspots: number
}
export interface DecisionInput {
  decision: 'APPROVED' | 'REJECTED'
  comment?: string | null
}
