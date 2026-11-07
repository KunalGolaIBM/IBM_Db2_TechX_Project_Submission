import type {
  DbHealth,
  DocumentDetail,
  DocumentSummary,
  EvaluationData,
  UploadedDocument,
  Verification,
  VerificationSummary,
} from "./types";

const RAW_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
export const API_BASE = RAW_BASE.replace(/\/$/, "");

export class ApiError extends Error {
  code: string;
  status: number;
  detail?: string;

  constructor(message: string, status: number, code = "request_failed", detail?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit, timeoutMs = 45_000): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        ...(init?.headers ?? {}),
      },
      cache: "no-store",
    });
    const text = await response.text();
    const payload = text ? JSON.parse(text) : null;
    if (!response.ok) {
      const body = payload?.error;
      throw new ApiError(
        body?.message ?? `Request failed with status ${response.status}`,
        response.status,
        body?.code ?? "request_failed",
        body?.detail
      );
    }
    return payload as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("The request timed out. The verification may still be processing.", 0, "timeout");
    }
    throw new ApiError(
      "The AEGIS API is unreachable. Check that the backend is running on port 8000.",
      0,
      "network_error"
    );
  } finally {
    clearTimeout(timeout);
  }
}

export function getHealth() {
  return request<{ status: string; version: string; llm_provider: string; llm_model: string }>(
    "/health",
    undefined,
    5_000
  );
}

export function getDbHealth() {
  return request<DbHealth>("/api/db/health", undefined, 8_000);
}

export async function getDocuments(): Promise<DocumentSummary[]> {
  const data = await request<{ documents: DocumentSummary[] }>("/api/documents");
  return data.documents;
}

export function getDocument(documentId: number): Promise<DocumentDetail> {
  return request<DocumentDetail>(`/api/documents/${documentId}`);
}

export function getEvaluation(): Promise<EvaluationData> {
  return request<EvaluationData>("/api/evaluation");
}

export async function uploadDocument(file: File, title?: string): Promise<UploadedDocument> {
  const form = new FormData();
  form.append("file", file);
  if (title?.trim()) form.append("title", title.trim());
  return request<UploadedDocument>("/api/documents", { method: "POST", body: form }, 90_000);
}

export interface VerifyPayload {
  submitted_text: string;
  document_ids: number[];
  evidence_text?: string;
  evidence_title?: string;
}

export function verifyResearch(payload: VerifyPayload): Promise<Verification> {
  return request<Verification>(
    "/api/verify",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    300_000
  );
}

export async function getVerifications(): Promise<VerificationSummary[]> {
  const data = await request<{ verifications: VerificationSummary[] }>("/api/verifications");
  return data.verifications;
}

export function getVerification(sessionId: number): Promise<Verification> {
  return request<Verification>(`/api/verifications/${sessionId}`);
}
