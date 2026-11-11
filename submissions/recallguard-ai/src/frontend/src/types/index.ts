export type Severity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type IncidentStatus =
  | "REPORTED" | "INVESTIGATING" | "EVIDENCE_REVIEW" | "RECALL_RECOMMENDED" | "PENDING_APPROVAL"
  | "APPROVED" | "REJECTED" | "EXECUTING" | "COMPLETED";

export interface Incident {
  incident_id: string;
  title: string;
  source_kind: "LOT" | "BATCH";
  source_ref: string;
  contaminant: string;
  contamination_category: string;
  severity: Severity;
  supplier_id: string | null;
  supplier_name?: string | null;
  reported_by: string;
  discovered_at: string;
  incident_status: IncidentStatus;
  description?: string | null;
  is_demo: boolean;
  created_at: string;
  updated_at: string;
  evidence_count?: number;
  recall_id?: string | null;
  comments?: Comment[];
  evidence?: EvidenceDoc[];
  recalls?: RecallSummary[];
  allowed_transitions?: string[];
}

export interface Comment { comment_id: string; author: string; author_role: string; body: string; created_at?: string }

export interface Health {
  status: string;
  database: {
    mode: "db2" | "dev"; is_ibm_db2: boolean; connected: boolean; error?: string | null; warning?: string;
    label?: string; latency_ms?: number; server?: string; target?: string; vector_supported?: boolean;
  };
  ai: { provider: string; model: string | null; configured: boolean; mode: string; note: string | null };
  integrations: Record<string, { installed: boolean; version?: string } | string>;
  python: string;
}

export interface DashboardSummary {
  kpis: Record<string, number>;
  risk_distribution: { risk_class: string; n: number }[];
  status_distribution: { incident_status: string; n: number }[];
  timeline: { occurred_at: string; actor: string; action_name: string; entity_kind: string; entity_ref: string; details: string }[];
  network: Record<string, number>;
  shipments_by_destination: { dest_kind: string; n: number }[];
  engine: string;
}

export interface QueryEntry { query: string; rows: number; ms: number; params: string[] }

export interface GraphNode {
  id: string; type: string; label: string; layer: number; subtitle?: string | null; affected?: boolean; focus?: boolean;
  supplier?: string; product_id?: string | null;
}
export interface GraphEdge {
  id: string; source: string; target: string; kind: "supplies" | "transform" | "ship"; label?: string;
  affected?: boolean; record_status?: string; status?: string; units?: number; batches?: string[]; process_step?: string;
}
export interface TraceGraph { root: Record<string, unknown> & { kind: string; ref: string }; nodes: GraphNode[]; edges: GraphEdge[]; queries: QueryEntry[]; engine: string }

export interface DataGap { code: string; severity: "LOW" | "MEDIUM" | "HIGH"; refs: string[]; message: string }

export interface AgentRun {
  run_id: string; incident_id: string; agent_name: string; title: string; step_no: number;
  execution_mode: "CREWAI_LLM" | "DETERMINISTIC_FALLBACK"; run_status: "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED";
  output: Record<string, any> | null; log: string[]; started_at: string | null; completed_at: string | null;
}
export interface Investigation {
  run_id: string; incident_id: string; status: string; mode: string; mode_note: string; progress: number; agents: AgentRun[];
}

export interface RiskFactor { factor: string; weight: number; raw_value: string | number; normalized: number; contribution: number; reason: string }
export interface RecallItem {
  item_id: string; batch_id: string; product_id: string; product_name: string; location_kind: string; location_ref: string;
  location_name: string | null; city: string | null; quantity_units: number; priority: "P1" | "P2" | "P3";
  inclusion_basis: "DIRECT" | "INDIRECT" | "PRECAUTIONARY"; reason: string; evidence_refs: string | null;
}
export interface RecallAction {
  action_id: string; location_kind: string; location_ref: string; location_name: string | null; city: string | null;
  action_type: "NOTIFY" | "QUARANTINE" | "RECOVER"; action_status: string; units_expected: number; units_recovered: number;
  notes: string | null; channel: string; updated_by: string | null; updated_at: string;
}
export interface VerificationCheck { check: string; passed: boolean; severity: "INFO" | "WARNING" | "BLOCKER"; detail: string }
export interface Recall {
  recall_id: string; incident_id: string; title: string; recall_class: string; recall_status: string; risk_score: number; risk_class: string;
  instructions: string; generated_by: string; decided_by: string | null; decided_at: string | null; decision_comment: string | null;
  created_at: string; updated_at: string;
  risk: { score: number; classification: string; factors: RiskFactor[]; reasoning: string; data_completeness_pct: number; confidence: string; disclaimer: string; narrative?: string };
  plan: { title: string; summary: string; total_units: number; consumer_notice_recommended: boolean; report_markdown: string;
          notifications: { location_kind: string; location_ref: string; location_name: string; action_types: string[]; units_expected: number; batches: string[]; instruction: string }[];
          excluded_batches: { batch_id: string; product_id: string; reason: string }[] };
  verification: { verdict: string; checks: VerificationCheck[]; human_review_reasons: string[]; summary: string; unsupported_claims: string[]; missing_from_plan: string[]; extraneous_in_plan: string[] };
  items: RecallItem[]; actions: RecallAction[]; incident: Incident;
  progress: { locations_notified: number; acknowledged: number; quarantine_done: number; quarantine_total: number; recover_done: number;
              recover_total: number; units_expected: number; units_recovered: number; recovery_pct: number; open_actions: number };
}
export interface RecallSummary {
  recall_id: string; incident_id: string; title: string; recall_class: string; recall_status: string; risk_score: number; risk_class: string;
  decided_by: string | null; decided_at: string | null; created_at: string; source_ref: string; contaminant: string; item_count: number; units: number; units_recovered: number;
}

export interface Claim { type: string; value: string; page: number; section: string | null; snippet: string; source: string; positive?: boolean; exists_in_db?: boolean }
export interface EvidenceDoc {
  document_id: string; incident_id: string | null; filename: string; doc_type: string; mime_type: string; size_bytes: number; sha256: string;
  page_count: number; verification_status: "UNVERIFIED" | "VERIFIED" | "DISPUTED"; uploaded_by: string; created_at: string;
  extracted: { claims: Claim[]; summary: { lot_ids: string[]; batch_ids: string[]; contaminants: string[]; suppliers: string[]; positive_results: number; unknown_ids: string[] }; method: string };
  duplicate?: boolean; indexing?: { chunks: number; embedder: string; engine: string };
}
export interface SearchResult { chunk_id: string; document_id: string; page_no: number; section_label: string | null; content: string; score: number; filename: string; doc_type: string; verification_status: string; citation: string }

export interface AuditLog { audit_id: string; occurred_at: string; actor: string; actor_role: string; action_name: string; entity_kind: string; entity_ref: string; details: string }

export interface ImpactReport {
  source: Record<string, any>; summary: Record<string, number>; data_gaps: DataGap[]; queries: QueryEntry[]; engine: string;
  batches: { batch_id: string; batch_type: string; product_id: string | null; product_name: string | null; relation: string; depth: number; quantity: number; quantity_unit: string; uncertain_link: boolean }[];
  locations: { loc_kind: string; loc_ref: string; loc_name: string; city: string; units_received: number; units_held: number; units_in_transit: number; products: string[] }[];
  products: { product_id: string; product_name: string; brand: string; batches: string[]; units_produced: number }[];
}

export type Role = "viewer" | "analyst" | "recall_manager" | "admin";
