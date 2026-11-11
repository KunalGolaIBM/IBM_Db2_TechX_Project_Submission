/**
 * Recorded REAL responses (captured from the running backend against live Db2 by
 * scripts/capture_api_examples.py). Used here as static fixtures for component tests only.
 * They are never imported by application code.
 */
import verified from "../../../docs/examples/successful-analysis.json";
import grouped from "../../../docs/examples/grouped-analysis.json";
import ambiguous from "../../../docs/examples/ambiguous-question.json";
import blocked from "../../../docs/examples/blocked-unsafe-request.json";
import blockedPolicy from "../../../docs/examples/blocked-policy.json";
import failed from "../../../docs/examples/analysis-failure.json";
import warnings from "../../../docs/examples/executed-with-warnings.json";
import auditDetail from "../../../docs/examples/audit-detail.json";
import auditHistory from "../../../docs/examples/audit-history.json";
import health from "../../../docs/examples/health.json";
import type { AnalyzeResponse, AuditDetail, AuditListResponse, HealthResponse } from "@/lib/api/types";

export const FIX = {
  verified: verified as unknown as AnalyzeResponse,
  grouped: grouped as unknown as AnalyzeResponse,
  ambiguous: ambiguous as unknown as AnalyzeResponse,
  blocked: blocked as unknown as AnalyzeResponse,
  blockedPolicy: blockedPolicy as unknown as AnalyzeResponse,
  failed: failed as unknown as AnalyzeResponse,
  warnings: warnings as unknown as AnalyzeResponse,
  auditDetail: auditDetail as unknown as AuditDetail,
  auditHistory: auditHistory as unknown as AuditListResponse,
  health: health as unknown as HealthResponse,
};
