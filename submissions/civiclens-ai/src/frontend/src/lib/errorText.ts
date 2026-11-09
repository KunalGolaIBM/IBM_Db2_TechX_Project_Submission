import { describeFieldError, isApiError } from '../api/errors'

/** Everything the UI needs to show an API failure clearly. Pure, so it is unit tested directly. */
export interface ErrorDescription {
  title: string
  message: string
  /** HTTP status, or 0 when no response was received. */
  status: number
  /** Stable machine code, shown in small type so support can quote it. */
  code: string
  /** Specific offending values (ids, fields). */
  items: string[]
  tone: 'error' | 'warning'
}

const idList = (value: unknown): string[] =>
  Array.isArray(value) ? value.map((v) => `Complaint #${String(v)}`) : []

export function describeError(error: unknown): ErrorDescription {
  if (!isApiError(error)) {
    return {
      title: 'Something went wrong',
      message: error instanceof Error ? error.message : 'An unexpected error occurred.',
      status: 0,
      code: 'UNEXPECTED',
      items: [],
      tone: 'error',
    }
  }
  const { status, code, details, fieldErrors } = error
  const make = (title: string, message: string, extra: Partial<ErrorDescription> = {}): ErrorDescription => ({
    title,
    message,
    status,
    code,
    items: [],
    tone: 'error',
    ...extra,
  })

  if (error.kind === 'network') {
    return make(
      'Cannot reach the API',
      'The browser could not connect to the CivicLens API. Check that the backend is running and that the API address and CORS settings are correct.',
    )
  }
  if (error.kind === 'timeout') return make('The request timed out', error.message)
  if (error.kind === 'contract') {
    const issues = Array.isArray(details.issues) ? (details.issues as string[]) : []
    return make(
      'Unexpected server response',
      'The server returned data this version of the dashboard does not understand, so it was not displayed.',
      { items: issues.map((p) => `Unexpected field: ${p}`) },
    )
  }

  switch (status) {
    case 401:
      return make('Sign-in required', 'Your access token was missing, rejected or has expired. Sign in again.')
    case 403:
      if (code === 'SELF_REVIEW_FORBIDDEN') {
        return make(
          'You cannot review your own investigation',
          'You created this investigation, so the four-eyes rule prevents you from approving or rejecting its recommendations. Ask another reviewer.',
        )
      }
      return make('Your role is not allowed to do this', error.message)
    case 404:
      return make('Not found', error.message)
    case 409:
      switch (code) {
        case 'ALREADY_DECIDED':
          return make(
            'Already decided',
            'Another reviewer decided this recommendation first. Nothing was changed by your action, and the list has been refreshed.',
          )
        case 'INVESTIGATION_NOT_RUNNABLE':
          return make(
            'This investigation cannot be run',
            'It is already running, awaiting review, or closed. Only open or failed investigations can be run.',
          )
        case 'LLM_NOT_CONFIGURED':
          return make(
            'No LLM is configured on the server',
            'LLM-only mode needs a language-model provider. Choose Auto or Rule-based instead; rule-based results are always labelled as such and never presented as AI output.',
            { tone: 'warning' },
          )
        case 'INVESTIGATION_NOT_REVIEWABLE':
          return make('Not awaiting review', 'This investigation is not in the review stage, so it cannot be decided.')
        case 'EVIDENCE_MISSING':
          return make('Evidence is missing', 'The recommendation no longer has linked evidence, so it cannot be approved.')
        case 'INVESTIGATION_CLOSED':
          return make('Investigation is closed', 'A closed investigation cannot be changed.')
        default:
          return make('Conflict', error.message)
      }
    case 422:
      if (code === 'UNKNOWN_COMPLAINT_IDS') {
        return make('Unknown complaint IDs', 'These complaints do not exist in the database, so nothing was saved.', {
          items: idList(details.unknown_ids),
        })
      }
      if (code === 'EVIDENCE_NOT_ATTACHED') {
        return make('Evidence is not attached to this investigation', 'Attach these complaints first, then cite them.', {
          items: idList(details.unattached_ids),
        })
      }
      if (code === 'VALIDATION_ERROR') {
        return make('Please correct the input', 'The server rejected some values.', {
          items: fieldErrors.map(describeFieldError),
        })
      }
      if (code === 'AGENT_STEP_LIMIT') {
        return make('The agent hit its step limit', error.message, { tone: 'warning' })
      }
      return make('The request was rejected', error.message)
    case 429:
      return make('Too many requests', 'Please wait a moment and try again.', { tone: 'warning' })
    case 502:
    case 504:
      return make('The investigation agent could not finish', error.message)
    case 503:
      if (code === 'DB_UNAVAILABLE') {
        return make('Database unavailable', 'The API is running but cannot reach IBM Db2 right now. Try again shortly.', {
          tone: 'warning',
        })
      }
      if (code === 'AUTH_NOT_CONFIGURED' || code === 'AUTH_MISCONFIGURED') {
        return make(
          'Authentication is not configured',
          'The server has no valid access tokens configured, so it refuses every request (it fails closed).',
          { tone: 'warning' },
        )
      }
      return make('Service unavailable', error.message, { tone: 'warning' })
    default:
      return make(status >= 500 ? 'Server error' : 'Request failed', error.message)
  }
}
