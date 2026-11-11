/**
 * API types — mirror of the backend contract (docs/API_CONTRACT.md).
 * The backend response models are strict (extra=forbid), so these shapes
 * are the contract; contract drift fails the TypeScript build.
 */

export type AdapterMode = "mock" | "real";
export type ProbeStatus = "ok" | "degraded" | "unavailable";

export interface Probe {
  name: string;
  status: ProbeStatus;
  mode: AdapterMode;
  latency_ms: number;
  detail: string;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  version: string;
  api_version: string;
  mode: AdapterMode;
  uptime_seconds: number;
  timestamp: string;
  checks: Probe[];
}

export interface DatabaseStatus {
  provider: string;
  connected: boolean;
  host: string;
  port: number;
  database: string;
  detail: string;
}

export interface VectorStoreStatus {
  provider: string;
  document_count: number;
  detail: string;
}

export interface ModelStatus {
  provider: string;
  model: string;
  available: boolean;
  detail: string;
  dimensions?: number | null;
}

export interface StatusResponse {
  timestamp: string;
  adapter_mode: AdapterMode;
  database: DatabaseStatus;
  vector_store: VectorStoreStatus;
  llm: ModelStatus;
  embeddings: ModelStatus;
}

export interface Citation {
  source: string;
  title: string;
  snippet: string;
  score?: number | null;
}

export interface Timings {
  total_ms: number;
  retrieval_ms?: number | null;
  generation_ms?: number | null;
}

export type ChatMode = "auto" | "rag" | "sql";
export type Intent = "docs" | "data" | "general";

export interface ChatRequest {
  message: string;
  session_id?: string | null;
  mode: ChatMode;
}

export interface ChatResponse {
  reply: string;
  intent: Intent;
  citations: Citation[];
  sql?: string | null;
  mock: boolean;
  request_id: string;
  timings: Timings;
  warnings: string[];
}

export interface SqlValidateResponse {
  valid: boolean;
  statement_type?: string | null;
  dialect?: string | null;
  normalized_sql?: string | null;
  violations: { code: string; message: string; severity: string }[];
  warnings: { code: string; message: string; severity: string }[];
  policy: { max_rows: number; timeout_ms: number; enforce_row_limit: boolean };
}

export interface ConfigResponse {
  environment: string;
  debug: boolean;
  adapter_mode: AdapterMode;
  api_base: string;
  cors_origins: string[];
  serve_frontend: boolean;
  database: { host: string; port: number; name: string; read_only_user: string };
  models: { llm: string; embeddings: string; ollama_base_url: string };
  sql_policy: {
    allowed_statements: string[];
    max_sql_length: number;
    max_ast_nodes: number;
    max_rows: number;
    query_timeout_ms: number;
    denied_schemas: string[];
    enforce_row_limit: boolean;
  };
  security: { injection_mode: string; max_message_length: number };
}

export interface AuditEntry {
  id: number;
  timestamp: string;
  operation: string;
  intent: string;
  question: string;
  status: string;
  latency_ms: number;
  detail?: string | null;
  request_id?: string | null;
}

export interface AuditResponse {
  entries: AuditEntry[];
  total: number;
  mock: boolean;
}

export type ApprovalExecutionMode =
  | "mock_simulated"
  | "disabled"
  | "admin_not_configured"
  | "enabled_unverified";

export interface ApprovalExecution {
  status: string;
  simulated: boolean;
  detail: string;
  reason?: string | null;
  code?: string | null;
  latency_ms?: number | null;
  executed_at?: string | null;
}

export interface Approval {
  id: string;
  status: string;
  action_type: string;
  params: Record<string, string>;
  statement: string;
  title: string;
  rationale: string;
  risk: string;
  created_at: string;
  expires_at: string;
  request_id: string | null;
  session_id: string | null;
  decided_by: string | null;
  decided_at: string | null;
  decision_reason: string | null;
  execution: ApprovalExecution | null;
}

export interface ApprovalListResponse {
  approvals: Approval[];
  total: number;
  mock: boolean;
  execution_mode: ApprovalExecutionMode;
}

export interface AgentProposalRequest {
  actions: {
    action_type: "runstats" | "create_index";
    params: Record<string, string>;
    rationale: string;
  }[];
  session_id?: string | null;
}

export interface AgentProposalResponse {
  approvals: Approval[];
  tool_calls: number;
  max_tool_calls: number;
  mock: boolean;
}

export interface ApprovalDecisionResponse {
  approval: Approval;
  mock: boolean;
}

export interface ApiErrorBody {
  code: string;
  message: string;
  request_id: string;
  detail?: unknown;
}
