import logging
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.core.config import settings
from backend.app.core.security import get_password_hash
from backend.app.models.entities import (
    Base, User, Responder, TrustedContact, Incident, IncidentStatusHistory,
    ChildJourney, ElderCheckIn, AssistanceRequest, CommunityHazard
)

logger = logging.getLogger("neighbourhood_safety.sqlite")

def init_sqlite():
    db_url = settings.DATABASE_URL
    logger.info(f"Connecting to SQLite database at {db_url}")
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Auto-seed initial demo data if empty
    session = SessionLocal()
    try:
        seed_data(session)
    finally:
        session.close()
        
    return engine, SessionLocal

def seed_data(session):
    if session.query(User).first() is not None:
        logger.info("Database already seeded with demo records.")
        return

    logger.info("Seeding realistic civic safety demo records into database...")

    # Default password: "Password123!"
    pw_hash = get_password_hash("Password123!")

    # 1. Residents
    resident1 = User(
        email="resident@neighbourhood.org",
        hashed_password=pw_hash,
        full_name="Priya Sharma",
        phone="+91 98765 43210",
        role="resident",
        is_active=True,
        is_verified=True,
        emergency_notes="Asthma patient, keeps inhaler. Blood group O+",
        address="Flat 402, Oak Ridge Apartments, Green Glen Layout"
    )
    resident2 = User(
        email="maya.sen@neighbourhood.org",
        hashed_password=pw_hash,
        full_name="Maya Sen",
        phone="+91 98765 43211",
        role="resident",
        is_active=True,
        is_verified=True,
        emergency_notes="Mother of 10-year-old child Aarav",
        address="House 18, Sunset Boulevard, Sector 4"
    )
    elder_user = User(
        email="elder.ramesh@neighbourhood.org",
        hashed_password=pw_hash,
        full_name="Col. Ramesh Varma (Retd)",
        phone="+91 98765 43212",
        role="resident",
        is_active=True,
        is_verified=True,
        emergency_notes="Senior citizen (76 yrs), mobility assistance required, hypertensive",
        address="Villa 7, Pine Wood Enclave"
    )

    # 2. Responders
    responder_user1 = User(
        email="responder@neighbourhood.org",
        hashed_password=pw_hash,
        full_name="Inspector Vikram Joshi",
        phone="+91 98765 43220",
        role="responder",
        is_active=True,
        is_verified=True,
        emergency_notes="Trained in First Aid & Tactical Community Response",
        address="Sector 4 Police Assistance Booth"
    )
    responder_user2 = User(
        email="medic.anita@neighbourhood.org",
        hashed_password=pw_hash,
        full_name="Dr. Anita Desai",
        phone="+91 98765 43221",
        role="responder",
        is_active=True,
        is_verified=True,
        emergency_notes="Paramedic & General Physician",
        address="Civic Health Clinic, Block B"
    )

    # 3. Administrator
    admin_user = User(
        email="admin@neighbourhood.org",
        hashed_password=pw_hash,
        full_name="Civic Safety Council Admin",
        phone="+91 98765 43299",
        role="admin",
        is_active=True,
        is_verified=True,
        address="Neighbourhood Command & Operations Center"
    )

    session.add_all([resident1, resident2, elder_user, responder_user1, responder_user2, admin_user])
    session.commit()

    # Responder Profiles
    resp_prof1 = Responder(
        user_id=responder_user1.id,
        badge_number="CP-704",
        service_type="security",
        is_available=True,
        current_lat=12.9716,
        current_lng=77.5946,
        rating=4.9,
        is_verified_by_admin=True
    )
    resp_prof2 = Responder(
        user_id=responder_user2.id,
        badge_number="MED-102",
        service_type="medical",
        is_available=True,
        current_lat=12.9725,
        current_lng=77.5980,
        rating=5.0,
        is_verified_by_admin=True
    )
    session.add_all([resp_prof1, resp_prof2])
    session.commit()

    # Trusted Contacts for Priya Sharma
    tc1 = TrustedContact(
        user_id=resident1.id,
        name="Rohit Sharma",
        relationship="Brother",
        phone="+91 98765 99991",
        email="rohit.sharma@example.com",
        can_receive_sos=True,
        can_track_location=True
    )
    tc2 = TrustedContact(
        user_id=resident1.id,
        name="Kavita Rao",
        relationship="Neighbor",
        phone="+91 98765 99992",
        email="kavita.rao@example.com",
        can_receive_sos=True,
        can_track_location=True
    )
    session.add_all([tc1, tc2])

    # Child Journey for Maya Sen
    now = datetime.datetime.utcnow()
    cj = ChildJourney(
        guardian_id=resident2.id,
        child_name="Aarav Sen (Age 10)",
        origin="St. Xavier's Academy, Sector 2",
        destination="House 18, Sunset Boulevard, Sector 4",
        expected_arrival_time=now + datetime.timedelta(minutes=45),
        status="active",
        last_check_in=now - datetime.timedelta(minutes=10),
        notes="School bus route #14. Traveling with companion Aryan."
    )
    session.add(cj)

    # Elder Care Check-in for Col. Ramesh Varma
    elder_check = ElderCheckIn(
        user_id=elder_user.id,
        scheduled_time=now,
        checked_in_at=now - datetime.timedelta(minutes=30),
        status="completed",
        wellness_status="good",
        notes="Morning wellness check completed. Took blood pressure medication on time."
    )
    elder_assistance = AssistanceRequest(
        user_id=elder_user.id,
        request_type="medicine",
        description="Prescription refill required from Apollo Pharmacy (Amlodipine 5mg).",
        urgency="medium",
        status="assigned",
        assigned_to_id=responder_user2.id
    )
    session.add_all([elder_check, elder_assistance])

    # Community Hazards
    hazard1 = CommunityHazard(
        reported_by_id=resident1.id,
        title="Malfunctioning Streetlight Near Park Alley",
        hazard_type="dark_street",
        severity="medium",
        latitude=12.9730,
        longitude=77.5960,
        address="Lane 3, Behind Central Community Park",
        status="verified",
        verified_at=now - datetime.timedelta(hours=2)
    )
    hazard2 = CommunityHazard(
        reported_by_id=resident2.id,
        title="Open Construction Pit Without Barricade",
        hazard_type="road_block",
        severity="high",
        latitude=12.9705,
        longitude=77.5920,
        address="Corner of 7th Cross and Outer Ring Feeder",
        status="active"
    )
    session.add_all([hazard1, hazard2])

    # Seed an initial incident
    inc1 = Incident(
        reference_code="INC-202611-001",
        reporter_id=resident1.id,
        title="Unidentified individual loitering near apartment basement",
        description="Observed a masked person attempting door handles of parked cars in Basement 2.",
        incident_type="suspicious_activity",
        priority="P2_HIGH",
        status="acknowledged",
        location_address="Oak Ridge Apartments, Basement 2, Green Glen Layout",
        latitude=12.9718,
        longitude=77.5950,
        assigned_responder_id=responder_user1.id,
        created_at=now - datetime.timedelta(minutes=25)
    )
    session.add(inc1)
    session.commit()

    hist1 = IncidentStatusHistory(
        incident_id=inc1.id,
        status="reported",
        notes="Incident reported via resident mobile application.",
        updated_by_id=resident1.id,
        created_at=now - datetime.timedelta(minutes=25)
    )
    hist2 = IncidentStatusHistory(
        incident_id=inc1.id,
        status="acknowledged",
        notes="Inspector Vikram Joshi acknowledged and assigned community patrol unit.",
        updated_by_id=responder_user1.id,
        created_at=now - datetime.timedelta(minutes=18)
    )
    session.add_all([hist1, hist2])
    session.commit()
    logger.info("Demo seeding completed successfully.")
