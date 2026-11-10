from typing import TypedDict, Any
from datetime import datetime
from uuid import uuid4

class SentinelState(TypedDict, total=False):
    shipment_id: str
    context: dict
    severity: str
    impact: dict
    options: list
    verification: dict
    case_id: str
    error: str

def calculate_impact(context):
    available = max(0, int(context["on_hand_qty"]) - int(context["reserved_qty"]))
    daily = max(1, int(context["daily_demand"]))
    runway = round(available / daily, 1)
    orders = context.get("production_orders", [])
    exposed = [o for o in orders if int(o["required_qty"]) > 0]
    exposed_qty = sum(int(o["required_qty"]) for o in exposed)
    delay_days = max(0, (datetime.fromisoformat(str(context["revised_eta"])[:10]) -
                         datetime.fromisoformat(str(context["original_eta"])[:10])).days)
    if runway <= delay_days:
        severity = "CRITICAL"
    elif context["criticality"] == "CRITICAL" or delay_days >= 5:
        severity = "HIGH"
    else:
        severity = "MEDIUM"
    return {
        "available_inventory": available,
        "daily_demand": daily,
        "inventory_runway_days": runway,
        "delay_days": delay_days,
        "exposed_order_count": len(exposed),
        "exposed_demand_qty": exposed_qty,
        "exposed_orders": exposed,
        "shortage_risk": runway <= delay_days,
    }, severity

def build_graph(repository):
    try:
        from langgraph.graph import StateGraph, END
    except ImportError as exc:
        raise RuntimeError("LangGraph is required to run the agent workflow. Install requirements.txt first.") from exc
    def monitor(state):
        if not state.get("shipment_id"):
            raise ValueError("A shipment ID is required.")
        return {"case_id": "CASE-" + uuid4().hex[:10].upper()}

    def investigate(state):
        return {"context": repository.get_disruption_context(state["shipment_id"])}

    def assess(state):
        impact, severity = calculate_impact(state["context"])
        return {"impact": impact, "severity": severity}

    def plan(state):
        c, impact = state["context"], state["impact"]
        options = []
        if impact["shortage_risk"]:
            options.append({"name":"EXPEDITE CURRENT SHIPMENT",
                "rationale":f"Request carrier/supplier escalation because the revised delay ({impact['delay_days']} days) exceeds inventory runway ({impact['inventory_runway_days']} days)."})
        options.append({"name":"REVIEW PARTIAL ALLOCATION",
            "rationale":f"Review allocation against {impact['exposed_order_count']} open production orders; available inventory is {impact['available_inventory']} units. Planner must confirm priorities."})
        if float(c["on_time_rate"]) < 90:
            options.append({"name":"QUALIFY ALTERNATE SOURCE",
                "rationale":f"Supplier on-time rate is {c['on_time_rate']}%; initiate qualification review before committing alternate supply."})
        options.append({"name":"REVIEW PRODUCTION SEQUENCE",
            "rationale":"Ask the production planner to review sequencing and communicate any approved schedule change to affected stakeholders."})
        return {"options": options}

    def verify(state):
        c=state["context"]; options=state["options"]
        checks = {
            "shipment_record_present": bool(c.get("shipment_id")),
            "supplier_and_po_present": bool(c.get("supplier_id") and c.get("po_id")),
            "inventory_present": c.get("on_hand_qty") is not None,
            "quality_status_visible": bool(c.get("quality_status")),
            "recommendations_have_rationale": all(bool(x.get("rationale")) for x in options),
            "human_approval_required": True
        }
        return {"verification":{"checks":checks,"passed":all(checks.values()),
            "note":"Options are decision support only. No purchase order or production schedule is changed automatically."}}

    def persist(state):
        c=state["context"]
        repository.create_risk_case(state["case_id"],state["shipment_id"],c["component_id"],
                                    state["severity"],f"{c['component_name']}: {state['severity']} supply risk")
        repository.record_recommendations(state["case_id"],state["options"])
        return {}

    graph=StateGraph(SentinelState)
    graph.add_node("monitor",monitor)
    graph.add_node("investigate",investigate)
    graph.add_node("assess",assess)
    graph.add_node("plan",plan)
    graph.add_node("verify",verify)
    graph.add_node("persist",persist)
    graph.set_entry_point("monitor")
    graph.add_edge("monitor","investigate")
    graph.add_edge("investigate","assess")
    graph.add_edge("assess","plan")
    graph.add_edge("plan","verify")
    graph.add_edge("verify","persist")
    graph.add_edge("persist",END)
    return graph.compile()

def investigate_shipment(repository, shipment_id):
    app=build_graph(repository)
    return app.invoke({"shipment_id":shipment_id})
