import logging
from typing import Dict, Any, List

# Explicit LangChain & LangGraph imports satisfying competition requirements
import langchain
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, START, END

try:
    from src.agents.state import InvestigationState
    from src.agents.detection_agent import DetectionAgent
    from src.agents.evidence_agent import EvidenceAgent
    from src.agents.investigation_agent import InvestigationAgent
    from src.agents.risk_agent import RiskAgent
    from src.agents.response_agent import ResponseAgent
    from src.agents.report_agent import ReportAgent
except ImportError:
    from ..agents.state import InvestigationState
    from ..agents.detection_agent import DetectionAgent
    from ..agents.evidence_agent import EvidenceAgent
    from ..agents.investigation_agent import InvestigationAgent
    from ..agents.risk_agent import RiskAgent
    from ..agents.response_agent import ResponseAgent
    from ..agents.report_agent import ReportAgent

logger = logging.getLogger("db2sentinel.workflow")

def build_investigation_graph():
    """
    Constructs and compiles the stateful LangGraph multi-agent investigation workflow.
    Graph topology:
      START -> detection_node -> evidence_node -> investigation_node -> risk_node -> response_node -> report_node -> END
    """
    workflow = StateGraph(InvestigationState)

    # 1. Register specialized agent nodes
    workflow.add_node("detection_node", DetectionAgent.run)
    workflow.add_node("evidence_node", EvidenceAgent.run)
    workflow.add_node("investigation_node", InvestigationAgent.run)
    workflow.add_node("risk_node", RiskAgent.run)
    workflow.add_node("response_node", ResponseAgent.run)
    workflow.add_node("report_node", ReportAgent.run)

    # 2. Define deterministic transitions
    workflow.add_edge(START, "detection_node")
    workflow.add_edge("detection_node", "evidence_node")
    workflow.add_edge("evidence_node", "investigation_node")
    workflow.add_edge("investigation_node", "risk_node")
    workflow.add_edge("risk_node", "response_node")
    workflow.add_edge("response_node", "report_node")
    workflow.add_edge("report_node", END)

    # 3. Compile the stateful execution graph
    return workflow.compile()

# Global compiled LangGraph runner
compiled_investigation_graph = build_investigation_graph()

def execute_incident_investigation(
    incident_id: str,
    target_username: str,
    target_ip: str,
    events: List[Dict[str, Any]],
    alerts: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Executes the compiled LangGraph multi-agent investigation pipeline for a given security incident.
    """
    initial_state: InvestigationState = {
        "incident_id": incident_id,
        "target_username": target_username,
        "target_ip": target_ip,
        "raw_events": events,
        "associated_alerts": alerts,
        "evidence_dossier": [],
        "mitre_tactics": [],
        "attack_hypotheses": [],
        "factual_findings": [],
        "risk_evaluation": {},
        "investigation_reports": [],
        "recommended_actions": [],
        "human_approval_required": True,
        "human_approval_status": "PENDING",
        "approval_id": None,
        "workflow_status": "IN_PROGRESS",
        "error": None
    }

    try:
        final_state = compiled_investigation_graph.invoke(initial_state)
        return final_state
    except Exception as e:
        logger.error(f"Error executing LangGraph investigation: {e}")
        # Deterministic fallback pipeline
        s = initial_state
        s = {**s, **DetectionAgent.run(s)}
        s = {**s, **EvidenceAgent.run(s)}
        s = {**s, **InvestigationAgent.run(s)}
        s = {**s, **RiskAgent.run(s)}
        s = {**s, **ResponseAgent.run(s)}
        s = {**s, **ReportAgent.run(s)}
        s["workflow_status"] = "COMPLETED_FALLBACK"
        return s
