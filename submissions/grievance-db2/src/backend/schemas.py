from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class DepartmentBase(BaseModel):
    code: str = Field(..., max_length=50)
    name: str = Field(..., max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    nodal_email: Optional[str] = Field(None, max_length=150)


class DepartmentOut(DepartmentBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GrievanceUpdateOut(BaseModel):
    id: int
    grievance_id: int
    previous_status: Optional[str] = None
    new_status: str
    notes: Optional[str] = None
    updated_by: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GrievanceCreate(BaseModel):
    citizen_name: str = Field(..., min_length=2, max_length=150, description="Full name of citizen")
    contact: str = Field(..., min_length=5, max_length=150, description="Phone number or email")
    category: str = Field(..., min_length=2, max_length=100, description="water, electricity, roads, sanitation, health, etc.")
    description: str = Field(..., min_length=10, max_length=3000, description="Detailed grievance description")
    ward: Optional[str] = Field("Ward 14 - Rohini East", max_length=100, description="Municipal ward or zone")
    priority: Optional[str] = Field("Medium", max_length=20, description="Low, Medium, High, Critical")
    subject: Optional[str] = Field(None, max_length=255, description="Brief subject summary")
    department_id: Optional[int] = Field(None, description="Department foreign key ID")
    state: Optional[str] = Field("Delhi (NCT)", max_length=100)
    pincode: Optional[str] = Field(None, max_length=10)
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class GrievanceStatusUpdate(BaseModel):
    status: str = Field(..., max_length=50, description="New status: Filed, Under Review, Forwarded to Dept, Resolved")
    notes: Optional[str] = Field(None, max_length=1000, description="Officer or system notes on this status change")
    updated_by: Optional[str] = Field("Officer", max_length=100, description="Name or role of updater")
    priority: Optional[str] = Field(None, max_length=20, description="Optional updated priority level")


class GrievanceOut(BaseModel):
    id: int
    tracking_id: str
    citizen_name: str
    contact: str
    category: str
    description: str
    ward: Optional[str] = None
    priority: str
    status: str
    created_at: datetime
    resolved_at: Optional[datetime] = None
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    subject: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    # AI Triage Fields (LangChain)
    ai_category: Optional[str] = None
    ai_priority: Optional[str] = None
    ai_summary: Optional[str] = None
    updates: List[GrievanceUpdateOut] = []

    model_config = ConfigDict(from_attributes=True)


class GrievanceCreateResponse(BaseModel):
    success: bool
    tracking_id: str
    message: str
    ai_triage: Optional[Dict[str, Any]] = None
    hotspot_alert: Optional[Dict[str, Any]] = None
    potential_duplicates: Optional[List[Dict[str, Any]]] = None
    data: GrievanceOut


class GrievanceListResponse(BaseModel):
    total: int
    page: int
    limit: int
    pages: int
    items: List[GrievanceOut]


class AskQuestionRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500, description="Natural language query about civic grievances")


class AskQuestionResponse(BaseModel):
    question: str
    generated_sql: str
    method: str
    execution_time_ms: float
    row_count: int
    columns: List[str]
    rows: List[Dict[str, Any]]
    explanation: Optional[str] = None
    natural_summary: Optional[str] = None


class AnalyticsResponse(BaseModel):
    total_grievances: int
    resolved_count: int
    pending_count: int
    resolution_rate: float
    avg_resolution_days: float
    sla_breaches_count: int
    sla_breached_dockets: List[Dict[str, Any]]
    department_breakdown: List[Dict[str, Any]]
    ward_breakdown: List[Dict[str, Any]]
    priority_breakdown: Dict[str, int]
    category_breakdown: Dict[str, int]


class StatsResponse(BaseModel):
    total_grievances: int
    status_breakdown: Dict[str, int]
    category_breakdown: Dict[str, int]
    priority_breakdown: Dict[str, int]
    resolved_count: int
    pending_count: int
    resolution_rate: float


# ==============================================================================
# Officer Console & AI Action Drafter Schemas
# ==============================================================================

class DraftActionRequest(BaseModel):
    tracking_id: str = Field(..., description="Tracking ID of the grievance to draft action for")


class DraftActionResponse(BaseModel):
    tracking_id: str
    action_type: str = Field(description="Field Inspection | Show-Cause Notice | Immediate Repair | Interim Relief")
    target_officer: str = Field(description="Designated officer / authority")
    statutory_deadline_days: int = Field(description="SLA compliance days allowed")
    drafted_order_text: str = Field(description="Formal administrative text of the order")
    recommended_status: str = Field(description="Forwarded to Dept | Resolved")
    generated_by: str = Field(default="LangChain Action Drafter")


class ResolveDocketRequest(BaseModel):
    tracking_id: str = Field(..., description="Tracking ID of grievance to resolve")
    officer_notes: str = Field(..., min_length=5, max_length=1500, description="Detailed action taken report (ATR) notes")
    resolution_summary: str = Field(..., min_length=5, max_length=255, description="Executive 1-sentence resolution summary")
    officer_name: str = Field("Executive Nodal Officer", max_length=100, description="Full name or designation of resolving officer")


class OfficerDocketOut(BaseModel):
    id: int
    tracking_id: str
    citizen_name: str
    contact: str
    category: str
    subject: Optional[str] = None
    description: str
    ward: Optional[str] = None
    priority: str
    status: str
    created_at: datetime
    days_open: int
    is_sla_breached: bool
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    ai_category: Optional[str] = None
    ai_priority: Optional[str] = None
    ai_summary: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class WardGeoHotspotOut(BaseModel):
    ward: str
    lat: float
    lng: float
    total_cases: int
    critical_cases: int
    sla_breaches: int
    is_hotspot: bool
    primary_category: str


class GeoHotspotsResponse(BaseModel):
    success: bool = True
    total_wards: int
    hotspots_count: int
    wards: List[WardGeoHotspotOut]
    geojson: Optional[Dict[str, Any]] = None


class SahayakChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="User query to CPGRAMS Sahayak Assistant")
    session_id: Optional[str] = Field(None, max_length=64, description="Optional conversational session ID")
    language: Optional[str] = Field("en", max_length=10, description="Preferred response language (en, hi, etc.)")


class SahayakChatResponse(BaseModel):
    reply: str
    tool_used: Optional[str] = None
    data_payload: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None



