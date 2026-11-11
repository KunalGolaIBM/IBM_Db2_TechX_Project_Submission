/**
 * Typed API client for the Db2 Ops Copilot backend.
 *
 * All requests go through `request()`, which:
 * - normalizes network failures and API error envelopes into `ApiClientError`
 *   (code + message from the backend error contract when available)
 * - never throws raw strings, so UI error states are always renderable
 */

import type {
  ApiErrorBody,
  AgentProposalRequest,
  AgentProposalResponse,
  ApprovalDecisionResponse,
  ApprovalListResponse,
  AuditResponse,
  ChatRequest,
  ChatResponse,
  ConfigResponse,
  HealthResponse,
  SqlValidateResponse,
  StatusResponse,
} from "./types";

export class ApiClientError extends Error {
  readonly code: string;
  readonly status: number;
  readonly detail?: unknown;

  constructor(code: string, message: string, status: number, detail?: unknown) {
    super(message);
    this.name = "ApiClientError";
    this.code = code;
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      ...init,
    });
  } catch (cause) {
    throw new ApiClientError(
      "NETWORK_ERROR",
      "Cannot reach the API. Is the backend running on port 8000?",
      0,
      String(cause),
    );
  }

  if (!response.ok) {
    let body: { error?: ApiErrorBody } | null = null;
    try {
      body = (await response.json()) as { error?: ApiErrorBody };
    } catch {
      body = null;
    }
    const err = body?.error;
    throw new ApiClientError(
      err?.code ?? "HTTP_ERROR",
      err?.message ?? `Request failed with HTTP ${response.status}`,
      response.status,
      err?.detail,
    );
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => request<HealthResponse>("/api/v1/health"),
  status: () => request<StatusResponse>("/api/v1/status"),
  config: () => request<ConfigResponse>("/api/v1/config"),
  audit: (limit = 25) =>
    request<AuditResponse>(`/api/v1/audit?limit=${encodeURIComponent(limit)}`),
  approvals: () => request<ApprovalListResponse>("/api/v1/approvals"),
  proposeActions: (payload: AgentProposalRequest) =>
    request<AgentProposalResponse>("/api/v1/agent/propose", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  decideApproval: (
    approvalId: string,
    decision: "approve" | "reject",
    actor?: string,
  ) =>
    request<ApprovalDecisionResponse>(
      `/api/v1/approvals/${encodeURIComponent(approvalId)}/decision`,
      {
        method: "POST",
        body: JSON.stringify({ decision, actor }),
      },
    ),
  validateSql: (sql: string) =>
    request<SqlValidateResponse>("/api/v1/sql/validate", {
      method: "POST",
      body: JSON.stringify({ sql }),
    }),
  chat: (payload: ChatRequest) =>
    request<ChatResponse>("/api/v1/chat", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
