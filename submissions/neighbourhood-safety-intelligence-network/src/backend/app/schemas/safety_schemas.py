import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

# --- Auth & Profile ---
class UserRegister(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=6)
    full_name: str = Field(min_length=2)
    phone: Optional[str] = None
    role: str = "resident"  # resident, responder, admin, guardian
    emergency_notes: Optional[str] = None
    address: Optional[str] = None

class UserLogin(BaseModel):
    email: str
    password: str

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
    full_name: Optional[str] = None
    phone: Optional[str] = None
    emergency_notes: Optional[str] = None
    address: Optional[str] = None

# --- Trusted Contacts ---
class TrustedContactCreate(BaseModel):
    name: str = Field(min_length=2)
    relationship: str
    phone: str
    email: Optional[str] = None
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
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_address: Optional[str] = "Current GPS Location"
    description: Optional[str] = "Emergency SOS triggered by resident."
    emergency_type: str = "sos"  # sos, medical, harassment, danger

class IncidentCreate(BaseModel):
    title: str = Field(min_length=3)
    description: str = Field(min_length=5)
    incident_type: str = "hazard"  # sos, hazard, medical, child_alert, elder_welfare, suspicious_activity
    priority: Optional[str] = "P2_HIGH"  # P1_CRITICAL, P2_HIGH, P3_MODERATE, P4_ADVISORY
    location_address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class IncidentStatusUpdate(BaseModel):
    status: str  # acknowledged, responder_en_route, on_scene, resolving, resolved, false_alarm
    notes: Optional[str] = None

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

# --- Child Safety ---
class ChildJourneyCreate(BaseModel):
    child_name: str
    origin: str
    destination: str
    expected_duration_minutes: int = 30
    notes: Optional[str] = None

class ChildCheckInRequest(BaseModel):
    status: str = "completed"  # active, completed, delayed, alert_triggered
    current_location: Optional[str] = None
    notes: Optional[str] = None

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
    wellness_status: str = "good"  # good, needs_assistance, emergency
    notes: Optional[str] = None

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
    request_type: str  # grocery, medicine, mobility, check_in, urgent
    description: str
    urgency: str = "medium"  # low, medium, high

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
    current_lat: Optional[float] = None
    current_lng: Optional[float] = None

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
    title: str
    hazard_type: str  # dark_street, road_block, aggressive_animals, electrical, flooding
    severity: str = "medium"
    address: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None

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

class CommunityInsightsResponse(BaseModel):
    total_incidents: int
    active_incidents: int
    resolved_incidents: int
    average_response_time_minutes: float
    incidents_by_type: Dict[str, int]
    incidents_by_priority: Dict[str, int]
    active_hazards: List[CommunityHazardResponse]
    safety_health_score: int  # 0 to 100
    ai_safety_advisory: str

# --- AI Workflows ---
class AIIncidentAssistanceRequest(BaseModel):
    raw_text: str = Field(..., min_length=3, max_length=4000)
    incident_type: Optional[str] = None
    location_address: Optional[str] = None
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
