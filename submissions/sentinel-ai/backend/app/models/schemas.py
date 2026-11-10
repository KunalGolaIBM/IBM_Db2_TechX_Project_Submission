from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class UserAccount(BaseModel):
    user_id: str
    username: str
    full_name: str
    email: str
    role: str
    department: str
    security_clearance: str
    status: str
    created_at: Optional[str] = None

class LoginEvent(BaseModel):
    event_id: str
    user_id: str
    timestamp: str
    ip_address: str
    device_name: Optional[str] = None
    device_type: Optional[str] = None
    location: Optional[str] = None
    status: str
    failure_reason: Optional[str] = None
    user_agent: Optional[str] = None

class AccessLog(BaseModel):
    log_id: str
    user_id: str
    timestamp: str
    resource_id: str
    resource_name: str
    resource_type: str
    access_type: str
    status: str
    classification_level: str

class SecurityAlert(BaseModel):
    alert_id: str
    user_id: str
    event_type: str
    severity: str
    description: str
    timestamp: str
    correlated_incident_id: Optional[str] = None
    status: str

class AIAnalysisRecord(BaseModel):
    analysis_id: str
    incident_id: str
    agent_name: str
    analysis_type: str
    findings: str
    reasoning: str
    confidence_score: float
    created_at: Optional[str] = None

class ResponseRecommendation(BaseModel):
    recommendation_id: str
    incident_id: str
    action_type: str
    description: str
    status: str
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    execution_notes: Optional[str] = None
    created_at: Optional[str] = None

class Incident(BaseModel):
    incident_id: str
    title: str
    user_id: str
    status: str
    severity: str
    risk_score: int
    mitre_technique_ids: Optional[str] = None
    summary: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    user: Optional[UserAccount] = None
    analyses: Optional[List[AIAnalysisRecord]] = []
    recommendations: Optional[List[ResponseRecommendation]] = []

class InvestigateRequest(BaseModel):
    user_id: str
    lookback_hours: Optional[int] = 24

class AttackSimulateRequest(BaseModel):
    target_user_id: Optional[str] = "USR-101"
    scenario: Optional[str] = "MULTI_VECTOR_COMPROMISE"

class ApprovalActionRequest(BaseModel):
    action: str = Field(..., description="'APPROVE' or 'REJECT'")
    admin_name: Optional[str] = "Cyber Commander Administrator"
    notes: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]

class DashboardStats(BaseModel):
    total_events: int
    successful_logins: int
    failed_logins: int
    suspicious_activities: int
    active_incidents: int
    pending_approvals: int
    severity_breakdown: Dict[str, int]
    system_status: Dict[str, Any]

