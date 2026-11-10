import type {
  AnalysisResult,
  Db2Status,
  GridOverview,
  HealthResponse,
} from '../types/api';

const configured = import.meta.env.VITE_API_BASE_URL;

export const API_BASE_URL = (configured && configured.trim().length > 0
  ? configured
  : 'http://127.0.0.1:8000/api/v1'
).replace(/\/+$/, '');

export const BACKEND_ORIGIN = API_BASE_URL.replace(/\/api\/v1$/, '');
export const SWAGGER_URL = `${BACKEND_ORIGIN}/docs`;

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

function toMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  timeoutMs = 30000,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...(options.headers ?? {}),
      },
    });

    if (!response.ok) {
      let detail = `Request failed with status ${response.status}`;
      try {
        const body = (await response.json()) as { detail?: string; message?: string };
        detail = body.detail ?? body.message ?? detail;
      } catch {
        detail = response.statusText || detail;
      }
      throw new ApiError(detail, response.status);
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('The backend did not respond in time.', 0);
    }
    throw new ApiError(
      toMessage(error, 'Unable to reach the BLACKSTART AI backend.'),
      0,
    );
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  getOverview: () => request<GridOverview>('/overview'),
  getHealth: () => request<HealthResponse>('/health'),
  getDb2Status: () => request<Db2Status>('/db2/status'),
  runAnalysis: () =>
    request<AnalysisResult>('/analyze', { method: 'POST' }, 60000),
};

export function describeApiError(error: unknown): string {
  if (error instanceof ApiError && error.status === 0) {
    return `Backend unreachable at ${API_BASE_URL}. Start FastAPI with uvicorn, then retry.`;
  }
  return toMessage(error, 'Unexpected error while contacting the backend.');
}
