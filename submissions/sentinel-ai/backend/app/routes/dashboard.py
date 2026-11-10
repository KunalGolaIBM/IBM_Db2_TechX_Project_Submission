from fastapi import APIRouter
from app.database.db2_connector import db_connector
from app.services.watsonx_service import watsonx_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/stats")
def get_dashboard_stats():
    # 1. Total events
    logins_res = db_connector.execute_query("SELECT COUNT(*) as cnt FROM LOGIN_EVENTS")
    total_logins = logins_res[0].get("cnt", 0) if logins_res else 0

    succ_res = db_connector.execute_query("SELECT COUNT(*) as cnt FROM LOGIN_EVENTS WHERE status = 'SUCCESS'")
    succ_logins = succ_res[0].get("cnt", 0) if succ_res else 0

    fail_res = db_connector.execute_query("SELECT COUNT(*) as cnt FROM LOGIN_EVENTS WHERE status = 'FAILURE'")
    fail_logins = fail_res[0].get("cnt", 0) if fail_res else 0

    access_res = db_connector.execute_query("SELECT COUNT(*) as cnt FROM ACCESS_LOGS")
    total_access = access_res[0].get("cnt", 0) if access_res else 0

    total_events = total_logins + total_access

    # 2. Suspicious activity alerts
    alerts_res = db_connector.execute_query("SELECT COUNT(*) as cnt FROM SECURITY_ALERTS WHERE status = 'OPEN'")
    suspicious_alerts = alerts_res[0].get("cnt", 0) if alerts_res else 0

    # 3. Incidents
    inc_res = db_connector.execute_query("SELECT COUNT(*) as cnt FROM INCIDENTS")
    active_incidents = inc_res[0].get("cnt", 0) if inc_res else 0

    # Severity counts
    severity_breakdown = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    sev_rows = db_connector.execute_query("SELECT severity, COUNT(*) as cnt FROM INCIDENTS GROUP BY severity")
    for r in sev_rows:
        sev = r.get("severity", "").upper()
        if sev in severity_breakdown:
            severity_breakdown[sev] = r.get("cnt", 0)

    # 4. Pending Approvals
    rec_res = db_connector.execute_query("SELECT COUNT(*) as cnt FROM RESPONSE_RECOMMENDATIONS WHERE status = 'PENDING_APPROVAL'")
    pending_approvals = rec_res[0].get("cnt", 0) if rec_res else 0

    # 5. System Status
    db_status = db_connector.get_status()
    ai_status = watsonx_service.get_status()

    return {
        "total_events": total_events,
        "successful_logins": succ_logins,
        "failed_logins": fail_logins,
        "resource_access_events": total_access,
        "suspicious_activities": suspicious_alerts,
        "active_incidents": active_incidents,
        "pending_approvals": pending_approvals,
        "severity_breakdown": severity_breakdown,
        "system_status": {
            "database": db_status,
            "ai_engine": ai_status,
            "orchestrator": {
                "framework": "LangGraph 1.2 Multi-Agent Orchestrator",
                "agents_active": 5,
                "status": "ONLINE"
            }
        }
    }

