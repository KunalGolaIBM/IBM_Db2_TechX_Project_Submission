// Typed client for the local FastAPI (needle/src/needle/api.py). The session token lives in memory only:
// a reload signs you out, and nothing is written to localStorage or cookies.

export type Mode = "keyword" | "vector" | "hybrid";
export const MODES: Mode[] = ["keyword", "vector", "hybrid"];
export type Status = "AFFECTED" | "NOT_CONFIRMED" | "UNKNOWN_COVERAGE" | "PREVIOUSLY_AFFECTED";

export interface Ranked { rank: number; id: string; rrf: number | null; kw_rank: number | null; vec_rank: number | null; vec_dist: number | null }
export interface Doc {
  id: string; title: string; kind: string | null; packages: string[]; aliases: string[]; published: string | null;
  cvss: string | null; embargoed: boolean; embargo_until: string | null; details: string; osv: string;
}
export interface Router {
  line: string; depth: number; chosen_depth: number | null; reason: string | null; how: string;
  visible_rows: number | null; total_rows: number | null;
}
export interface ExposureRow {
  SERVICE_ID: string; SERVICE: string; OWNER_TEAM: string; SYNTHETIC: number; PACKAGE: string; VERSION_NOW: string | null;
  ADV_ID: string; STATUS: Status; EXPOSED_SINCE: string | null; EXPOSED_UNTIL: string | null; DAYS_EXPOSED: number | null;
  VERSIONS: string | null;
}
export interface Fatal { kind: "login" | "db" | "ollama" | "sql" | string; message: string }
export interface TriageResult {
  user: string; query: string; k: number; ts: string; fatal?: Fatal;
  rankings: Record<Mode, Ranked[]>; docs: Record<string, Doc>; router: Router; timings_ms: Record<string, number>;
  visible_docs: number | null; dropped_invisible: number; exposure: ExposureRow[];
  exposure_error: { kind: "no_grant" | "error"; message: string } | null;
  sql: { path: string; call: string; params: Record<string, unknown>; procedure: string; exposure: string; exposure_params: string[] };
}
export interface Memo {
  mode: Mode; model: string; elapsed_s: number; text: string; kept: number;
  removed: { text: string; reasons: string[] }[]; raw_unverified: string; advisories: string[];
}
export interface Health {
  db: { ok: boolean; detail: string; database: string };
  ollama: { ok: boolean; embed_model: string; embed_ok: boolean; llm_model: string; llm_ok: boolean; detail: string };
  demo_switcher: boolean;
}
export interface DemoUser { user: string; role: string }
export interface Config { demo_switcher: boolean; modes: Mode[]; status_help: Record<Status, string>; demo_users: DemoUser[] }
export interface SeriesPoint {
  user: string; x: number; recall: number; rows: number; underfill: number; index: boolean; L: number | null;
  ixscan_est_rows?: number; mode?: string; depth?: number; fallbacks?: number;
}
export interface Finding {
  selectivity: { split: string; n_queries: number; db2: string; series: { rcac: SeriesPoint[]; router: SeriesPoint[]; where: SeriesPoint[] } };
  estimate: { permission_ff: number; vector_ixscan_est_rows: number; srchlsiz: number; steps: string[]; same_estimate_every_step: boolean };
  correlated: { queries: number; p10_zero_rows: number; p10_recall_zero: number; coverage_by_p: Record<string, number> };
  literal_control: { heldout_recall: number; all_recall: number; all_returned: number };
  plan_cache: {
    statement: string; order: string; distinct_executable_ids: number;
    steps: { user: string; cache_entries: number; executable_id: string; executions: number; rows_read: number; rows_returned: number; queries: number }[];
  };
  sources: Record<string, string>;
}
export interface Stats {
  eval_run: { file: string; run_id: string; session_user: string; queries: number; per_slice: number };
  recall10: Record<"named" | "masked" | "paraphrase", Record<"triage" | "approx" | "bm25" | "exact", number>>;
  latency_ms: { triage_p50: number; triage_p95: number; approx_p50: number; exact_p50: number; embed_p50: number };
  ann_overlap10: number; embargoed_rows: number;
  posting_fix: { before_ms: number; after_ms: number; file: string } | null;
  tests: { passed: number; skipped: number; file: string } | null;
}
export interface ExplainPlan { name: string; sql: string; explain_time: string | null; total_cost: number | null; uses_vector_index: boolean | null; plan: string }
export interface CompareIdentity extends Partial<TriageResult> { user: string; role: string; embargoed_ids?: string[] }
export interface Compare { query: string; k: number; identities: CompareIdentity[] }
export interface Session { token: string; user: string; demo: boolean; visible_docs: number | null }

export class ApiError extends Error {
  constructor(public status: number, public kind: string, message: string) { super(message); }
}

let token: string | null = null;
export const setToken = (t: string | null) => { token = t; };

async function call<T>(path: string, body?: unknown): Promise<T> {
  let r: Response;
  try {
    r = await fetch(path, {
      method: body === undefined ? "GET" : "POST",
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "api", "The NEEDLE API is not running on this machine (python -m needle.api).");
  }
  const data = await r.json().catch(() => null);
  if (!r.ok) {
    const d = data?.detail;
    throw new ApiError(r.status, d?.kind ?? "api", d?.message ?? (typeof d === "string" ? d : `HTTP ${r.status}`));
  }
  return data as T;
}

export const api = {
  health: () => call<Health>("/api/health"),
  config: () => call<Config>("/api/config"),
  login: (user: string, password?: string) => call<Session>("/api/login", { user, password: password || null }),
  logout: () => call<{ ok: boolean }>("/api/logout", {}),
  triage: (query: string, k: number) => call<TriageResult>("/api/triage", { query, k }),
  memo: (mode: Mode) => call<Memo>("/api/memo", { mode }),
  compare: (query: string, k: number) => call<Compare>("/api/compare", { query, k }),
  finding: () => call<Finding>("/api/finding"),
  stats: () => call<Stats>("/api/stats"),
  explain: () => call<{ source: string; plans: ExplainPlan[] }>("/api/explain"),
};

export const evidenceUrl = (path: string) => {
  const [dir, name] = path.split("/").slice(-2);
  return `/api/evidence/${dir === "results" ? "results" : "evidence"}/${name}`;
};

export const fmt = {
  int: (n: number | null | undefined) => (n == null ? "–" : Math.round(n).toLocaleString("en-US")),
  dec: (n: number | null | undefined, d = 3) => (n == null ? "–" : (Math.round(n * 10 ** d + 1e-9) / 10 ** d).toFixed(d)),
  ms: (n: number | null | undefined) => (n == null ? "–" : `${n < 10 ? n.toFixed(1) : Math.round(n).toLocaleString("en-US")} ms`),
};

export const SAMPLES = [
  {
    label: "PyYAML, a chat message",
    text: "heads up from #platform-sec: someone says the yaml loader we use in a few python services can run arbitrary code when it parses an untrusted config file. no CVE number in the thread. are we exposed?",
  },
  {
    label: "Pillow FlashPix, no CVE yet",
    text: "heap overflow in the image library's FlashPix JPEG decoder can lead to code execution, no CVE yet",
  },
];
