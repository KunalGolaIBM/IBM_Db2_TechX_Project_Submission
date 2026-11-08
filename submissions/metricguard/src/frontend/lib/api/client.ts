import type {
  AnalyzeResponse, AuditDetail, AuditListResponse, ExamplesResponse, HealthResponse, MetricsResponse, ValidationStatus,
} from "./types";
import { ALL_STATUSES } from "./types";

export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

/** Every failure the UI has to tell apart. */
export type ApiErrorKind =
  | "network"              // fetch failed: backend not reachable
  | "timeout"              // client gave up waiting
  | "planner_unavailable"  // 503 PLANNER_UNAVAILABLE (transport error, no analysis body)
  | "db_unavailable"       // 503 on /api/health or other Db2-dependent endpoints
  | "not_found"            // 404
  | "invalid_request"      // 422
  | "server"               // 5xx / unexpected status
  | "malformed";           // 2xx whose body does not match the contract

export class ApiError extends Error {
  constructor(
    public readonly kind: ApiErrorKind,
    message: string,
    public readonly status?: number,
    public readonly code?: string,
    public readonly details?: string[],
    public readonly body?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface RequestOptions { method?: "GET" | "POST"; body?: unknown; signal?: AbortSignal; timeoutMs?: number }

async function request<T>(path: string, opts: RequestOptions = {}): Promise<{ data: T; status: number }> {
  const { method = "GET", body, signal, timeoutMs = 60_000 } = opts;
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
  const onAbort = () => controller.abort();
  signal?.addEventListener("abort", onAbort);

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: body !== undefined ? { "content-type": "application/json", accept: "application/json" } : { accept: "application/json" },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
      cache: "no-store",
    });
  } catch (err) {
    if (signal?.aborted) throw err; // caller cancelled: let it propagate as AbortError
    if (timedOut) throw new ApiError("timeout", "The request took too long. The backend may be busy.");
    throw new ApiError("network", "Cannot reach the MetricGuard API.");
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onAbort);
  }

  let json: unknown = null;
  try { json = await res.json(); } catch { json = null; }

  if (!res.ok) {
    // /api/health uses 503 with a normal HealthResponse body; callers that want it use `getHealth`.
    const errBody = (json as { error?: { code?: string; message?: string; details?: { field?: string; issue?: string }[] } } | null)?.error;
    const code = errBody?.code;
    const message = errBody?.message ?? `Unexpected response (HTTP ${res.status}).`;
    const details = errBody?.details?.map((d) => (d.field ? `${d.field}: ${d.issue}` : String(d.issue ?? ""))).filter(Boolean);
    if (res.status === 503 && code === "PLANNER_UNAVAILABLE") throw new ApiError("planner_unavailable", message, 503, code, details);
    if (res.status === 503) throw new ApiError("db_unavailable", message, 503, code, details, json);
    if (res.status === 404) throw new ApiError("not_found", message, 404, code, details);
    if (res.status === 422) throw new ApiError("invalid_request", message, 422, code, details);
    throw new ApiError("server", message, res.status, code, details);
  }
  return { data: json as T, status: res.status };
}

// ---------- runtime guards (cheap contract checks, not a schema validator) ----------

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);

export function assertAnalyzeResponse(v: unknown): AnalyzeResponse {
  if (!isObj(v)) throw malformed("not an object");
  if (typeof v.request_id !== "string") throw malformed("request_id missing");
  if (typeof v.status !== "string" || !ALL_STATUSES.includes(v.status as ValidationStatus)) throw malformed(`unknown status ${String(v.status)}`);
  if (!isObj(v.verification) || !Array.isArray(v.verification.checks) || !Array.isArray(v.verification.reasons)) throw malformed("verification missing");
  if (!isObj(v.planner) || typeof v.planner.execution_mode !== "string") throw malformed("planner metadata missing");
  if (!isObj(v.timing) || !isObj(v.audit)) throw malformed("timing/audit missing");
  const executed = v.status === "VERIFIED" || v.status === "EXECUTED_WITH_WARNINGS";
  if (executed && (!isObj(v.result) || !Array.isArray(v.result.rows) || !Array.isArray(v.result.columns))) throw malformed("executed status without result");
  if (executed && !isObj(v.answer)) throw malformed("executed status without answer");
  return v as unknown as AnalyzeResponse;
}

function malformed(why: string) {
  return new ApiError("malformed", `The API returned a response that does not match the contract (${why}).`);
}

// ---------- endpoints ----------

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  try {
    const { data } = await request<HealthResponse>("/api/health", { signal, timeoutMs: 10_000 });
    if (!isObj(data) || !isObj(data.database)) throw malformed("health body");
    return data;
  } catch (err) {
    // 503 carries a full HealthResponse describing the outage; surface it instead of a bare error.
    if (err instanceof ApiError && err.kind === "db_unavailable" && isObj(err.body) && isObj(err.body.database)) return err.body as unknown as HealthResponse;
    throw err;
  }
}

export async function getMetrics(signal?: AbortSignal): Promise<MetricsResponse> {
  const { data } = await request<MetricsResponse>("/api/metrics", { signal, timeoutMs: 15_000 });
  if (!isObj(data) || !Array.isArray(data.metrics)) throw malformed("metrics body");
  return data;
}

export async function getExamples(signal?: AbortSignal): Promise<ExamplesResponse> {
  const { data } = await request<ExamplesResponse>("/api/examples", { signal, timeoutMs: 15_000 });
  if (!isObj(data) || !Array.isArray(data.examples)) throw malformed("examples body");
  return data;
}

/**
 * Browser-side limit for POST /api/analyze. It must exceed the API's worst case (PLANNER_TIMEOUT_SECONDS 30 s x 2
 * attempts + backoff, about 61 s) so the UI shows the API's own answer, including its 503, instead of a bare timeout.
 */
export const ANALYZE_TIMEOUT_MS = 90_000;

export async function analyze(question: string, signal?: AbortSignal): Promise<AnalyzeResponse> {
  const { data } = await request<unknown>("/api/analyze", { method: "POST", body: { question }, signal, timeoutMs: ANALYZE_TIMEOUT_MS });
  return assertAnalyzeResponse(data);
}

export async function listAudit(params: { limit?: number; offset?: number; status?: ValidationStatus | "" }, signal?: AbortSignal): Promise<AuditListResponse> {
  const q = new URLSearchParams();
  if (params.limit) q.set("limit", String(params.limit));
  if (params.offset) q.set("offset", String(params.offset));
  if (params.status) q.set("status", params.status);
  const qs = q.toString();
  const { data } = await request<AuditListResponse>(`/api/audit${qs ? `?${qs}` : ""}`, { signal, timeoutMs: 20_000 });
  if (!isObj(data) || !Array.isArray(data.items)) throw malformed("audit list body");
  return data;
}

export async function getAuditDetail(requestId: string, signal?: AbortSignal): Promise<AuditDetail> {
  const { data } = await request<AuditDetail>(`/api/audit/${encodeURIComponent(requestId)}`, { signal, timeoutMs: 20_000 });
  if (!isObj(data) || typeof data.request_id !== "string") throw malformed("audit detail body");
  return data;
}
