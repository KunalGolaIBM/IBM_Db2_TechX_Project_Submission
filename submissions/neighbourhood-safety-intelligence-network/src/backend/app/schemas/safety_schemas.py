import datetime
from typing import Optional, List, Dict, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Allowed values, shared by request validation, the incident state machine and the clients.
IncidentType = Literal["sos", "hazard", "medical", "child_alert", "elder_welfare", "suspicious_activity"]
Priority = Literal["P1_CRITICAL", "P2_HIGH", "P3_MODERATE", "P4_ADVISORY"]
IncidentStatus = Literal["reported", "acknowledged", "responder_en_route", "on_scene", "resolving", "resolved", "false_alarm"]
Level = Literal["low", "medium", "high"]

EMAIL_PATTERN = r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$"
PHONE_PATTERN = r"^[0-9+()\-\s]{5,30}$"


def Latitude():
    return Field(default=None, ge=-90, le=90)


def Longitude():
    return Field(default=None, ge=-180, le=180)


# --- Auth & Profile ---
class UserRegister(BaseModel):
    email: str = Field(max_length=255, pattern=EMAIL_PATTERN)
    # bcrypt only uses the first 72 bytes, so longer passwords are rejected instead of silently truncated.
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=2, max_length=255)
    phone: Optional[str] = Field(default=None, pattern=PHONE_PATTERN)
    # Admin accounts can never be self-registered; responders stay unverified until an admin approves them.
    role: Literal["resident", "guardian", "responder"] = "resident"
    emergency_notes: Optional[str] = Field(default=None, max_length=2000)
    address: Optional[str] = Field(default=None, max_length=255)

    @field_validator("email")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        return v.strip().lower()

class UserLogin(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=72)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    email: str
    full_name: str
    role: str

class UserProfile(BaseModel):
    id: int
    email: str
    full_name: str
    phone: Optional[str] = None
    role: str
    is_active: bool
    is_verified: bool
    emergency_notes: Optional[str] = None
    address: Optional[str] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)

class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    phone: Optional[str] = Field(default=None, pattern=PHONE_PATTERN)
    emergency_notes: Optional[str] = Field(default=None, max_length=2000)
    address: Optional[str] = Field(default=None, max_length=255)

# --- Trusted Contacts ---
class TrustedContactCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    relationship: str = Field(min_length=2, max_length=100)
    phone: str = Field(pattern=PHONE_PATTERN)
    email: Optional[str] = Field(default=None, max_length=255, pattern=EMAIL_PATTERN)
    can_receive_sos: bool = True
    can_track_location: bool = True

class TrustedContactResponse(BaseModel):
    id: int
    user_id: int
    name: str
    relationship: str
    phone: str
    email: Optional[str] = None
    can_receive_sos: bool
    can_track_location: bool
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)

# --- Incident & SOS ---
class SOSCreate(BaseModel):
    latitude: Optional[float] = Latitude()
    longitude: Optional[float] = Longitude()
    location_address: Optional[str] = Field(default="Current GPS Location", max_length=255)
    description: Optional[str] = Field(default="Emergency SOS triggered by resident.", max_length=2000)
    emergency_type: Literal["sos", "medical", "harassment", "danger"] = "sos"

class IncidentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=5, max_length=4000)
    incident_type: IncidentType = "hazard"
    priority: Optional[Priority] = "P2_HIGH"
    location_address: Optional[str] = Field(default=None, max_length=255)
    latitude: Optional[float] = Latitude()
    longitude: Optional[float] = Longitude()

class IncidentStatusUpdate(BaseModel):
    status: IncidentStatus
    notes: Optional[str] = Field(default=None, max_length=2000)

class IncidentStatusHistoryItem(BaseModel):
    id: int
    status: str
    notes: Optional[str] = None
    updated_by_name: Optional[str] = None
    created_at: datetime.datetime

class IncidentResponse(BaseModel):
    id: int
    reference_code: str
    reporter_id: int
    reporter_name: Optional[str] = None
    title: str
    description: str
    incident_type: str
    priority: str
    status: str
    location_address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    assigned_responder_id: Optional[int] = None
    assigned_responder_name: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    resolved_at: Optional[datetime.datetime] = None
    status_history: List[IncidentStatusHistoryItem] = []

    model_config = ConfigDict(from_attributes=True)

class SimilarIncident(BaseModel):
    id: int
    reference_code: str
    title: str
    incident_type: str
    priority: str
    status: str
    location_address: Optional[str] = None
    created_at: datetime.datetime
    similarity: float  # 1 - cosine distance computed by Db2 VECTOR_DISTANCE
    same_location: bool = False  # reported at the same address as the incident being viewed

# --- Child Safety ---
class ChildJourneyCreate(BaseModel):
    child_name: str = Field(min_length=1, max_length=255)
    origin: str = Field(min_length=2, max_length=255)
    destination: str = Field(min_length=2, max_length=255)
    expected_duration_minutes: int = Field(default=30, ge=1, le=480)
    notes: Optional[str] = Field(default=None, max_length=2000)

