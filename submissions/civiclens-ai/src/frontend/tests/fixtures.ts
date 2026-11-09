import type {
  AuditEntry,
  Complaint,
  EvidenceItem,
  Hotspot,
  Investigation,
  Me,
  Overview,
  Recommendation,
  RecommendationListItem,
  RunResult,
} from '../src/api/schemas'

export const API = 'http://api.test'

export const analyst: Me = {
  user_id: 'alice',
  role: 'analyst',
  capabilities: ['complaint:create', 'investigation:create', 'evidence:attach', 'investigation:run', 'recommendation:propose'],
}
export const reviewer: Me = { user_id: 'rita', role: 'reviewer', capabilities: ['recommendation:decide'] }

/** Fake tokens for tests only: they are accepted by the MSW server and mean nothing anywhere else. */
export const TOKENS = { analyst: 'test-analyst-token-0000000000', reviewer: 'test-reviewer-token-000000000' } as const
export const meForToken = (token: string): Me | null =>
  token === TOKENS.analyst ? analyst : token === TOKENS.reviewer ? reviewer : null

export const complaint = (over: Partial<Complaint> = {}): Complaint => ({
  complaint_id: 1,
  external_ref: 'SYN-0001',
  category: 'POTHOLE',
  title: 'Deep pothole on main road',
  description: '[SYNTHETIC] Deep pothole on main road. Reported by a fictional resident for demo purposes.',
  latitude: 27.4964,
  longitude: 77.6767,
  geo_cell: 'C5499_15535',
  ward: 'Ward 1',
  severity: 4,
  status: 'NEW',
  source: 'SYNTHETIC',
  duplicate_of: null,
  is_synthetic: true,
  reported_at: '2026-11-08T21:00:00',
  created_at: '2026-11-09T08:51:04.548588',
  ...over,
})

export const hotspot = (over: Partial<Hotspot> = {}): Hotspot => ({
  geo_cell: 'C5499_15535',
  category: 'POTHOLE',
  complaint_count: 9,
  avg_severity: 3.6,
  center_latitude: 27.4966,
  center_longitude: 77.6767,
  first_reported_at: '2026-10-12T19:00:00',
  last_reported_at: '2026-11-08T21:00:00',
  ...over,
})

export const investigation = (over: Partial<Investigation> = {}): Investigation => ({
  investigation_id: 7,
  title: 'Pothole cluster triage',
  question: 'Which neighbourhoods should repair crews visit first?',
  status: 'OPEN',
  created_by: 'alice',
  created_at: '2026-11-09T09:00:00',
  closed_at: null,
  ...over,
})

export const evidenceItem = (over: Partial<EvidenceItem> = {}): EvidenceItem => ({
  investigation_id: 7,
  complaint_id: 1,
  relevance: 1,
  note: 'cited by DETERMINISTIC_FALLBACK',
  added_at: '2026-11-09T09:01:00',
  title: 'Deep pothole on main road',
  category: 'POTHOLE',
  geo_cell: 'C5499_15535',
  severity: 4,
  reported_at: '2026-11-08T21:00:00',
  is_synthetic: true,
  ...over,
})

export const recommendation = (over: Partial<Recommendation> = {}): Recommendation => ({
  recommendation_id: 11,
  investigation_id: 7,
  summary: 'Inspect pothole cluster in cell C5499_15535 (9 complaints)',
  rationale:
    '[RULE-BASED, NO LLM] Rule set hotspot-rules-v1. Db2 aggregation found 9 non-duplicate pothole complaints in geo-cell C5499_15535.',
  priority: 1,
  confidence: 0.692,
  evidence_ids: [1, 2],
  generator_type: 'DETERMINISTIC_FALLBACK',
  model_name: 'hotspot-rules-v1',
  status: 'PROPOSED',
  created_at: '2026-11-09T09:02:00',
  review: null,
  ...over,
})

