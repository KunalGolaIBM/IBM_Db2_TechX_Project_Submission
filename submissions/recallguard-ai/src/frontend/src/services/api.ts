import type {
  AuditLog, DashboardSummary, EvidenceDoc, Health, ImpactReport, Incident, Investigation, Recall, RecallSummary, Role, SearchResult, TraceGraph,
} from "@/types";

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "/api/v1";

export const USERS: Record<Role, string> = {
  viewer: "viewer@recallguard.demo",
  analyst: "qa.analyst@recallguard.demo",
  recall_manager: "recall.manager@recallguard.demo",
  admin: "admin@recallguard.demo",
};

let currentRole: Role = (() => {
  try {
    return (localStorage.getItem("rg.role") as Role) || "analyst";
  } catch {
    return "analyst";
  }
})();

export function getRole(): Role {
  return currentRole;
}
export function setRole(r: Role) {
  currentRole = r;
  try {
    localStorage.setItem("rg.role", r);
  } catch {
    /* storage unavailable */
  }
}

export class ApiError extends Error {
  constructor(public status: number, message: string, public body?: unknown) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("X-User-Id", USERS[currentRole]);
  headers.set("X-User-Role", currentRole);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { ...init, headers });
  } catch (e) {
    throw new ApiError(0, "Cannot reach the RecallGuard API. Is the backend running on port 8000?");
  }
  const text = await res.text();
  const body = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail = body?.detail;
    const msg = typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((d: any) => `${d.loc?.slice(-1)[0]}: ${d.msg}`).join("; ") : res.statusText;
    throw new ApiError(res.status, msg || `HTTP ${res.status}`, body);
  }
  return body as T;
}

const post = <T,>(path: string, data?: unknown) => request<T>(path, { method: "POST", body: data === undefined ? undefined : JSON.stringify(data) });

export const api = {
  health: () => request<Health>("/health"),
  dashboard: () => request<DashboardSummary>("/dashboard/summary"),
  incidents: () => request<Incident[]>("/incidents"),
  incident: (id: string) => request<Incident>(`/incidents/${encodeURIComponent(id)}`),
  createIncident: (data: Record<string, unknown>) => post<Incident>("/incidents", data),
  investigate: (id: string) => post<{ run_id: string; mode: string }>(`/incidents/${encodeURIComponent(id)}/investigate`),
  reinvestigate: (id: string, reason: string) => post<{ run_id: string }>(`/incidents/${encodeURIComponent(id)}/reinvestigate`, { reason }),
  investigation: (id: string) => request<Investigation>(`/incidents/${encodeURIComponent(id)}/investigation`),
  comment: (id: string, body: string) => post(`/incidents/${encodeURIComponent(id)}/comments`, { body }),
  trace: (ref: string) => request<TraceGraph>(`/supply-chain/trace/${encodeURIComponent(ref)}`),
  impact: (ref: string) => request<ImpactReport>(`/supply-chain/impact/${encodeURIComponent(ref)}`),
  catalog: () => request<{ lots: any[]; batches: any[]; suppliers: any[] }>("/supply-chain/catalog"),
  recalls: () => request<RecallSummary[]>("/recalls"),
  recall: (id: string) => request<Recall>(`/recalls/${encodeURIComponent(id)}`),
  generateRecall: (incident_id: string) => post<Recall>("/recalls/generate", { incident_id }),
  approve: (id: string, comment: string) => post<Recall>(`/recalls/${encodeURIComponent(id)}/approve`, { comment }),
  reject: (id: string, comment: string) => post<Recall>(`/recalls/${encodeURIComponent(id)}/reject`, { comment }),
  updateAction: (id: string, actionId: string, status: string, units_recovered?: number) =>
    post<Recall>(`/recalls/${encodeURIComponent(id)}/actions/${encodeURIComponent(actionId)}`, { status, units_recovered }),
  simulateAcks: (id: string) => post<Recall>(`/recalls/${encodeURIComponent(id)}/simulate-acknowledgements`),
  completeRecall: (id: string, comment: string) => post<Recall>(`/recalls/${encodeURIComponent(id)}/complete`, { comment }),
  evidence: (incident_id?: string) => request<EvidenceDoc[]>(`/evidence${incident_id ? `?incident_id=${encodeURIComponent(incident_id)}` : ""}`),
  searchEvidence: (q: string) => request<{ query: string; results: SearchResult[]; engine: string }>(`/evidence/search?q=${encodeURIComponent(q)}`),
  upload: (file: File | Blob, filename: string, incident_id?: string, doc_type?: string) => {
    const fd = new FormData();
    fd.append("file", file, filename);
    if (incident_id) fd.append("incident_id", incident_id);
    if (doc_type) fd.append("doc_type", doc_type);
    return request<EvidenceDoc>("/evidence/upload", { method: "POST", body: fd });
  },
  setVerification: (id: string, status: string) => post<EvidenceDoc>(`/evidence/${encodeURIComponent(id)}/verification`, { status }),
  auditLogs: (entity_ref?: string) => request<AuditLog[]>(`/audit-logs${entity_ref ? `?entity_ref=${encodeURIComponent(entity_ref)}` : ""}`),
  sampleReport: async () => {
    const res = await fetch(`${BASE}/demo/sample-lab-report`);
    if (!res.ok) throw new ApiError(res.status, "Sample lab report unavailable");
    return res.blob();
  },
  tomatoTemplate: () => request<Record<string, unknown>>("/demo/tomato-incident"),
  resetDemo: () => post<{ removed_incidents: string[] }>("/demo/reset"),
};
