from fastapi import APIRouter, HTTPException, Query
from ..database import db_manager
try:
    from src.workflows.security_workflow import execute_incident_investigation
except ImportError:
    from ...workflows.security_workflow import execute_incident_investigation

router = APIRouter(tags=["Security Incidents"])

@router.get("/incidents")
def list_incidents(
    limit: int = 50,
    offset: int = 0
):
    """Retrieves security incidents and their investigation statuses."""
    limit_val = int(getattr(limit, "default", limit)) if not isinstance(limit, int) else limit
    offset_val = int(getattr(offset, "default", offset)) if not isinstance(offset, int) else offset
    incidents = db_manager.get_incidents(limit=limit_val, offset=offset_val)
    return {"count": len(incidents), "incidents": incidents}

@router.get("/incidents/{incident_id}")
def get_incident(incident_id: str):
    """Retrieves a single incident along with its agent investigation dossier."""
    incident = db_manager.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found")
    investigations = db_manager.get_investigations(incident_id)
    return {
        "incident": incident,
        "investigations": investigations
    }

@router.post("/incidents/{incident_id}/investigate")
def run_investigation(incident_id: str):
    """
    Triggers the LangGraph multi-agent investigation workflow for an incident.
    Orchestrates Detection, Evidence, Investigation, Risk, Response, and Report agents.
    """
    incident = db_manager.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found")

    events = db_manager.get_events(limit=50)
    alerts = db_manager.get_alerts(limit=50)

    # Execute LangGraph Multi-Agent Investigation
    final_state = execute_incident_investigation(
        incident_id=incident_id,
        target_username=incident.get("assigned_to", "REPORT_USER"),
        target_ip="198.51.100.44",
        events=events,
        alerts=alerts
    )

    # Persist findings into Db2
    report_text = final_state["investigation_reports"][-1]["summary"] if final_state.get("investigation_reports") else "Investigation completed."
    db_manager.update_incident(incident_id, {
        "ai_summary": report_text,
        "status": "AWAITING_APPROVAL" if final_state.get("human_approval_required") else "RESOLVED"
    })

    # Record agent investigation findings
    db_manager.insert_investigation({
        "incident_id": incident_id,
        "agent_name": "LangGraph Investigation Team",
        "findings": "\n".join(final_state.get("factual_findings", [])[:5]),
        "recommendation": "\n".join([f"{a['action_type']}: {a['target']}" for a in final_state.get("recommended_actions", [])]),
        "confidence": 0.94
    })

    # Record Human Approval request
    app_id = db_manager.insert_approval({
        "incident_id": incident_id,
        "proposed_action": "TERMINATE SESSION & LOCK COMPROMISED DB2 CREDENTIALS (REPORT_USER)",
        "requested_by": "Response Agent",
        "approval_status": "PENDING"
    })

    db_manager.log_audit("AI_INVESTIGATION_COMPLETED", "LangGraph Supervisor", f"Completed multi-agent triage for {incident_id}")

    return {
        "message": "LangGraph multi-agent investigation completed successfully.",
        "incident_id": incident_id,
        "workflow_status": final_state.get("workflow_status"),
        "approval_id": app_id,
        "risk_evaluation": final_state.get("risk_evaluation"),
        "mitre_tactics": final_state.get("mitre_tactics"),
        "recommended_actions": final_state.get("recommended_actions"),
        "report": report_text
    }
