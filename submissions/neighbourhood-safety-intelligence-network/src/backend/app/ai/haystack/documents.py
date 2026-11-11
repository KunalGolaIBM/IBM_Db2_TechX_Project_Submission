from typing import List, Dict, Any

APPROVED_CIVIC_SAFETY_DOCUMENTS: List[Dict[str, Any]] = [
    {
        "id": "DOC-SOS-001",
        "title": "Community SOS & Personal Distress Protocol",
        "category": "emergency_response",
        "content": (
            "When a resident triggers an emergency SOS, the platform immediately initiates an auditable "
            "incident sequence. 1) Location coordinates are transmitted strictly to designated trusted contacts "
            "and on-duty verified community responders within a 2-kilometer radius. 2) The incident priority is "
            "automatically classified as P1_CRITICAL. 3) Responders are notified with real-time audio-visual alerts "
            "and must acknowledge within 120 seconds. 4) The resident's emergency medical and allergy notes are made "
            "visible only to certified medical responders. 5) Responders must remain in communication with civic dispatch "
            "until on-scene arrival is logged. False alarms must be verified by two-party authentication before closure."
        ),
        "source": "Municipal Civic Safety Standard Operating Procedure v3.2",
        "updated_at": "2026-04-15"
    },
    {
        "id": "DOC-CHILD-002",
        "title": "Child Journey Monitoring and Delay Escalation Guidelines",
        "category": "child_safety",
        "content": (
            "Guardian-monitored child journeys track travel between verified safe waypoints (home, school, activity center). "
            "1) Expected travel times include a calibrated 15-minute buffer. 2) If no check-in is received by expected "
            "arrival time, an automated gentle push reminder is sent to the child profile. 3) At +15 minutes overdue without "
            "communication, the status transitions to 'delayed' and guardians receive an urgent notification. 4) At +30 minutes "
            "overdue or if the route deviates significantly, a P2_HIGH Child Welfare Alert is registered, notifying neighbourhood "
            "patrol units along the registered route corridor. Responders must verify last-known waypoint camera or witness records."
        ),
        "source": "Guardian Network Child Protection Framework, Section 4",
        "updated_at": "2026-05-20"
    },
    {
        "id": "DOC-ELDER-003",
        "title": "Senior Citizen Wellness Checks and Assistance Procedures",
        "category": "elder_care",
        "content": (
            "Elder welfare monitoring operates through morning and evening check-in windows. "
            "1) Residents or their designated caregivers set preferred check-in hours. 2) If a check-in is missed, "
            "the system flags a 'missed_checkin' status and prompts trusted family contacts. 3) If no contact is established "
            "within 60 minutes, a certified community volunteer or medical responder is dispatched for a physical welfare "
            "knock-and-verify. 4) Responders are trained to check for common home hazards, medication continuity, and hydration. "
            "Urgent medical assistance requests take precedence over routine domestic chores."
        ),
        "source": "Civic Elder Care & Ageing-in-Place Guidelines",
        "updated_at": "2026-06-10"
    },
    {
        "id": "DOC-HAZARD-004",
        "title": "Community Hazard Identification, Verification, and Containment",
        "category": "hazard_mitigation",
        "content": (
            "Civic hazards reported by residents (such as broken streetlights, waterlogging, fallen wires, aggressive strays, "
            "or blocked egress routes) are published to the neighbourhood map only after verified or corroborated by at least "
            "two independent residents or one verified patrol responder. Unverified hazards are displayed with a distinct warning badge. "
            "High-severity hazards trigger an automatic detour notification for child journeys and pedestrian routes passing within "
            "200 meters. The community admin escalates unresolved hazards directly to municipal ward engineers."
        ),
        "source": "Urban Safety Task Force Hazard Catalog 2026",
        "updated_at": "2026-07-01"
    },
    {
        "id": "DOC-WOMEN-005",
        "title": "Safe Transit and Women's Night Corridor Policy",
        "category": "transit_safety",
        "content": (
            "Women residents traveling during late hours (10:00 PM to 6:00 AM) can activate 'Safe Transit Companion' mode. "
            "This shares temporary live breadcrumbs exclusively with chosen trusted contacts and nearby active community "
            "patrols. If the user remains stationary in an unlit zone for over 5 minutes, an unobtrusive safety prompt is sent. "
            "If unanswered within 90 seconds, nearby patrollers are notified to conduct a non-intrusive safety drive-by."
        ),
        "source": "Metropolitan Women's Safety Initiative Protocol #11",
        "updated_at": "2026-08-12"
    },
    {
        "id": "DOC-TRIAGE-006",
        "title": "Incident Priority Classification Matrix & Triage Standards",
        "category": "responder_procedures",
        "content": (
            "Incidents must be triaged into four distinct levels: "
            "P1_CRITICAL: Active physical danger, medical emergency, violence, or direct SOS. Requires immediate response (<5 min). "
            "P2_HIGH: Suspicious individuals attempting property entry, aggressive animals, missing child overdue >15m, fire hazards. (<15 min). "
            "P3_MODERATE: Non-violent disputes, street lighting outages, property damage, delayed elder assistance. (<1 hour). "
            "P4_ADVISORY: General safety inquiries, routine maintenance requests, noise complaints. Handled within 24 hours. "
            "AI suggestions are strictly preliminary; responder in-charge makes final classification."
        ),
        "source": "Unified Civic Incident Classification System (UCICS)",
        "updated_at": "2026-09-01"
    }
]
