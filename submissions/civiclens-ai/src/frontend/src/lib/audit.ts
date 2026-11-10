import type { AuditEntry } from '../api/schemas'
import type { GeneratorType } from './domain'
import { GENERATOR_TYPES } from './domain'

const ACTION_LABEL: Record<string, string> = {
  INVESTIGATION_CREATED: 'Investigation created',
  AGENT_RUN_STARTED: 'Run started',
  AGENT_RUN_COMPLETED: 'Run completed',
  AGENT_RUN_FAILED: 'Run failed',
  TOOL_CALL: 'Tool call',
  TOOL_REFUSED: 'Tool call refused',
  TOOL_ARGS_REJECTED: 'Tool arguments rejected',
  EVIDENCE_REJECTED: 'Evidence rejected',
  LLM_RUN_FAILED: 'LLM run failed',
  RECOMMENDATION_PROPOSED: 'Recommendation proposed',
  REVIEW_APPROVED: 'Review: approved',
  REVIEW_REJECTED: 'Review: rejected',
  REVIEW_DENIED: 'Review attempt denied',
  COMPLAINT_CREATED: 'Complaint created',
}

export const actionLabel = (action: string): string =>
  ACTION_LABEL[action] ?? action.toLowerCase().replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())

/** Audit input is JSON, but the server truncates long payloads, so parsing can fail: fall back to raw text. */
export function parseAuditInput(input: string | null): Record<string, unknown> | null {
  if (!input) return null
  try {
    const value: unknown = JSON.parse(input)
    return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : null
  } catch {
    return null
  }
}

export const formatAuditValue = (value: unknown): string => {
  if (value === null || value === undefined) return '–'
  if (Array.isArray(value)) return value.length > 6 ? `${value.slice(0, 6).join(', ')}, … (${value.length})` : value.join(', ')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

/** Which generator the run recorded when it finished (AGENT_RUN_COMPLETED carries it), if the run finished. */
export function generatorOfRun(entries: AuditEntry[]): GeneratorType | null {
  for (const e of [...entries].reverse()) {
    if (e.action !== 'AGENT_RUN_COMPLETED') continue
    const g = parseAuditInput(e.input_json)?.generator
    if (typeof g === 'string' && (GENERATOR_TYPES as readonly string[]).includes(g)) return g as GeneratorType
  }
  return null
}

export const isToolActivity = (e: AuditEntry): boolean =>
  e.action === 'TOOL_CALL' || e.action === 'TOOL_REFUSED' || e.action === 'TOOL_ARGS_REJECTED'
