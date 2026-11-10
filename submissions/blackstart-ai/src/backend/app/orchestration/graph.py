from typing import TypedDict, Any
from langgraph.graph import StateGraph, START, END


class GridState(TypedDict, total=False):
    grid: dict[str, Any]
    findings: dict[str, Any]
    events: list[dict[str, Any]]
    result: dict[str, Any]


def record(state, agent, event_type, finding, confidence=95):
    events = list(state.get("events", []))
    events.append({
        "agent": agent,
        "event_type": event_type,
        "finding": finding,
        "confidence": confidence
    })
    return events


def volt(state):
    grid = state["grid"]
    incidents = grid["incidents"]
    overloaded = []

    for line in grid["lines"]:
        capacity = float(line["capacity_mw"] or 0)
        load = float(line["current_load_mw"] or 0)
        if capacity and load / capacity >= 0.80:
            overloaded.append({
                "line": line["line_name"],
                "utilization": round(load / capacity * 100, 2)
            })

    findings = {
        "open_incidents": [
            i for i in incidents
            if str(i.get("status", "")).upper() == "OPEN"
        ],
        "overloaded_lines": overloaded
    }

    events = record(
        state, "VOLT", "INCIDENT_DETECTION",
        f"Detected {len(findings['open_incidents'])} open incidents "
        f"and {len(overloaded)} lines at or above 80% utilization."
    )

    return {"findings": {"volt": findings}, "events": events}


def pulse(state):
    grid = state["grid"]
    substations = grid["substations"]
    lines = grid["lines"]

    topology = {
        "substation_count": len(substations),
        "transmission_line_count": len(lines),
        "online_substations": sum(
            str(s["status"]).upper() == "ONLINE" for s in substations
        ),
        "line_connections": [
            {
                "line": l["line_name"],
                "from": l["from_substation"],
                "to": l["to_substation"]
            } for l in lines
        ]
    }

    findings = dict(state.get("findings", {}))
    findings["pulse"] = topology
    events = record(
        state, "PULSE", "TOPOLOGY_ANALYSIS",
        f"Analyzed {len(substations)} substations and {len(lines)} transmission lines."
    )
    return {"findings": findings, "events": events}


def cascade(state):
    overloaded = state["findings"]["volt"]["overloaded_lines"]
    grid = state["grid"]

    risk = "HIGH" if any(
        item["utilization"] >= 90 for item in overloaded
    ) else "MODERATE" if overloaded else "LOW"

    findings = dict(state.get("findings", {}))
    findings["cascade"] = {
        "risk_level": risk,
        "overloaded_line_count": len(overloaded),
        "at_risk_lines": overloaded,
        "simulation_mode": "DEMONSTRATION_ONLY"
    }

    events = record(
        state, "CASCADE", "CASCADE_SIMULATION",
        f"Estimated cascading failure risk: {risk}. "
        f"{len(overloaded)} lines require attention."
    )
    return {"findings": findings, "events": events}


def guardian(state):
    risk = state["findings"]["cascade"]["risk_level"]
    incidents = state["findings"]["volt"]["open_incidents"]

    impact = {
        "risk_level": risk,
        "open_incident_count": len(incidents),
        "critical_alert": risk == "HIGH",
        "assessment": (
            "Immediate operator review recommended."
            if risk == "HIGH"
            else "Continue monitoring and review operational thresholds."
        )
    }

    findings = dict(state.get("findings", {}))
    findings["guardian"] = impact

    events = record(
        state, "GUARDIAN", "INFRASTRUCTURE_IMPACT",
        impact["assessment"]
    )
    return {"findings": findings, "events": events}


def blackstart(state):
    risk = state["findings"]["cascade"]["risk_level"]
    overloaded = state["findings"]["volt"]["overloaded_lines"]

    recommendations = []

    if overloaded:
        recommendations.append(
            "Ask grid operators to inspect high-utilization transmission lines."
        )
        recommendations.append(
            "Review load distribution and available reserve capacity."
        )

    if risk == "HIGH":
        recommendations.append(
            "Escalate for immediate human operator assessment."
        )
    else:
        recommendations.append(
            "Continue monitoring and validate the latest grid measurements."
        )

    recommendations.append(
        "Do not execute switching or recovery actions automatically."
    )

    result = {
        "system": "BLACKSTART AI",
        "overall_risk": risk,
        "agents_executed": [
            "VOLT", "PULSE", "CASCADE", "GUARDIAN", "BLACKSTART"
        ],
        "findings": state["findings"],
        "recommendations": recommendations,
        "execution_mode": "ADVISORY_ONLY",
        "data_source": "IBM Db2"
    }

    events = record(
        state, "BLACKSTART", "RECOVERY_RECOMMENDATION",
        f"Generated {len(recommendations)} advisory recommendations."
    )

    return {"result": result, "events": events}


workflow = StateGraph(GridState)

workflow.add_node("volt", volt)
workflow.add_node("pulse", pulse)
workflow.add_node("cascade", cascade)
workflow.add_node("guardian", guardian)
workflow.add_node("blackstart", blackstart)

workflow.add_edge(START, "volt")
workflow.add_edge("volt", "pulse")
workflow.add_edge("pulse", "cascade")
workflow.add_edge("cascade", "guardian")
workflow.add_edge("guardian", "blackstart")
workflow.add_edge("blackstart", END)

blackstart_graph = workflow.compile()


def analyze_grid(grid):
    return blackstart_graph.invoke({
        "grid": grid,
        "findings": {},
        "events": []
    })