class ChildCheckInRequest(BaseModel):
    status: Literal["active", "completed", "delayed", "alert_triggered"] = "completed"
    current_location: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = Field(default=None, max_length=1000)

class ChildJourneyResponse(BaseModel):
    id: int
    guardian_id: int
    child_name: str
    origin: str
    destination: str
    expected_arrival_time: datetime.datetime
    actual_arrival_time: Optional[datetime.datetime] = None
    status: str
    last_check_in: Optional[datetime.datetime] = None
    notes: Optional[str] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)

# --- Elder Care ---
class ElderCheckInCreate(BaseModel):
    wellness_status: Literal["good", "needs_assistance", "emergency"] = "good"
    notes: Optional[str] = Field(default=None, max_length=2000)

class ElderCheckInResponse(BaseModel):
    id: int
    user_id: int
    user_name: Optional[str] = None
    scheduled_time: datetime.datetime
    checked_in_at: Optional[datetime.datetime] = None
    status: str
    wellness_status: str
    notes: Optional[str] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)

class AssistanceRequestCreate(BaseModel):
    request_type: Literal["grocery", "medicine", "mobility", "check_in", "urgent"]
    description: str = Field(min_length=3, max_length=2000)
    urgency: Level = "medium"

class AssistanceRequestResponse(BaseModel):
    id: int
    user_id: int
    user_name: Optional[str] = None
    request_type: str
    description: str
    urgency: str
    status: str
    assigned_to_name: Optional[str] = None
    created_at: datetime.datetime
    resolved_at: Optional[datetime.datetime] = None

    model_config = ConfigDict(from_attributes=True)

# --- Responders ---
class ResponderAvailabilityUpdate(BaseModel):
    is_available: bool
    current_lat: Optional[float] = Latitude()
    current_lng: Optional[float] = Longitude()

class ResponderProfileResponse(BaseModel):
    id: int
    user_id: int
    full_name: str
    badge_number: str
    service_type: str
    is_available: bool
    current_lat: Optional[float] = None
    current_lng: Optional[float] = None
    rating: float
    is_verified_by_admin: bool

# --- Community Insights & Hazards ---
class CommunityHazardCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    hazard_type: Literal["dark_street", "road_block", "aggressive_animals", "electrical", "flooding"]
    severity: Level = "medium"
    address: str = Field(min_length=3, max_length=255)
    latitude: Optional[float] = Latitude()
    longitude: Optional[float] = Longitude()

class CommunityHazardResponse(BaseModel):
    id: int
    reported_by_id: int
    title: str
    hazard_type: str
    severity: str
    address: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    status: str
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)

class PriorityResponseTime(BaseModel):
    priority: str
    incidents: int
    acknowledged: int
    avg_ack_minutes: Optional[float] = None
    median_ack_minutes: Optional[float] = None
    p90_ack_minutes: Optional[float] = None
    avg_resolve_minutes: Optional[float] = None
    ack_target_minutes: float

class IncidentHotspot(BaseModel):
    rank: int
    location: str
    incidents: int
    open_incidents: int
    last_reported: datetime.datetime

class CommunityInsightsResponse(BaseModel):
    total_incidents: int
    active_incidents: int
    resolved_incidents: int
    # Measured time from report to first acknowledgement (None until any incident is acknowledged).
    average_response_time_minutes: Optional[float] = None
    incidents_by_type: Dict[str, int]
    incidents_by_priority: Dict[str, int]
    active_hazards: List[CommunityHazardResponse]
    safety_health_score: int  # 0 to 100
    ai_safety_advisory: str
    analytics_engine: str
    window_days: int
    response_times: List[PriorityResponseTime]
    hotspots: List[IncidentHotspot]
    incidents_by_hour: Dict[int, int]
    sla_breaches: int  # open P1-P4 incidents still unacknowledged past their target time

# --- AI Workflows ---
class AIIncidentAssistanceRequest(BaseModel):
    raw_text: str = Field(..., min_length=3, max_length=4000)
    incident_type: Optional[IncidentType] = None
    location_address: Optional[str] = Field(default=None, max_length=255)
    incident_id: Optional[int] = None  # when set, the analysis is persisted against this incident

class AIIncidentAssistanceResponse(BaseModel):
    parsed_category: str
    extracted_location: Optional[str] = None
    suggested_priority: str
    triage_reasoning: str
    missing_critical_info: List[str]
    immediate_safety_checklist: List[str]
    retrieved_civic_protocols: List[Dict[str, str]]
    advisory_notice: str = "AI-assisted guidance is advisory only. Verified human responders supervise all incident actions."
    persisted_analysis_id: Optional[int] = None
    escalated: bool = False  # True when the CrewAI flow took the critical (P1) branch
    workflow_steps: List[str] = []
