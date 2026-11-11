"""Structured output contracts shared by all five agents (validated with Pydantic).

Facts (IDs, quantities, locations) in these models are ALWAYS populated from
Db2 query results. LLM agents may only add narrative fields (summary,
hypothesis, rationale); the Verification Agent rejects any ID in narrative text
that does not exist in Db2.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AGENTS = ("investigation", "supply_chain", "risk_assessment", "recall_planning", "verification")
AGENT_TITLES = {
    "investigation": "Investigation Agent",
    "supply_chain": "Supply Chain Agent",
    "risk_assessment": "Risk Assessment Agent",
    "recall_planning": "Recall Planning Agent",
    "verification": "Verification Agent",
}


class EvidenceRef(BaseModel):
    document_id: str | None = None
    filename: str | None = None
    page: int | None = None
    section: str | None = None
    snippet: str = ""
    claim_type: str = ""
    value: str = ""
    positive: bool | None = None


class Conflict(BaseModel):
    topic: str
    statement_a: str
    statement_b: str
    sources: list[str] = Field(default_factory=list)
    resolution: str = "Requires human review"


class InvestigationFindings(BaseModel):
    incident_id: str
    suspected_source_ref: str
    source_kind: Literal["LOT", "BATCH"]
    supplier_id: str | None = None
    supplier_name: str | None = None
    contaminant: str
    lab_confirmed: bool
    lab_findings: list[EvidenceRef] = Field(default_factory=list)
    supporting_records: list[EvidenceRef] = Field(default_factory=list)
    extracted_lot_ids: list[str] = Field(default_factory=list)
    extracted_dates: list[str] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    summary: str
    hypothesis: str = ""


class LocationExposure(BaseModel):
    loc_kind: str
    loc_ref: str
    loc_name: str | None = None
    city: str | None = None
    units_received: int
    units_held: int
    units_in_transit: int = 0
    batches: list[str]
    products: list[str] = Field(default_factory=list)


class DataGap(BaseModel):
    code: str
    severity: Literal["LOW", "MEDIUM", "HIGH"]
    refs: list[str]
    message: str


class SupplyChainFindings(BaseModel):
    source_ref: str
    affected_batch_ids: list[str]
    direct_batch_ids: list[str]
    indirect_batch_ids: list[str]
    finished_batch_ids: list[str]
    product_ids: list[str]
    locations: list[LocationExposure]
    data_gaps: list[DataGap]
    summary_counts: dict[str, int]
    queries_executed: list[dict]
    engine: str
    summary: str


class RiskFactor(BaseModel):
    factor: str
    weight: int
    raw_value: str | int | float
    normalized: float
    contribution: float
    reason: str


class RiskAssessment(BaseModel):
    score: int = Field(ge=0, le=100)
    classification: Literal["LOW", "MODERATE", "HIGH", "CRITICAL"]
    recall_class: Literal["CLASS_I", "CLASS_II", "CLASS_III"]
    factors: list[RiskFactor]
    reasoning: str
    data_completeness_pct: int
    confidence: Literal["LOW", "MEDIUM", "HIGH"]
    evidence_confirmed: bool
    disclaimer: str
    model_version: str
    narrative: str = ""


class RecallItem(BaseModel):
    batch_id: str
    product_id: str
    product_name: str | None = None
    location_kind: Literal["FACILITY", "WAREHOUSE", "DISTRIBUTOR", "RETAILER"]
    location_ref: str
    location_name: str | None = None
    city: str | None = None
    quantity_units: int
    priority: Literal["P1", "P2", "P3"]
    inclusion_basis: Literal["DIRECT", "INDIRECT", "PRECAUTIONARY"]
    reason: str
    evidence_refs: list[str]
    lineage_path: list[str] = Field(default_factory=list)


class Notification(BaseModel):
    location_kind: str
    location_ref: str
    location_name: str | None = None
    action_types: list[str]
    units_expected: int
    batches: list[str]
    instruction: str


class ExcludedBatch(BaseModel):
    batch_id: str
    product_id: str
    reason: str


class RecallPlan(BaseModel):
    recall_class: Literal["CLASS_I", "CLASS_II", "CLASS_III"]
    title: str
    items: list[RecallItem]
    notifications: list[Notification]
    excluded_batches: list[ExcludedBatch]
    total_units: int
    summary: str
    consumer_notice_recommended: bool
    report_markdown: str = ""


class VerificationCheck(BaseModel):
    check: str
    passed: bool
    severity: Literal["INFO", "WARNING", "BLOCKER"]
    detail: str


class VerificationReport(BaseModel):
    verdict: Literal["PASS", "PASS_WITH_WARNINGS", "FAIL"]
    checks: list[VerificationCheck]
    unsupported_claims: list[str]
    missing_from_plan: list[str]
    extraneous_in_plan: list[str]
    conflicts: list[Conflict]
    human_review_reasons: list[str]
    requires_human_review: bool = True
    summary: str
