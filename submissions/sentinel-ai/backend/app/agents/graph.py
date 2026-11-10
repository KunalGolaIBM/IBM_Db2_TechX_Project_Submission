import uuid
import datetime
import json
import logging
from langgraph.graph import StateGraph, START, END
from app.agents.state import SentinelAgentState
from app.agents.event_monitoring_agent import event_monitoring_agent
from app.agents.behaviour_analysis_agent import behaviour_analysis_agent
from app.agents.threat_intelligence_agent import threat_intelligence_agent
from app.agents.risk_assessment_agent import risk_assessment_agent
from app.agents.incident_response_agent import incident_response_agent
from app.database.db2_connector import db_connector

logger = logging.getLogger("sentinel.graph")

def create_sentinel_graph():
    """Builds and compiles the 5-agent LangGraph orchestration workflow."""
    workflow = StateGraph(SentinelAgentState)

    # Add 5 specialized agent nodes
    workflow.add_node("event_monitoring", event_monitoring_agent)
    workflow.add_node("behaviour_analysis", behaviour_analysis_agent)
    workflow.add_node("threat_intelligence", threat_intelligence_agent)
    workflow.add_node("risk_assessment", risk_assessment_agent)
    workflow.add_node("incident_response", incident_response_agent)

    # Define linear sequential coordination edges
    workflow.add_edge(START, "event_monitoring")
    workflow.add_edge("event_monitoring", "behaviour_analysis")
    workflow.add_edge("behaviour_analysis", "threat_intelligence")
    workflow.add_edge("threat_intelligence", "risk_assessment")
    workflow.add_edge("risk_assessment", "incident_response")
    workflow.add_edge("incident_response", END)

    return workflow.compile()

# Pre-compile the graph
sentinel_orchestrator = create_sentinel_graph()

def run_agentic_investigation(user_id: str, lookback_hours: int = 24, existing_incident_id: str = None) -> SentinelAgentState:
    """Executes the full 5-agent LangGraph pipeline and persists results into IBM Db2."""
    incident_id = existing_incident_id or f"INC-{uuid.uuid4().hex[:8].upper()}"
    
    initial_state: SentinelAgentState = {
        "incident_id": incident_id,
        "user_id": user_id,
        "user_account": {},
        "lookback_hours": lookback_hours,
        "raw_logins": [],
        "raw_accesses": [],
        "event_monitoring_findings": {},
        "behaviour_analysis_findings": {},
        "threat_intel_findings": {},
        "risk_assessment_findings": {},
        "incident_response_findings": {},
        "agent_execution_logs": [],
        "status": "RUNNING"
    }

    # Execute LangGraph workflow
    final_state = sentinel_orchestrator.invoke(initial_state)

    # Persist the final incident and AI analyses to IBM Db2
    persist_investigation_results(final_state)

    return final_state

def persist_investigation_results(state: SentinelAgentState):
    """Saves generated Incident, AI Analysis rows, and Response Recommendations to IBM Db2."""
    try:
        incident_id = state.get("incident_id")
        user_id = state.get("user_id")
        user_acc = state.get("user_account", {})
        risk = state.get("risk_assessment_findings", {})
        threat = state.get("threat_intel_findings", {})
        response = state.get("incident_response_findings", {})
        now_iso = datetime.datetime.now().isoformat()

        severity = risk.get("severity", "MEDIUM")
        risk_score = risk.get("risk_score", 50)
        technique_ids = json.dumps(threat.get("technique_ids", []))
        title = f"Suspicious Activity Correlation - {user_acc.get('full_name', user_id)}"
        summary = risk.get("summary", "Automated multi-agent correlation completed.")

        # 1. Save or Update INCIDENTS table
        existing = db_connector.execute_query("SELECT incident_id FROM INCIDENTS WHERE incident_id = ?", (incident_id,))
        if existing:
            db_connector.execute_update(
                """UPDATE INCIDENTS 
                   SET severity = ?, risk_score = ?, mitre_technique_ids = ?, summary = ?, updated_at = ?
                   WHERE incident_id = ?""",
                (severity, risk_score, technique_ids, summary, now_iso, incident_id)
            )
        else:
            db_connector.execute_update(
                """INSERT INTO INCIDENTS (incident_id, title, user_id, status, severity, risk_score, mitre_technique_ids, summary, created_at, updated_at)
                   VALUES (?, ?, ?, 'INVESTIGATING', ?, ?, ?, ?, ?, ?)""",
                (incident_id, title, user_id, severity, risk_score, technique_ids, summary, now_iso, now_iso)
            )

        # 2. Save 5 records to AI_ANALYSIS table
        agent_findings = [
            ("Agent 1: Event Monitoring Agent", "AUTHENTICATION_VELOCITY", state.get("event_monitoring_findings", {}), 0.95),
            ("Agent 2: Behaviour Analysis Agent", "BEHAVIORAL_BASELINE_DEVIATION", state.get("behaviour_analysis_findings", {}), 0.92),
            ("Agent 3: Threat Intelligence Agent", "MITRE_ATTACK_MAPPING", state.get("threat_intel_findings", {}), 0.90),
            ("Agent 4: Risk Assessment Agent", "EXPLAINABLE_RISK_SCORING", state.get("risk_assessment_findings", {}), 0.94),
            ("Agent 5: Incident Response Agent", "DEFENSIVE_PLAYBOOK_GENERATION", state.get("incident_response_findings", {}), 0.93),
        ]

        # Clear prior analysis for this incident if re-running
        db_connector.execute_update("DELETE FROM AI_ANALYSIS WHERE incident_id = ?", (incident_id,))

        for agent_name, a_type, data, confidence in agent_findings:
            analysis_id = f"ANL-{uuid.uuid4().hex[:8].upper()}"
            findings_text = data.get("summary", "")
            reasoning_text = json.dumps(data)
            db_connector.execute_update(
                """INSERT INTO AI_ANALYSIS (analysis_id, incident_id, agent_name, analysis_type, findings, reasoning, confidence_score, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (analysis_id, incident_id, agent_name, a_type, findings_text, reasoning_text, confidence, now_iso)
            )

        # 3. Save recommendations to RESPONSE_RECOMMENDATIONS table
        # Delete prior recommendations for this incident if re-running
        db_connector.execute_update("DELETE FROM RESPONSE_RECOMMENDATIONS WHERE incident_id = ?", (incident_id,))

        for action in response.get("recommended_actions", []):
            rec_id = action.get("recommendation_id", f"REC-{uuid.uuid4().hex[:8].upper()}")
            db_connector.execute_update(
                """INSERT INTO RESPONSE_RECOMMENDATIONS (recommendation_id, incident_id, action_type, description, status, created_at)
                   VALUES (?, ?, ?, ?, 'PENDING_APPROVAL', ?)""",
                (rec_id, incident_id, action.get("action_type"), action.get("description"), now_iso)
            )

        logger.info(f"Successfully saved LangGraph analysis to IBM Db2 for incident {incident_id}.")
    except Exception as e:
        logger.error(f"Error persisting investigation results to IBM Db2: {e}")

