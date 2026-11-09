/** One error type for everything that can go wrong talking to the API. Never contains credentials. */
export type ApiErrorKind = 'http' | 'network' | 'timeout' | 'contract'

export interface FieldError {
  field: string
  message: string
}

export class ApiError extends Error {
  readonly kind: ApiErrorKind
  /** HTTP status; 0 when no response was received. */
  readonly status: number
  /** Stable machine-readable code (e.g. ALREADY_DECIDED), or a synthetic one for transport failures. */
  readonly code: string
  readonly details: Record<string, unknown>
  readonly fieldErrors: FieldError[]

  constructor(init: {
    kind: ApiErrorKind
    status: number
    code: string
    message: string
    details?: Record<string, unknown>
    fieldErrors?: FieldError[]
  }) {
    super(init.message)
    this.name = 'ApiError'
    this.kind = init.kind
    this.status = init.status
    this.code = init.code
    this.details = init.details ?? {}
    this.fieldErrors = init.fieldErrors ?? []
  }
}

export const isApiError = (value: unknown): value is ApiError => value instanceof ApiError

/** `field` of a validation error that concerns the request as a whole rather than one input. */
export const WHOLE_REQUEST = 'request'

/** "title: String should have at least 3 characters", or just the message when no single field is to blame. */
export const describeFieldError = (e: FieldError): string => (e.field === WHOLE_REQUEST ? e.message : `${e.field}: ${e.message}`)

/** Build an ApiError from a non-2xx response body. Handles FastAPI's two `detail` shapes. */
export function errorFromResponse(status: number, payload: unknown, statusText = ''): ApiError {
  const detail = (payload as { detail?: unknown } | null | undefined)?.detail

  if (Array.isArray(detail)) {
    // FastAPI/pydantic request validation: [{ loc: ['body','title'], msg: '...', type: '...' }]
    const fieldErrors: FieldError[] = detail.map((item) => {
      const entry = item as { loc?: unknown[]; msg?: string }
      const path = (entry.loc ?? []).filter((p) => p !== 'body' && p !== 'query').join('.')
      // pydantic prefixes errors raised by a custom validator with "Value error, ": noise for a person reading it
      return { field: path || WHOLE_REQUEST, message: (entry.msg ?? 'Invalid value').replace(/^Value error, /, '') }
    })
    return new ApiError({
      kind: 'http',
      status,
      code: 'VALIDATION_ERROR',
      message: fieldErrors[0] ? describeFieldError(fieldErrors[0]) : 'The request was rejected.',
      fieldErrors,
    })
  }

  if (detail && typeof detail === 'object') {
    const { code, message, ...rest } = detail as Record<string, unknown>
    return new ApiError({
      kind: 'http',
      status,
      code: typeof code === 'string' ? code : `HTTP_${status}`,
      message: typeof message === 'string' ? message : statusText || 'Request failed.',
      details: rest,
    })
  }

  return new ApiError({
    kind: 'http',
    status,
    code: `HTTP_${status}`,
    message: typeof detail === 'string' ? detail : statusText || 'Request failed.',
  })
}
