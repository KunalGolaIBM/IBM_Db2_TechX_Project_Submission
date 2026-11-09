"""
ClaimGuard AI - Pydantic Request & Response Models
Provides strong input validation and typed responses across all API endpoints.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, EmailStr, Field


# -----------------------------------------------------------------------------
# System & Health Models
# -----------------------------------------------------------------------------
class HealthResponse(BaseModel):
    status: str
    app_name: str
    version: str
    environment: str
    database: Dict[str, Any]
    gemini_configured: bool
    demo_mode: bool
    timestamp: str


# -----------------------------------------------------------------------------
# Customer Models
# -----------------------------------------------------------------------------
class CustomerBase(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=30)
    date_of_birth: Optional[str] = None
    national_id: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=255)


class CustomerCreate(CustomerBase):
    pass


class CustomerResponse(CustomerBase):
    customer_id: str
    created_at: Optional[str] = None


# -----------------------------------------------------------------------------
# Policy Models
# -----------------------------------------------------------------------------
class PolicyBase(BaseModel):
    customer_id: str
    policy_number: str
    policy_type: str
    status: str = "ACTIVE"
    start_date: str
    end_date: str
    max_coverage_amount: float
    remaining_coverage: float
    deductible: float = 0.0
    copay_percentage: float = 0.0


class PolicyCreate(PolicyBase):
    pass


class PolicyResponse(PolicyBase):
    policy_id: str
    created_at: Optional[str] = None


# -----------------------------------------------------------------------------
# Claim Models
# -----------------------------------------------------------------------------
class ClaimCreate(BaseModel):
    policy_id: str = Field(..., min_length=1, max_length=50)
    customer_id: str = Field(..., min_length=1, max_length=50)
    incident_date: str = Field(..., min_length=8, max_length=20)
    admission_date: Optional[str] = Field(None, max_length=20)
    discharge_date: Optional[str] = Field(None, max_length=20)
    claim_amount: float = Field(..., gt=0, le=50000000.0)
    hospital_name: Optional[str] = Field(None, max_length=200)
    hospital_invoice_number: Optional[str] = Field(None, max_length=100)
    diagnosis_code: Optional[str] = Field(None, max_length=50)
    diagnosis_description: Optional[str] = Field(None, max_length=500)


class ClaimDecisionUpdate(BaseModel):
    status: str = Field(..., pattern="^(APPROVED|REJECTED|IN_REVIEW|FLAGGED)$")
    decision_notes: Optional[str] = Field(None, max_length=1000)
    approved_amount: Optional[float] = Field(None, ge=0)


class ClaimResponse(BaseModel):
    claim_id: str
    claim_number: str
    policy_id: str
    customer_id: str
    incident_date: str
    admission_date: Optional[str] = None
    discharge_date: Optional[str] = None
    claim_amount: float
    approved_amount: float = 0.0
    hospital_name: Optional[str] = None
    hospital_invoice_number: Optional[str] = None
    diagnosis_code: Optional[str] = None
    diagnosis_description: Optional[str] = None
    status: str
    risk_score: float = 0.0
    risk_level: str = "LOW"
    decision_notes: Optional[str] = None
    reviewed_by: Optional[str] = None
    submitted_at: Optional[str] = None
    updated_at: Optional[str] = None


# -----------------------------------------------------------------------------
# Document Models
# -----------------------------------------------------------------------------
class DocumentResponse(BaseModel):
    document_id: str
    claim_id: str
    document_name: str
    document_type: str
    file_path: str
    file_hash: str
    file_size_bytes: int
    mime_type: str
    extracted_data: Optional[str] = None
    uploaded_at: Optional[str] = None


# -----------------------------------------------------------------------------
# Fraud Alert Models
# -----------------------------------------------------------------------------
class FraudAlertResponse(BaseModel):
    alert_id: str
    claim_id: str
    alert_type: str
    severity: str
    description: str
    evidence_details: Optional[str] = None
    is_resolved: int = 0
    resolved_by: Optional[str] = None
    resolution_notes: Optional[str] = None
    created_at: Optional[str] = None


class AlertResolveRequest(BaseModel):
    resolution_notes: str = Field(..., min_length=3, max_length=1000)


# -----------------------------------------------------------------------------
# Verification Log Models
# -----------------------------------------------------------------------------
class VerificationLogResponse(BaseModel):
    log_id: str
    claim_id: str
    agent_name: str
    action: str
    status: str
    details: Optional[str] = None
    execution_time_ms: Optional[int] = 0
    created_at: Optional[str] = None


# -----------------------------------------------------------------------------
# User & Auth Models
# -----------------------------------------------------------------------------
class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


class UserResponse(BaseModel):
    user_id: str
    username: str
    email: str
    full_name: str
    role: str
    is_active: int


# -----------------------------------------------------------------------------
# Dashboard Stats Model
# -----------------------------------------------------------------------------
class DashboardStats(BaseModel):
    total_claims: int
    pending_claims: int
    approved_claims: int
    rejected_claims: int
    flagged_claims: int
    active_alerts: int
    total_claimed_amount: float
    total_approved_amount: float
    average_risk_score: float
    db2_connected: bool
    demo_mode: bool
