import json
from typing import Optional
from fastapi import APIRouter, HTTPException
from app.database.db2_connector import db_connector
from app.agents.graph import run_agentic_investigation
from app.services.attack_simulator import simulate_multi_vector_compromise
from app.models.schemas import InvestigateRequest, AttackSimulateRequest

router = APIRouter(prefix="/incidents", tags=["Incidents"])

@router.get("")
def list_incidents():
    query = """
        SELECT i.*, u.full_name, u.email, u.department, u.security_clearance 
        FROM INCIDENTS i
        LEFT JOIN USER_ACCOUNTS u ON i.user_id = u.user_id
        ORDER BY i.created_at DESC
    """
    rows = db_connector.execute_query(query)
    for r in rows:
        if r.get("mitre_technique_ids"):
            try:
                r["mitre_technique_ids"] = json.loads(r["mitre_technique_ids"])
            except Exception:
                pass
    return rows

@router.get("/{incident_id}")
def get_incident_details(incident_id: str):
    inc_rows = db_connector.execute_query(
        """SELECT i.*, u.full_name, u.email, u.department, u.security_clearance, u.role
           FROM INCIDENTS i
           LEFT JOIN USER_ACCOUNTS u ON i.user_id = u.user_id
           WHERE i.incident_id = ?""",
        (incident_id,)
    )
    if not inc_rows:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident = inc_rows[0]
    if incident.get("mitre_technique_ids"):
        try:
            incident["mitre_technique_ids"] = json.loads(incident["mitre_technique_ids"])
        except Exception:
            pass

    # Retrieve 5 AI_ANALYSIS records
    analyses = db_connector.execute_query(
        "SELECT * FROM AI_ANALYSIS WHERE incident_id = ? ORDER BY analysis_id ASC",
        (incident_id,)
    )
    for a in analyses:
        if a.get("reasoning"):
            try:
                a["parsed_reasoning"] = json.loads(a["reasoning"])
            except Exception:
                pass

    # Retrieve Recommendations
    recommendations = db_connector.execute_query(
        "SELECT * FROM RESPONSE_RECOMMENDATIONS WHERE incident_id = ? ORDER BY created_at ASC",
        (incident_id,)
    )

    # Retrieve correlated alerts or recent logins for target user
    user_id = incident.get("user_id")
    recent_logins = db_connector.execute_query(
        "SELECT * FROM LOGIN_EVENTS WHERE user_id = ? ORDER BY timestamp DESC LIMIT 20",
        (user_id,)
    )
    recent_accesses = db_connector.execute_query(
        "SELECT * FROM ACCESS_LOGS WHERE user_id = ? ORDER BY timestamp DESC LIMIT 20",
        (user_id,)
    )

    return {
        "incident": incident,
        "analyses": analyses,
        "recommendations": recommendations,
        "recent_logins": recent_logins,
        "recent_accesses": recent_accesses
    }

@router.post("/investigate")
def investigate_account(req: InvestigateRequest):
    """Executes the 5 LangGraph AI agents to investigate a target account."""
    final_state = run_agentic_investigation(user_id=req.user_id, lookback_hours=req.lookback_hours or 24)
    return {
        "incident_id": final_state.get("incident_id"),
        "severity": final_state.get("risk_assessment_findings", {}).get("severity"),
        "risk_score": final_state.get("risk_assessment_findings", {}).get("risk_score"),
        "agent_logs": final_state.get("agent_execution_logs"),
        "recommendations": final_state.get("incident_response_findings", {}).get("recommended_actions")
    }

@router.post("/simulate-attack")
def trigger_attack_simulation(req: AttackSimulateRequest):
    """Triggers the Section 8 Attack Scenario: Brute force + unfamiliar device + classified warplan access."""
    result = simulate_multi_vector_compromise(target_user_id=req.target_user_id or "USR-101")
    return result

@router.get("/{incident_id}/report")
def get_incident_report(incident_id: str):
    inc_details = get_incident_details(incident_id)
    # Check if there is an AI_ANALYSIS record from Incident Response Agent
    for a in inc_details.get("analyses", []):
        if "Incident Response" in a.get("agent_name", ""):
            parsed = a.get("parsed_reasoning", {})
            report_md = parsed.get("incident_report_markdown")
            if report_md:
                return {"incident_id": incident_id, "markdown": report_md}

    return {
        "incident_id": incident_id,
        "markdown": f"# Incident Report {incident_id}\n\nSummary: {inc_details['incident'].get('summary')}"
    }

