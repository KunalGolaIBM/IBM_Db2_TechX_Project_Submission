/** Enumerations that mirror the backend's models (kept in sync by the zod schemas + live contract test). */

export const CATEGORIES = [
  'POTHOLE',
  'STREETLIGHT',
  'WATER_LEAK',
  'SEWAGE',
  'GARBAGE',
  'DRAINAGE',
  'ROAD_DAMAGE',
  'TRAFFIC_SIGNAL',
  'OTHER',
] as const
export type Category = (typeof CATEGORIES)[number]

export const COMPLAINT_STATUSES = [
  'NEW',
  'TRIAGED',
  'DUPLICATE',
  'UNDER_INVESTIGATION',
  'RESOLVED',
  'REJECTED',
] as const
export type ComplaintStatus = (typeof COMPLAINT_STATUSES)[number]

export const INVESTIGATION_STATUSES = ['OPEN', 'RUNNING', 'PENDING_REVIEW', 'CLOSED', 'FAILED'] as const
export type InvestigationStatus = (typeof INVESTIGATION_STATUSES)[number]

export const RECOMMENDATION_STATUSES = ['PROPOSED', 'APPROVED', 'REJECTED', 'NEEDS_INFO'] as const
export type RecommendationStatus = (typeof RECOMMENDATION_STATUSES)[number]

export const GENERATOR_TYPES = ['LLM', 'DETERMINISTIC_FALLBACK', 'MANUAL', 'UNKNOWN'] as const
export type GeneratorType = (typeof GENERATOR_TYPES)[number]

export const CATEGORY_LABEL: Record<Category, string> = {
  POTHOLE: 'Pothole',
  STREETLIGHT: 'Streetlight',
  WATER_LEAK: 'Water leak',
  SEWAGE: 'Sewage',
  GARBAGE: 'Garbage',
  DRAINAGE: 'Drainage',
  ROAD_DAMAGE: 'Road damage',
  TRAFFIC_SIGNAL: 'Traffic signal',
  OTHER: 'Other',
}

export const COMPLAINT_STATUS_LABEL: Record<ComplaintStatus, string> = {
  NEW: 'New',
  TRIAGED: 'Triaged',
  DUPLICATE: 'Duplicate',
  UNDER_INVESTIGATION: 'Under investigation',
  RESOLVED: 'Resolved',
  REJECTED: 'Rejected',
}

export const INVESTIGATION_STATUS_LABEL: Record<InvestigationStatus, string> = {
  OPEN: 'Open',
  RUNNING: 'Running',
  PENDING_REVIEW: 'Pending review',
  CLOSED: 'Closed',
  FAILED: 'Failed',
}

export const RECOMMENDATION_STATUS_LABEL: Record<RecommendationStatus, string> = {
  PROPOSED: 'Awaiting review',
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
  NEEDS_INFO: 'Needs info',
}

export const SEVERITY_LABEL: Record<number, string> = {
  1: 'Minor',
  2: 'Low',
  3: 'Moderate',
  4: 'High',
  5: 'Critical',
}

/**
 * Severity 1 -> 5 ordinal ramp. These hex values MUST equal --color-sev-* in index.css (SVG and Leaflet
 * cannot read CSS variables); tests/theme.test.ts enforces that.
 */
export const SEVERITY_COLORS = ['#a14f09', '#bb672c', '#d67f46', '#f2985f', '#feb98f'] as const
export const severityColor = (severity: number): string =>
  SEVERITY_COLORS[Math.min(Math.max(Math.round(severity), 1), 5) - 1]

/** Priority 1 is the most urgent. */
export const PRIORITY_LABEL: Record<number, string> = {
  1: 'Urgent',
  2: 'High',
  3: 'Normal',
  4: 'Low',
  5: 'Minimal',
}

export const isCategory = (value: string): value is Category => (CATEGORIES as readonly string[]).includes(value)

/** Categorical chart series (fixed order). Must equal --color-series-* in index.css (tests/theme.test.ts). */
export const SERIES_COLORS = { copper: '#cc7233', blue: '#3987e5', aqua: '#199e70', violet: '#9085e9' } as const

/** Colour follows the entity: a generator keeps its hue wherever it appears. */
export const GENERATOR_COLOR: Record<GeneratorType, string> = {
  LLM: SERIES_COLORS.copper,
  DETERMINISTIC_FALLBACK: SERIES_COLORS.blue,
  MANUAL: SERIES_COLORS.aqua,
  UNKNOWN: '#8e95a2',
}
export const GENERATOR_SEGMENT_LABEL: Record<GeneratorType, string> = {
  LLM: 'AI model (LLM)',
  DETERMINISTIC_FALLBACK: 'Rule-based · no LLM',
  MANUAL: 'Manual · analyst',
  UNKNOWN: 'Origin not recorded',
}
