from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class EventCreate(BaseModel):
    event_type: str
    username: str
    source_ip: Optional[str] = "127.0.0.1"
    database_name: Optional[str] = "SENTINELDB"
    sql_operation: Optional[str] = "NONE"
    object_name: Optional[str] = None
    status: str = "SUCCESS"
    severity: Optional[str] = "LOW"
    event_source: Optional[str] = "DB2_AUDIT_FACILITY"
    raw_details: Optional[Dict[str, Any]] = None

class AlertCreate(BaseModel):
    event_id: Optional[int] = None
    alert_name: str
    description: str
    severity: str
    risk_score: float
    status: Optional[str] = "OPEN"

class IncidentCreate(BaseModel):
    title: str
    description: Optional[str] = None
    severity: str
    risk_score: float
    status: Optional[str] = "INVESTIGATING"
    assigned_to: Optional[str] = "LangGraph Supervisor"
    ai_summary: Optional[str] = None

class ApprovalAction(BaseModel):
    reviewer: str = "Security DBA"
    notes: Optional[str] = None

class InvestigationRequest(BaseModel):
    incident_id: str
