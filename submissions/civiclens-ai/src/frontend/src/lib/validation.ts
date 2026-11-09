/**
 * Client-side form checks. They mirror the server's limits only to give instant feedback; the server
 * remains the authority and its 422 responses are always displayed as well.
 */
export type FieldErrors<K extends string> = Partial<Record<K, string>>

export const LIMITS = {
  title: [3, 200],
  question: [3, 2000],
  description: [3, 4000],
  summary: [5, 500],
  rationale: [10, 8000],
  comment: [3, 2000],
  maxEvidence: 50,
} as const

const lengthError = (value: string, [min, max]: readonly [number, number], label: string): string | undefined => {
  const n = value.trim().length
  if (n < min) return `${label} must be at least ${min} characters.`
  if (n > max) return `${label} must be at most ${max} characters.`
  return undefined
}

export function validateInvestigation(f: { title: string; question: string }): FieldErrors<'title' | 'question'> {
  return {
    title: lengthError(f.title, LIMITS.title, 'Title'),
    question: lengthError(f.question, LIMITS.question, 'Question'),
  }
}

export interface ComplaintForm {
  title: string
  description: string
  latitude: string
  longitude: string
  ward: string
}

const coordinate = (raw: string, min: number, max: number, label: string): string | undefined => {
  if (raw.trim() === '') return `${label} is required.`
  const n = Number(raw)
  if (!Number.isFinite(n)) return `${label} must be a number.`
  if (n < min || n > max) return `${label} must be between ${min} and ${max}.`
  return undefined
}

export function validateComplaint(f: ComplaintForm): FieldErrors<keyof ComplaintForm> {
  return {
    title: lengthError(f.title, LIMITS.title, 'Title'),
    description: lengthError(f.description, LIMITS.description, 'Description'),
    latitude: coordinate(f.latitude, -90, 90, 'Latitude'),
    longitude: coordinate(f.longitude, -180, 180, 'Longitude'),
    ward: f.ward.trim().length > 64 ? 'Ward must be at most 64 characters.' : undefined,
  }
}

export function validateRecommendation(f: {
  summary: string
  rationale: string
  evidenceIds: number[]
}): FieldErrors<'summary' | 'rationale' | 'evidence'> {
  return {
    summary: lengthError(f.summary, LIMITS.summary, 'Summary'),
    rationale: lengthError(f.rationale, LIMITS.rationale, 'Explanation'),
    evidence:
      f.evidenceIds.length === 0
        ? 'Select at least one piece of attached evidence.'
        : f.evidenceIds.length > LIMITS.maxEvidence
          ? `Cite at most ${LIMITS.maxEvidence} complaints.`
          : undefined,
  }
}

export const validateDecision = (decision: 'APPROVED' | 'REJECTED', comment: string): string | undefined =>
  decision === 'REJECTED' && comment.trim().length < LIMITS.comment[0]
    ? `A comment of at least ${LIMITS.comment[0]} characters is required to reject.`
    : comment.trim().length > LIMITS.comment[1]
      ? `Comment must be at most ${LIMITS.comment[1]} characters.`
      : undefined

/** True when no field has an error message. */
export const isValid = (errors: Record<string, string | undefined>): boolean => Object.values(errors).every((e) => !e)

/** "12, #15 99" -> ids [12, 15, 99]; anything that is not a positive integer is reported back, not dropped. */
export function parseIdList(text: string): { ids: number[]; invalid: string[] } {
  const ids = new Set<number>()
  const invalid: string[] = []
  for (const token of text.split(/[\s,;]+/).filter(Boolean)) {
    const m = /^#?(\d{1,15})$/.exec(token)
    const n = m ? Number(m[1]) : NaN
    if (Number.isSafeInteger(n) && n >= 1) ids.add(n)
    else invalid.push(token)
  }
  return { ids: [...ids].sort((a, b) => a - b), invalid }
}
