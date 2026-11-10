from fastapi import APIRouter
from ..database import db_manager
from ..services.detection_service import DetectionEngine

router = APIRouter(tags=["Demonstration Controller"])

@router.post("/demo/generate-events")
def generate_demo_events():
    """Generates controlled baseline and simulated attack telemetry in IBM Db2."""
    db_manager.seed_demo_data()
    return {
        "message": "Generated controlled baseline and simulated security attack telemetry.",
        "events_count": len(db_manager.get_events(limit=50))
    }

@router.post("/demo/run-detection")
def run_demo_detection():
    """Executes the detection engine and creates correlated incidents."""
    engine = DetectionEngine(db_manager)
    alerts = engine.run_detection()

    # Automatically create an incident for high-severity alerts
    high_alerts = [a for a in alerts if a.get("severity") in ("HIGH", "CRITICAL")]
    inc_id = None
    if high_alerts:
        inc_id = f"INC-2026-0884"
        max_score = max(a.get("risk_score", 50.0) for a in high_alerts)
        db_manager.insert_incident({
            "incident_id": inc_id,
            "title": "Compromised Account: Suspicious Off-Hours Financial Data Exfiltration",
            "description": f"Detected multi-stage attack sequence: off-hours login, sensitive table access (28,400 rows), and catalog reconnaissance.",
            "severity": "CRITICAL" if max_score >= 75 else "HIGH",
            "risk_score": max_score,
            "status": "INVESTIGATING",
            "assigned_to": "REPORT_USER"
        })

    return {
        "message": f"Detection engine executed; created {len(alerts)} alerts.",
        "alerts_created": len(alerts),
        "incident_created": inc_id
    }

@router.post("/demo/reset")
def reset_demo():
    """Clears all demonstration telemetry and resets the database."""
    db_manager.reset_demo_data()
    return {"message": "Demonstration database reset successfully."}
