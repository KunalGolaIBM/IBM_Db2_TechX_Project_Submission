from fastapi import APIRouter
from ..database import db_manager

router = APIRouter(tags=["Dashboard"])

@router.get("/dashboard/summary")
def get_dashboard_summary():
    """Returns high-level SOC metrics, recent events, alerts, and incidents."""
    metrics = db_manager.get_metrics()
    recent_events = db_manager.get_events(limit=5)
    recent_alerts = db_manager.get_alerts(limit=5)
    recent_incidents = db_manager.get_incidents(limit=5)
    pending_approvals = db_manager.get_approvals(limit=5)
    db_status = db_manager.get_status()

    # Calculate severity breakdown
    alerts = db_manager.get_alerts(limit=200)
    sev_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    for a in alerts:
        s = a.get("severity", "LOW").upper()
        if s in sev_counts:
            sev_counts[s] += 1

    return {
        "metrics": metrics,
        "database_status": db_status,
        "severity_distribution": [
            {"name": "Low", "value": sev_counts["LOW"], "color": "#42BE65"},
            {"name": "Medium", "value": sev_counts["MEDIUM"], "color": "#F1C21B"},
            {"name": "High", "value": sev_counts["HIGH"], "color": "#FA4D56"},
            {"name": "Critical", "value": sev_counts["CRITICAL"], "color": "#DA1E28"}
        ],
        "recent_events": recent_events,
        "recent_alerts": recent_alerts,
        "recent_incidents": recent_incidents,
        "pending_approvals": pending_approvals
    }
