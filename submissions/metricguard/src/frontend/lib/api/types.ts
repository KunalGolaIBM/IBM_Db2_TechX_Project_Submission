/**
 * Friendly aliases over the types generated from docs/openapi.json (API contract v1.1.0).
 * Regenerate with `npm run gen:types`. Never hand-edit schema.d.ts.
 */
import type { components } from "./schema";

type S = components["schemas"];

export type ValidationStatus = S["ValidationStatus"];
export type CheckStatus = S["CheckStatus"];
export type AnalyzeResponse = S["AnalyzeResponse"];
export type Answer = S["Answer"];
export type QueryPlan = S["QueryPlan"];
export type MetricUsage = S["MetricUsage"];
export type SqlBlock = S["SqlBlock"];
export type SqlParameter = S["SqlParameterOut"];
export type ResultBlock = S["ResultBlock"];
export type ResultColumn = S["ResultColumn"];
export type ChartSpec = S["ChartSpec"];
export type ChartSeries = S["ChartSeries"];
export type Verification = S["Verification"];
export type VerificationCheck = S["VerificationCheck"];
export type Reason = S["Reason"];
export type Clarification = S["Clarification"];
export type ClarificationOption = S["ClarificationOption"];
export type PlannerInfo = S["PlannerInfo"];
export type ErrorBody = S["ErrorBody"];
export type Timing = S["Timing"];
export type HealthResponse = S["HealthResponse"];
export type MetricsResponse = S["MetricsResponse"];
export type MetricInfo = S["MetricInfo"];
export type ExamplesResponse = S["ExamplesResponse"];
export type ExampleInfo = S["ExampleInfo"];
export type AuditListResponse = S["AuditListResponse"];
export type AuditSummary = S["AuditSummary"];
export type AuditDetail = S["AuditDetail"];
export type AuditMetricDefinition = S["AuditMetricDefinition"];

export type ExecutionMode = "LLM" | "DEMO_RULE_BASED";

export const ALL_STATUSES: ValidationStatus[] = ["VERIFIED", "EXECUTED_WITH_WARNINGS", "AMBIGUOUS", "BLOCKED", "EXECUTION_FAILED"];