export const queueItem = (over: Partial<RecommendationListItem> = {}): RecommendationListItem => ({
  ...recommendation(),
  investigation_title: 'Pothole cluster triage',
  investigation_status: 'PENDING_REVIEW',
  investigation_created_by: 'alice',
  ...over,
})

export const auditEntry = (over: Partial<AuditEntry> = {}): AuditEntry => ({
  audit_id: 1,
  actor_type: 'AGENT',
  actor_id: 'civiclens-agent',
  action: 'TOOL_CALL',
  tool_name: 'hotspot_summary',
  input_json: '{"days": 30, "min_count": 3, "limit": 3}',
  output_summary: '3 rows',
  success: true,
  created_at: '2026-11-09T09:01:30',
  ...over,
})

export const runResult = (over: Partial<RunResult> = {}): RunResult => ({
  investigation_id: 7,
  status: 'PENDING_REVIEW',
  generator: 'DETERMINISTIC_FALLBACK',
  model_name: 'hotspot-rules-v1',
  llm_configured: false,
  fallback_reason: 'No LLM provider configured (LLM_PROVIDER=none).',
  steps: 4,
  tool_calls: 4,
  recommendation_ids: [11],
  notice: 'Recommendations were produced by deterministic rule-based logic. NO LLM WAS USED. All are PROPOSED and need human review.',
  ...over,
})

export function overview(over: Partial<Overview> = {}): Overview {
  const trend = Array.from({ length: 30 }, (_, i) => ({
    date: `2026-10-${String(11 + i).padStart(2, '0')}`.replace(/^2026-10-(3[2-9]|[4-9]\d)/, '2026-11-01'),
    count: i % 5,
  }))
  return {
    generated_at: '2026-11-09T10:09:01.123456',
    complaints: {
      total: 52,
      synthetic: 52,
      real: 0,
      last_7d: 14,
      last_30d: 50,
      by_category: [
        { category: 'POTHOLE', count: 13, avg_severity: 3.4, synthetic: 13 },
        { category: 'WATER_LEAK', count: 11, avg_severity: 3.1, synthetic: 11 },
        { category: 'GARBAGE', count: 8, avg_severity: 3.0, synthetic: 8 },
      ],
      by_status: [{ status: 'NEW', count: 52 }],
      by_severity: [1, 2, 3, 4, 5].map((severity) => ({ severity, count: severity * 2 })),
      trend_days: 30,
      trend,
    },
    investigations: {
      total: 4,
      active: 2,
      by_status: { OPEN: 1, RUNNING: 0, PENDING_REVIEW: 1, CLOSED: 2, FAILED: 0 },
    },
    recommendations: {
      total: 3,
      pending_review: 1,
      by_status: { PROPOSED: 1, APPROVED: 1, REJECTED: 1, NEEDS_INFO: 0 },
      by_generator: { LLM: 0, DETERMINISTIC_FALLBACK: 3, MANUAL: 0, UNKNOWN: 0 },
    },
    hotspots: {
      window_days: 30,
      min_count: 3,
      total: 12,
      items: [hotspot(), hotspot({ geo_cell: 'C5497_15536', category: 'WATER_LEAK', complaint_count: 7 })],
    },
    recent_agent_activity: [
      {
        audit_id: 5,
        investigation_id: 7,
        action: 'TOOL_CALL',
        tool_name: 'hotspot_summary',
        success: true,
        output_summary: '3 rows',
        created_at: '2026-11-09T09:01:30',
      },
    ],
    system: {
      environment: 'development',
      database: { status: 'ok', product: 'DB2/LINUXX8664', version: '12.01.0500', database: 'CIVICDB', schema_name: 'CIVICLENS' },
      llm: { configured: false, provider: 'none', model: null, problem: null },
      agent: {
        max_steps: 6,
        timeout_s: 90,
        tools: ['search_complaints', 'get_complaint', 'find_duplicate_candidates', 'hotspot_summary'],
      },
    },
    ...over,
  }
}
