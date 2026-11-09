"""Pydantic v2 schemas and models for PACT API."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Generic, List, Literal, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")

CaseStatusType = Literal["OPEN", "INVESTIGATING", "AWAITING_REVIEW", "REVIEWED", "NEEDS_EVIDENCE"]
CasePriorityType = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
ReviewDecisionType = Literal["FINDING_CONFIRMED", "EXCEPTION_APPROVED", "ESCALATED", "ADDITIONAL_EVIDENCE_REQUESTED"]
SimulationType = Literal["ADD_ACCEPTABLE_RECEIPT"]


class ErrorDetail(BaseModel):
    code: str
    message: str
    retryable: bool = False


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


class HealthStatus(BaseModel):
    status: str
    db2_connected: bool
    database: str
    server_version: Optional[str] = None


class RuleFindingSchema(BaseModel):
    id: Optional[int] = None
    case_id: Optional[int] = None
    rule_id: str
    rule_name: str
    status: Literal["PASS", "FAIL", "UNKNOWN"]
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
    discrepancy_amount: float = 0.00
    details: str
    evidence_refs: Optional[str] = None
    created_at: Optional[str] = None


class CaseSummary(BaseModel):
    id: int
    case_number: str
    po_line_id: int
    status: CaseStatusType
    priority: CasePriorityType
    version: int
    summary: Optional[str] = None
    po_number: str
    supplier_name: str
    item_label: str
    ordered_qty: int
    agreed_unit_price: float
    created_at: str
    updated_at: str
    findings_count: int = 0
    fail_count: int = 0
    unknown_count: int = 0


class CaseDetail(BaseModel):
    id: int
    case_number: str
    po_line_id: int
    status: CaseStatusType
    priority: CasePriorityType
    version: int
    summary: Optional[str] = None
    created_at: str
    updated_at: str
    po_number: str
    supplier_name: str
    buyer_name: str
    item_sku: str
    item_label: str
    ordered_qty: int
    agreed_unit_price: float
    ordered_on: str
    findings: List[RuleFindingSchema] = Field(default_factory=list)


class EvidenceRecord(BaseModel):
    table: str
    id: int
    record_data: Dict[str, Any]


class CaseEvidence(BaseModel):
    case_id: int
    po_line_id: int
    reconciliation_facts: Dict[str, Any]
    purchase_order: EvidenceRecord
    po_line: EvidenceRecord
    receipts: List[EvidenceRecord]
    invoices: List[EvidenceRecord]


class ReviewDecisionCreate(BaseModel):
    decision: ReviewDecisionType
    reviewer: str
    reviewer_notes: str
    rationale: Optional[str] = None
    expected_version: int


class ReviewDecisionResponse(BaseModel):
    id: int
    case_id: int
    decision: str
    reviewer: str
    reviewer_notes: str
    rationale: Optional[str] = None
    decided_at: str
    new_case_status: str
    new_case_version: int


class AuditEventResponse(BaseModel):
    id: int
    case_id: Optional[int] = None
    entity_type: str
    entity_id: str
    event_type: str
    actor: str
    action_details: str
    created_at: str


class AddAcceptableReceiptParams(BaseModel):
    delta_quantity: int = Field(gt=0, le=1_000_000, description="Hypothetical additional units to simulate")
    condition: str = Field(default="good", description="Hypothetical condition, defaults to good")
    received_on: Optional[str] = Field(default=None, description="Hypothetical receipt date (YYYY-MM-DD)")
    notes: Optional[str] = Field(default=None, max_length=500, description="Auditor rationale / notes")


class SimulationRequest(BaseModel):
    simulation_type: str = Field(default="ADD_ACCEPTABLE_RECEIPT", description="Simulation scenario type")
    parameters: AddAcceptableReceiptParams


class RuleStatusDiff(BaseModel):
    rule_id: str
    rule_name: str
    baseline_status: Literal["PASS", "FAIL", "UNKNOWN"]
    simulated_status: Literal["PASS", "FAIL", "UNKNOWN"]
    improved: bool
    details_baseline: Optional[str] = None
    details_simulated: Optional[str] = None


class SimulationStateSummary(BaseModel):
    receipt_count: int
    accepted_qty: int
    invoiced_qty: int
    gap: int
    findings_count: int
    fail_count: int
    unknown_count: int


class SimulationResponse(BaseModel):
    id: int
    case_id: int
    simulation_type: str
    parameters: Dict[str, Any]
    original_findings_count: int
    simulated_findings_count: int
    delta_summary: str
    is_recommended: bool
    baseline_state: SimulationStateSummary
    simulated_state: SimulationStateSummary
    rule_diff: List[RuleStatusDiff]
    created_at: str


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    limit: int
    pages: int


class InvestigationRequest(BaseModel):
    focus_areas: Optional[List[str]] = Field(default=None, description="Optional focus areas: quantity, pricing, delivery")
    max_tool_calls: int = Field(default=8, ge=1, le=15, description="Maximum number of read-only tool calls")


class InvestigationClaim(BaseModel):
    rule_code: str
    statement: str
    evidence_refs: List[str] = Field(default_factory=list)
    is_verified: bool = True


class ToolExecutionTrace(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    status: str
    record_ids: List[int] = Field(default_factory=list)


class InvestigationResponse(BaseModel):
    case_id: int
    status: str
    summary: str
    claims: List[InvestigationClaim]
    unknowns: List[str]
    suggested_action: str
    tool_traces: List[ToolExecutionTrace]
    cited_source_records: List[Dict[str, Any]]
    provider: str
    model: str
    created_at: str


class ReconciliationRunResult(BaseModel):
    po_lines_reconciled: int
    total_evaluations: int
    pass_count: int
    fail_count: int
    unknown_count: int
    cases_created_or_updated: int
