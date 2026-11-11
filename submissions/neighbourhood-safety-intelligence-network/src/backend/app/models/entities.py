import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey, Enum
)
from sqlalchemy.orm import declarative_base, relationship as sa_relationship

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)
    role = Column(String(50), default="resident", nullable=False)  # resident, responder, admin, guardian
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    emergency_notes = Column(Text, nullable=True)
    address = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    trusted_contacts = sa_relationship("TrustedContact", back_populates="user", cascade="all, delete-orphan")
    reported_incidents = sa_relationship("Incident", back_populates="reporter", foreign_keys="Incident.reporter_id")
    assigned_incidents = sa_relationship("Incident", back_populates="assigned_responder", foreign_keys="Incident.assigned_responder_id")
    responder_profile = sa_relationship("Responder", back_populates="user", uselist=False)
    child_journeys = sa_relationship("ChildJourney", back_populates="guardian")
    elder_checkins = sa_relationship("ElderCheckIn", back_populates="user")
    assistance_requests = sa_relationship("AssistanceRequest", back_populates="user", foreign_keys="AssistanceRequest.user_id")

class TrustedContact(Base):
    __tablename__ = "trusted_contacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    relationship = Column(String(100), nullable=False)
    phone = Column(String(50), nullable=False)
    email = Column(String(255), nullable=True)
    can_receive_sos = Column(Boolean, default=True)
    can_track_location = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = sa_relationship("User", back_populates="trusted_contacts")

class Responder(Base):
    __tablename__ = "responders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    badge_number = Column(String(100), nullable=False)
    service_type = Column(String(100), default="community_patrol")  # medical, security, fire, community_patrol
    is_available = Column(Boolean, default=True)
    current_lat = Column(Float, nullable=True)
    current_lng = Column(Float, nullable=True)
    rating = Column(Float, default=5.0)
    is_verified_by_admin = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = sa_relationship("User", back_populates="responder_profile")

class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reference_code = Column(String(50), unique=True, nullable=False)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    incident_type = Column(String(50), default="sos", nullable=False)  # sos, hazard, medical, child_alert, elder_welfare, suspicious_activity
    priority = Column(String(50), default="P1_CRITICAL", nullable=False)  # P1_CRITICAL, P2_HIGH, P3_MODERATE, P4_ADVISORY
    status = Column(String(50), default="reported", nullable=False)  # reported, acknowledged, responder_en_route, on_scene, resolving, resolved, false_alarm
    location_address = Column(String(255), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    assigned_responder_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    reporter = sa_relationship("User", back_populates="reported_incidents", foreign_keys=[reporter_id])
    assigned_responder = sa_relationship("User", back_populates="assigned_incidents", foreign_keys=[assigned_responder_id])
    status_history = sa_relationship("IncidentStatusHistory", back_populates="incident", cascade="all, delete-orphan", order_by="IncidentStatusHistory.created_at.desc()")
    location_events = sa_relationship("LocationEvent", back_populates="incident", cascade="all, delete-orphan")
    ai_analysis = sa_relationship("AIAnalysisRecord", back_populates="incident", uselist=False)

class IncidentStatusHistory(Base):
    __tablename__ = "incident_status_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False, index=True)
    status = Column(String(50), nullable=False)
    notes = Column(Text, nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    incident = sa_relationship("Incident", back_populates="status_history")
    updated_by = sa_relationship("User")

class LocationEvent(Base):
    __tablename__ = "location_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    accuracy = Column(Float, nullable=True)
    event_type = Column(String(50), default="sos_ping")
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    incident = sa_relationship("Incident", back_populates="location_events")
    user = sa_relationship("User")

class ChildJourney(Base):
    __tablename__ = "child_journeys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    guardian_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    child_name = Column(String(255), nullable=False)
    origin = Column(String(255), nullable=False)
    destination = Column(String(255), nullable=False)
    expected_arrival_time = Column(DateTime, nullable=False)
    actual_arrival_time = Column(DateTime, nullable=True)
    status = Column(String(50), default="active", nullable=False)  # active, completed, delayed, alert_triggered
    last_check_in = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    guardian = sa_relationship("User", back_populates="child_journeys")

class ElderCheckIn(Base):
    __tablename__ = "elder_checkins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    scheduled_time = Column(DateTime, nullable=False)
    checked_in_at = Column(DateTime, nullable=True)
    status = Column(String(50), default="pending", nullable=False)  # pending, completed, missed, flagged
    wellness_status = Column(String(50), default="good", nullable=False)  # good, needs_assistance, emergency
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = sa_relationship("User", back_populates="elder_checkins")

class AssistanceRequest(Base):
    __tablename__ = "assistance_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    request_type = Column(String(100), default="grocery")  # grocery, medicine, mobility, check_in, urgent
    description = Column(Text, nullable=False)
    urgency = Column(String(50), default="medium")  # low, medium, high
    status = Column(String(50), default="open")  # open, assigned, in_progress, completed
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    user = sa_relationship("User", back_populates="assistance_requests", foreign_keys=[user_id])
    assigned_to = sa_relationship("User", foreign_keys=[assigned_to_id])

class CommunityHazard(Base):
    __tablename__ = "community_hazards"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reported_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    hazard_type = Column(String(100), nullable=False)  # dark_street, road_block, aggressive_animals, electrical, flooding
    severity = Column(String(50), default="medium")  # low, medium, high
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    address = Column(String(255), nullable=False)
    status = Column(String(50), default="active")  # active, verified, resolved
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    reported_by = sa_relationship("User")

class AIAnalysisRecord(Base):
    __tablename__ = "ai_analysis_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False, unique=True)
    intake_summary = Column(Text, nullable=False)
    suggested_priority = Column(String(50), nullable=False)
    triage_reasoning = Column(Text, nullable=False)
    recommended_actions_json = Column(Text, nullable=False)
    retrieved_protocols_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    incident = sa_relationship("Incident", back_populates="ai_analysis")

class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(String(100), nullable=True)
    ip_address = Column(String(50), nullable=True)
    details_json = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
