// Typed client for the ShipSafe REST API (same origin; Vite proxies /api in dev).

export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info';
export type Gate = 'PASS' | 'PASS_WITH_WARNINGS' | 'BLOCKED';
export type Role = 'viewer' | 'operator' | 'admin';

export interface AssessmentRow {
  ASSESSMENT_ID: string;
  PROJECT_ID: string;
  PROJECT_NAME: string;
  PROFILE: string;
  STATUS: Gate;
  GATE_REASON: string;
  STARTED_AT: number;
  FINISHED_AT: number;
  FINDINGS_COUNT: number;
  CRITICAL_COUNT: number;
  HIGH_COUNT: number;
  MEDIUM_COUNT: number;
  LOW_COUNT: number;
  COMMIT_SHA?: string;
}

export interface PolicyRef {
  doc_id: string;
  title: string;
  section?: string;
  version?: string;
  similarity?: number;
}

export interface FindingRow {
  FINDING_ID: string;
  FINGERPRINT: string;
  SOURCE_TOOL: string;
  RULE_ID: string;
  CATEGORY: string;
  SEVERITY: Severity;
  CONFIDENCE: string;
  FILE_PATH: string | null;
  LINE_START: number | null;
  TITLE: string;
  DESCRIPTION: string;
  REMEDIATION: string;
  EVIDENCE: { snippet?: string; policy?: PolicyRef; sources?: string[]; package?: string; fix_versions?: string[]; [k: string]: unknown };
  REFERENCES: string[];
}

export interface ToolRunRow {
  TOOL_NAME: string;
  VERSION: string;
  STATUS: 'passed' | 'failed' | 'skipped' | 'unsupported' | 'not_run';
  DURATION_MS: number;
  EXIT_CODE: number;
  MESSAGE: string;
}

export interface TrendRow {
  PROJECT_ID: string;
  PROJECT_NAME: string;
  ASSESSMENT_ID: string;
  STATUS: Gate;
  STARTED_AT: number;
  CRITICAL_COUNT: number;
  HIGH_COUNT: number;
  MEDIUM_COUNT: number;
  LOW_COUNT: number;
  RISK_SCORE: number;
  RISK_DELTA: number | null;
}

export interface Overview {
  stats: {
    projects: number;
    assessments: number;
    blocked_runs: number;
    findings: number;
    unique_issues: number;
    policy_docs: number;
    open_critical: number;
    open_high: number;
    projects_blocked: number;
  };
  posture: TrendRow[];
  trend: TrendRow[];
  breakdown: { CATEGORY: string; SEVERITY: Severity; TOTAL: number; UNIQUE_ISSUES: number }[];
  recent: AssessmentRow[];
}

export interface Ready {
  status: 'ready' | 'degraded';
  db2: {
    connected: boolean;
    engine?: string;
    version?: string;
    database?: string;
    schema?: string;
    host?: string;
    port?: number;
    tables_in_schema?: number;
    views_in_schema?: number;
    latency_ms?: number;
    policy_chunks?: number;
    error?: string;
  };
}

export interface JobStep {
  key: string;
  message: string;
  ts: number;
}

export interface Job {
  job_id: string;
  status: 'queued' | 'running' | 'done' | 'failed';
  target: string;
  profile: string;
  actor: string;
  created_at: number;
  finished_at: number | null;
  steps: JobStep[];
  steps_total: string[];
  current_step: string | null;
  assessment_id: string | null;
  gate: Gate | null;
  persisted?: boolean;
  warnings: string[];
  error: string | null;
  summary: { findings: number; critical: number; high: number; medium: number; low: number; reason: string; project: string } | null;
}

export interface PolicyHit {
  doc_id: string;
  title: string;
  section: string;
  category: string;
  version: string;
  source: string;
  content: string;
  similarity: number;
  cosine_distance: number;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

const TOKEN_KEY = 'shipsafe.token';

export const tokenStore = {
  get(): string | null {
    try {
      return sessionStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set(token: string) {
    try {
      sessionStorage.setItem(TOKEN_KEY, token);
    } catch {
      /* storage unavailable: token lives only in memory for this tab */
    }
  },
  clear() {
    try {
      sessionStorage.removeItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
  },
};

let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn;
}

export async function api<T>(path: string, init: RequestInit = {}, token = tokenStore.get()): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  const res = await fetch(path, { ...init, headers });
  if (res.status === 401 && onUnauthorized) onUnauthorized();
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === 'string' ? body.detail : Array.isArray(body.detail) ? body.detail[0]?.msg : body.error || detail;
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, detail || `Request failed (${res.status})`);
  }
  const type = res.headers.get('content-type') || '';
  return (type.includes('application/json') ? res.json() : res.text()) as Promise<T>;
}

export async function download(path: string, filename: string) {
  const headers = new Headers();
  const token = tokenStore.get();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const res = await fetch(path, { headers });
  if (!res.ok) throw new ApiError(res.status, 'Download failed');
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
