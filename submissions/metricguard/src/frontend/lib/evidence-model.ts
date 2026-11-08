import type {
  AnalyzeResponse, AuditDetail, ErrorBody, QueryPlan, SqlParameter, Timing, ValidationStatus, Verification,
} from "@/lib/api/types";

/** One normalized view over a live analysis and a stored audit record, so the same evidence panel serves both. */
export interface EvidenceModel {
  source: "live" | "audit";
  requestId: string;
  createdAt: string;
  status: ValidationStatus;
  verification: Verification;
  plan: QueryPlan | null;
  assumptions: Assumption[];
  sql: { text: string; parameters: SqlParameter[]; sqlHash: string; tables?: string[]; generatedBy?: string } | null;
  metrics: { ref: string; name: string; version: string; displayName?: string; definitionHash: string; db2HashMatch: boolean | null }[];
  timing: Partial<Timing> | { total_ms: number | null; planning_ms: number | null; validation_ms: number | null; execution_ms: number | null; verification_ms: number | null };
  planner: { mode: "LLM" | "DEMO_RULE_BASED" | null; name: string | null; model: string | null; disclosure: string | null } | null;
  error: ErrorBody | null;
  auditPersisted: boolean | null;
  auditPath: string | null;
}

type Assumption = AnalyzeResponse["assumptions"][number];

export function fromAnalyze(r: AnalyzeResponse): EvidenceModel {
  const v03 = r.verification.checks.find((c) => c.id === "V03")?.status;
  return {
    source: "live",
    requestId: r.request_id,
    createdAt: r.created_at,
    status: r.status,
    verification: r.verification,
    plan: r.plan,
    assumptions: r.assumptions,
    sql: r.sql ? { text: r.sql.text, parameters: r.sql.parameters, sqlHash: r.sql.sql_hash, tables: r.sql.tables, generatedBy: r.sql.generated_by } : null,
    metrics: r.metrics.map((m) => ({
      ref: `${m.name}@${m.version}`, name: m.name, version: m.version, displayName: m.display_name, definitionHash: m.definition_hash,
      db2HashMatch: v03 === "PASS" ? true : v03 === "FAIL" ? false : null,
    })),
    timing: r.timing,
    planner: { mode: r.planner.execution_mode, name: r.planner.name, model: r.planner.model ?? null, disclosure: r.planner.disclosure ?? null },
    error: r.error,
    auditPersisted: r.audit.persisted,
    auditPath: r.audit.persisted ? (r.audit.url ?? null) : null,
  };
}

export function fromAudit(d: AuditDetail): EvidenceModel {
  const verification: Verification = d.verification ?? { status: d.status, summary: d.status_reason ?? "", reasons: [], checks: [] };
  return {
    source: "audit",
    requestId: d.request_id,
    createdAt: d.created_at,
    status: d.status,
    verification,
    plan: d.plan,
    assumptions: [],
    sql: d.sql ? { text: d.sql.text, parameters: d.sql.parameters, sqlHash: d.sql.sql_hash } : null,
    metrics: (d.metric_definitions ?? []).map((m) => {
      const [name = m.ref, version = ""] = m.ref.split("@");
      return { ref: m.ref, name, version, definitionHash: m.definition_hash, db2HashMatch: m.db2_hash_match ?? null };
    }),
    timing: d.timing,
    planner: { mode: d.execution_mode ?? null, name: d.planner, model: d.planner_model ?? null, disclosure: null },
    error: d.error,
    auditPersisted: true,
    auditPath: null,
  };
}
