export type Classification =
  | "SUPPORTED"
  | "CONTRADICTED"
  | "INSUFFICIENT_EVIDENCE"
  | "VERIFICATION_ERROR";

export type SessionStatus = "PROCESSING" | "COMPLETED" | "FAILED";

export interface VerificationCounts {
  total: number;
  supported: number;
  contradicted: number;
  insufficient_evidence: number;
  verification_error: number;
}

export interface Evidence {
  passage_id: number;
  passage_text: string;
  page_number: number | null;
  passage_index: number;
  document_id: number;
  document_title: string;
  filename: string;
  evidence_relationship: string | null;
  relevance_score: number;
}

export interface Claim {
  claim_id: number;
  original_claim: string;
  normalized_claim: string;
  claim_type: string;
  position_start: number | null;
  position_end: number | null;
  classification: Classification | null;
  explanation: string | null;
  limitations: string | null;
  numerical_analysis: string | null;
  human_review_status: string;
  verification_method: string | null;
  result_created_at: string | null;
  evidence: Evidence[];
}

export interface Verification {
  session_id: number;
  submitted_text: string;
  model_provider: string;
  status: SessionStatus;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
  duration_ms: number | null;
  counts: VerificationCounts;
  claims: Claim[];
}

export interface VerificationSummary {
  session_id: number;
  status: SessionStatus;
  model_provider: string;
  created_at: string;
  completed_at: string | null;
  duration_ms: number | null;
  preview: string;
  total_claims: number;
  counts: VerificationCounts;
}

export interface DocumentSummary {
  document_id: number;
  title: string;
  filename: string;
  source_type: string;
  processing_status: string;
  passage_count: number;
  created_at: string;
}

export interface Passage {
  passage_id: number;
  document_id: number;
  passage_text: string;
  page_number: number | null;
  passage_index: number;
  char_start: number | null;
  char_end: number | null;
}

export interface DocumentDetail extends DocumentSummary {
  content_hash: string;
  passages: Passage[];
}

export interface UploadedDocument extends DocumentSummary {
  content_hash: string;
  already_existed: boolean;
}

export interface EvaluationData {
  status: "not_run" | "completed" | "error";
  dataset: string;
  license: string;
  message: string;
  results: Record<string, unknown> | null;
}

export interface DbHealth {
  connected: boolean;
  database: string;
  host: string;
  schema: string;
  server?: string | null;
  server_time?: string | null;
  tables: string[];
  missing_tables: string[];
  message?: string | null;
}
