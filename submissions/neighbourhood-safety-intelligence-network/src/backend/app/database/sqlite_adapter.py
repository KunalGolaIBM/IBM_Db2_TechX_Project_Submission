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
    inc1.reference_code = f"INC-{inc1.created_at:%Y%m}-{inc1.id:05d}"
    session.commit()

    _seed_incident_history(session, now, {
        "priya": resident1, "maya": resident2, "ramesh": elder_user,
        "vikram": responder_user1, "anita": responder_user2,
    })
    logger.info("Demo seeding completed successfully.")


# A deterministic 30-day history so analytics, hotspots and related-report search have real data
# from the first start. Each row: days ago, hour, reporter, responder, title, description, type,
# priority, location, minutes to acknowledge (None = still unacknowledged), minutes to resolve.
HISTORY = [
    (27, 21, "priya", "vikram", "Streetlight out behind the park",
     "The streetlight on Lane 3 behind the community park is not working and the lane is completely dark at night.",
     "hazard", "P3_MODERATE", "Lane 3, Behind Central Community Park", 22, 1440),
    (26, 22, "maya", "vikram", "Lane 3 lamp not working",
     "Street lamp near the park on Lane 3 is still off, the whole lane is pitch dark after sunset.",
     "hazard", "P3_MODERATE", "Lane 3, Behind Central Community Park", 35, 1300),
    (24, 23, "priya", "vikram", "Man following women near park lane",
     "A man has been following women walking alone on the dark lane behind the park late at night.",
     "suspicious_activity", "P2_HIGH", "Lane 3, Behind Central Community Park", 7, 95),
    (22, 9, "ramesh", "anita", "Fell in the bathroom",
     "I slipped in the bathroom and hurt my hip, I cannot get up on my own.",
     "medical", "P1_CRITICAL", "Flat 12, Shanti Senior Residency", 1.5, 70),
    (20, 18, "maya", "anita", "Child not back from tuition",
     "My daughter has not returned from tuition, she is 40 minutes late and not answering her phone.",
     "child_alert", "P2_HIGH", "Bright Minds Tuition Centre, 5th Main", 4, 55),
    (18, 22, "priya", "vikram", "Masked men checking car doors",
     "Two masked men were trying the door handles of parked cars in the basement.",
     "suspicious_activity", "P2_HIGH", "Oak Ridge Apartments, Basement 2, Green Glen Layout", 9, 120),
    (15, 7, "ramesh", "anita", "Missed medicine delivery",
     "My blood pressure medicine delivery did not arrive and I have only one day left.",
     "elder_welfare", "P3_MODERATE", "Flat 12, Shanti Senior Residency", 40, 300),
    (13, 20, "maya", "vikram", "Open pit without barricade",
     "There is an open construction pit on the corner with no barricade or light; a scooter nearly fell in.",
     "hazard", "P2_HIGH", "Corner of 7th Cross and Outer Ring Feeder", 12, 2880),
    (11, 23, "priya", "vikram", "Basement gate left open at night",
     "The basement gate was left open again after midnight and strangers walked in.",
     "suspicious_activity", "P3_MODERATE", "Oak Ridge Apartments, Basement 2, Green Glen Layout", 28, 240),
    (9, 13, "ramesh", "anita", "Neighbour fainted in the lift",
     "An elderly neighbour fainted in the lift and is breathing but not responding properly.",
     "medical", "P1_CRITICAL", "Shanti Senior Residency, Block A Lift", 2, 60),
    (6, 19, "maya", "vikram", "Waterlogging after rain",
     "Heavy rain has flooded the underpass and two-wheelers are getting stuck.",
     "hazard", "P3_MODERATE", "Corner of 7th Cross and Outer Ring Feeder", 50, 600),
    (4, 22, "priya", "vikram", "Suspicious van parked for hours",
     "A van without number plates has been parked near the basement entrance since evening.",
     "suspicious_activity", "P3_MODERATE", "Oak Ridge Apartments, Basement 2, Green Glen Layout", 18, None),
    (2, 8, "ramesh", "anita", "Elderly resident not answering door",
     "My neighbour Mrs. Rao has not answered her door or phone since yesterday evening.",
     "elder_welfare", "P2_HIGH", "Flat 14, Shanti Senior Residency", 6, 45),
    (0, None, "maya", None, "Stray dogs chasing children",
     "A pack of stray dogs is chasing children near the school bus stop every morning.",
     "hazard", "P3_MODERATE", "School Bus Stop, 5th Main", None, None),
]


def _seed_incident_history(session, now, people):
    for (days, hour, reporter, responder, title, description, inc_type, priority, place,
         ack_min, resolve_min) in HISTORY:
        created = (now - datetime.timedelta(days=days, minutes=90)) if hour is None else \
            (now - datetime.timedelta(days=days)).replace(hour=hour, minute=15, second=0, microsecond=0)
        status = "reported" if ack_min is None else ("resolved" if resolve_min else "acknowledged")
        inc = Incident(
            reference_code=f"SEED-{days}-{len(title)}-{hour}",
            reporter_id=people[reporter].id,
            title=title,
            description=description,
            incident_type=inc_type,
            priority=priority,
            status=status,
            location_address=place,
            assigned_responder_id=people[responder].id if responder and ack_min is not None else None,
            created_at=created,
            updated_at=created,
        )
        session.add(inc)
        session.flush()
        inc.reference_code = f"INC-{created:%Y%m}-{inc.id:05d}"

        timeline = [("reported", 0, people[reporter], "Report submitted by resident.")]
        if ack_min is not None:
            timeline.append(("acknowledged", ack_min, people[responder], "Responder acknowledged and is coordinating."))
        if resolve_min:
            timeline.append(("on_scene", ack_min + max(3, resolve_min * 0.3), people[responder], "Responder on scene."))
            timeline.append(("resolved", resolve_min, people[responder], "Resolved and verified with the resident."))
            inc.resolved_at = created + datetime.timedelta(minutes=resolve_min)
        for state, minutes, user, notes in timeline:
            at = created + datetime.timedelta(minutes=minutes)
            session.add(IncidentStatusHistory(incident_id=inc.id, status=state, notes=notes,
                                              updated_by_id=user.id, created_at=at))
            inc.updated_at = at
    session.commit()
