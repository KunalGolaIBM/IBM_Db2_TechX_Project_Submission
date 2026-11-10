
"""LangGraph workflow for ColdChain Guardian.

Workflow:
Monitoring -> Incident -> Risk Assessment -> Recommendation

Normal readings terminate after monitoring.
Failed stages stop further processing.
Each node calls the existing agent's run(state) function.
"""

from __future__ import annotations

from typing import Any, Dict

from langgraph.graph import StateGraph, END

# Import existing agent implementations
from ..agents.monitoring import run as monitoring_run
from ..agents.incident import run as incident_run
from ..agents.risk_assessment import run as risk_run
from ..agents.crew_analysis import run as crew_run
from ..agents.recommendation import run as recommendation_run

from .state import WorkflowState


# ---------------------------------------------------------
# Final state normalization
# ---------------------------------------------------------

def _finalize(state: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize the final workflow state."""

    if state.get("error") or state.get("status") == "FAILED":
        state["status"] = "FAILED"
    elif state.get("status") == "SKIPPED":
        state["status"] = "SKIPPED"
    else:
        state["status"] = "SUCCESS"

    state.setdefault("recommendations", [])
    state.setdefault("recommendation_ids", [])

    return state


# ---------------------------------------------------------
# Monitoring node
# ---------------------------------------------------------

def monitoring_node(state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        new_state = monitoring_run(state)

        if not isinstance(new_state, dict):
            raise TypeError("Monitoring agent must return a dictionary")

        status = new_state.get("temperature_status")
        new_state["is_violation"] = status == "VIOLATION"

        return new_state

    except Exception as exc:
        return {
            **state,
            "error": f"Monitoring error: {exc}",
            "status": "FAILED",
        }


# ---------------------------------------------------------
# Incident node
# ---------------------------------------------------------

def incident_node(state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        new_state = incident_run(state)

        if not isinstance(new_state, dict):
            raise TypeError("Incident agent must return a dictionary")

        return new_state

    except Exception as exc:
        return {
            **state,
            "error": f"Incident error: {exc}",
            "status": "FAILED",
        }


# ---------------------------------------------------------
# Risk assessment node
# ---------------------------------------------------------

def risk_node(state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        new_state = risk_run(state)

        if not isinstance(new_state, dict):
            raise TypeError("Risk assessment agent must return a dictionary")

        return new_state

    except Exception as exc:
        return {
            **state,
            "error": f"Risk assessment error: {exc}",
            "status": "FAILED",
        }


# ---------------------------------------------------------
# Recommendation node
# ---------------------------------------------------------

def crew_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Run collaborative analysis without treating a missing LLM key as a workflow failure."""
    try:
        new_state = crew_run(state)
        if not isinstance(new_state, dict):
            raise TypeError("CrewAI analysis must return a dictionary")
        return new_state
    except Exception as exc:
        failed = dict(state)
        failed["crew_status"] = "FALLBACK"
        failed["crew_error"] = f"CrewAI error: {exc}"
        try:
            from ..agents.crew_analysis import build_fallback_analysis

            failed["crew_analysis"] = build_fallback_analysis(failed, reason=str(exc))
        except Exception:
            failed["crew_analysis"] = {
                "source": "deterministic_fallback",
                "available": False,
                "summary": "CrewAI analysis could not be completed.",
                "message": str(exc),
                "suggested_actions": [],
            }
        return failed


def recommendation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        new_state = recommendation_run(state)

        if not isinstance(new_state, dict):
            raise TypeError("Recommendation agent must return a dictionary")

        return new_state

    except Exception as exc:
        return {
            **state,
            "error": f"Recommendation error: {exc}",
            "status": "FAILED",
        }


# ---------------------------------------------------------
# Build LangGraph workflow
# ---------------------------------------------------------

graph = StateGraph(WorkflowState)

# Register agent nodes
graph.add_node("monitoring", monitoring_node)
graph.add_node("incident", incident_node)
graph.add_node("risk_assessment", risk_node)
graph.add_node("crew_analysis", crew_node)
graph.add_node("recommendation", recommendation_node)


# Starting point
graph.set_entry_point("monitoring")


# ---------------------------------------------------------
# Conditional routing
# ---------------------------------------------------------

# Monitoring:
# Normal reading -> END
# Violation -> Incident
# Failure -> END

def route_after_monitoring(state: Dict[str, Any]) -> str:
    if state.get("status") == "FAILED":
        return END

    if state.get("is_violation"):
        return "incident"

    return END


graph.add_conditional_edges(
    "monitoring",
    route_after_monitoring,
)


# Incident:
# Valid incident ID -> Risk assessment
# Missing/invalid incident ID or failure -> END

def route_after_incident(state: Dict[str, Any]) -> str:
    incident_id = state.get("incident_id")

    if state.get("status") == "FAILED":
        return END

    if (
        isinstance(incident_id, int)
        and not isinstance(incident_id, bool)
        and incident_id > 0
    ):
        return "risk_assessment"

    return END


graph.add_conditional_edges(
    "incident",
    route_after_incident,
)


# Risk assessment:
# Valid risk score -> CrewAI collaborative analysis -> Recommendation
# Failure or missing score -> END

def route_after_risk(state: Dict[str, Any]) -> str:
    risk_score = state.get("risk_score")

    if state.get("status") == "FAILED":
        return END

    if (
        isinstance(risk_score, (int, float))
        and not isinstance(risk_score, bool)
    ):
        return "crew_analysis"

    return END


graph.add_conditional_edges(
    "risk_assessment",
    route_after_risk,
)


# CrewAI analysis is additive and never fails the workflow (it falls back to a
# deterministic explanation when no LLM is configured). It always hands off to
# the deterministic recommendation agent, which owns database writes.
graph.add_edge("crew_analysis", "recommendation")

# Recommendation always terminates the workflow
graph.add_edge("recommendation", END)


# Compile workflow
workflow = graph.compile()


# ---------------------------------------------------------
# Public workflow function
# ---------------------------------------------------------

def run_workflow(reading_id: int) -> Dict[str, Any]:
    """Execute the ColdChain Guardian workflow for a reading."""

    if (
        not isinstance(reading_id, int)
        or isinstance(reading_id, bool)
        or reading_id <= 0
    ):
        raise ValueError("reading_id must be a positive integer")

    initial_state: WorkflowState = {
        "reading_id": reading_id,
        "status": "RUNNING",
        "recommendations": [],
        "recommendation_ids": [],
    }

    # Execute compiled LangGraph workflow
    final_state = workflow.invoke(initial_state)

    # Normalize final state
    final_state = _finalize(final_state)

    # Return API-friendly response
    return {
        "reading_id": reading_id,
        "workflow_status": final_state.get("status", "UNKNOWN"),
        "violation_detected": final_state.get("is_violation", False),
        "temperature_status": final_state.get("temperature_status"),
        "temperature_deviation": final_state.get("temperature_deviation"),
        "incident_id": final_state.get("incident_id"),
        "incident_created": final_state.get("incident_created", False),
        "severity": final_state.get("severity"),
        "risk_assessment_id": final_state.get("risk_assessment_id"),
        "risk_score": final_state.get("risk_score"),
        "risk_level": final_state.get("risk_level"),
        "risk_explanation": final_state.get("risk_explanation"),
        "risk_reused": final_state.get("risk_reused", False),
        "crew_analysis": final_state.get("crew_analysis"),
        "crew_status": final_state.get("crew_status"),
        "recommendations": final_state.get("recommendations", []),
        "recommendation_ids": final_state.get("recommendation_ids", []),
        "recommendations_generated": final_state.get("recommendations_generated", False),
        "error": final_state.get("error"),
    }
