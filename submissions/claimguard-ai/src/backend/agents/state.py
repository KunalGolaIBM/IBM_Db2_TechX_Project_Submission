"""
ClaimGuard AI - LangGraph Shared State Definitions
Defines validated Pydantic models and TypedDict state passed between agents.
"""

from typing import Any, Dict, List, Optional, TypedDict
from pydantic import BaseModel, Field


class ExtractedDocumentData(BaseModel):
    """Structured data extracted by Document Extraction Agent."""
    patient_name: Optional[str] = None
    patient_id: Optional[str] = None
    hospital_name: Optional[str] = None
    hospital_invoice_number: Optional[str] = None
    admission_date: Optional[str] = None
    discharge_date: Optional[str] = None
    diagnosis: Optional[str] = None
    diagnosis_code: Optional[str] = None
    total_amount: Optional[float] = None
    currency: str = "INR"
    line_items: List[Dict[str, Any]] = Field(default_factory=list)
    confidence_score: float = Field(default=0.85, ge=0.0, le=1.0)
    raw_summary: Optional[str] = None


class DbVerificationResult(BaseModel):
    """Output from Database Verification Agent."""
    customer_exists: bool
    customer_details: Optional[Dict[str, Any]] = None
    policy_exists: bool
    policy_active: bool
    policy_details: Optional[Dict[str, Any]] = None
    start_date_valid: bool = True
    end_date_valid: bool = True
    has_sufficient_coverage: bool = True
    max_coverage: float = 0.0
    remaining_coverage: float = 0.0
    historical_claims_count: int = 0
    historical_claims_total: float = 0.0
    discrepancies: List[str] = Field(default_factory=list)


class FraudIndicator(BaseModel):
    """Individual fraud detection indicator."""
    alert_type: str
    severity: str = Field(..., pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    description: str
    evidence: Optional[str] = None
    risk_weight: int = 10


class FraudAnalysisResult(BaseModel):
    """Output from Fraud Detection Agent."""
    is_suspicious: bool = False
    indicators: List[FraudIndicator] = Field(default_factory=list)
    duplicate_hash_found: bool = False
    duplicate_invoice_found: bool = False
    date_anomaly_found: bool = False
    unusual_amount_found: bool = False
    summary: str = "No severe fraud indicators identified."


class DecisionResult(BaseModel):
    """Output from Decision Support Agent."""
    risk_score: float = Field(..., ge=0.0, le=100.0)
    risk_level: str = Field(..., pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    recommendation: str = Field(..., pattern="^(APPROVE|INVESTIGATE|REJECT)$")
    executive_summary: str
    key_factors: List[str] = Field(default_factory=list)
    recommended_approved_amount: Optional[float] = None
    human_review_required: bool = True
    disclaimer: str = (
        "AI output is advisory decision-support only. Final legal and financial "
        "approval or rejection must be authorized by a licensed human claim examiner."
    )


class ClaimGuardState(TypedDict, total=False):
    """
    Shared workflow state for the LangGraph orchestrator.
    Every agent reads and mutates typed segments of this state.
    """
    claim_id: str
    claim_data: Dict[str, Any]
    documents: List[Dict[str, Any]]
    extracted_docs: List[Dict[str, Any]]
    db_verification: Optional[Dict[str, Any]]
    fraud_analysis: Optional[Dict[str, Any]]
    decision_output: Optional[Dict[str, Any]]
    audit_logs: List[Dict[str, Any]]
    errors: List[str]
    current_step: str
    completed: bool
