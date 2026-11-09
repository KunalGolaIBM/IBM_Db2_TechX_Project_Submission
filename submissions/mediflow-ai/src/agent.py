from datetime import date
from uuid import uuid4
from src.models import InventoryItem, RiskFinding, Recommendation

def assess_item(item: InventoryItem) -> RiskFinding:
    days = item.on_hand / item.avg_daily_use
    reasons = []
    stockout = days < item.supplier_lead_days + 3 or item.on_hand < item.reorder_level
    expiry = bool(item.nearest_expiry and (item.nearest_expiry - date.today()).days <= 30 and item.expiring_quantity > 0)
    if days < item.supplier_lead_days + 3:
        reasons.append(f"Estimated cover ({days:.1f} days) is below supplier lead time plus a 3-day buffer.")
    if item.on_hand < item.reorder_level:
        reasons.append("On-hand quantity is below the configured reorder level.")
    if expiry:
        reasons.append(f"{item.expiring_quantity} units are in batches expiring within 30 days.")
    if not reasons:
        reasons.append("No threshold breach detected in the current snapshot.")
    return RiskFinding(medicine_id=item.medicine_id, medicine_name=item.medicine_name,
        days_of_cover=round(days, 1), stockout_risk=stockout, expiry_risk=expiry, reasons=reasons)

def draft_recommendation(item: InventoryItem, finding: RiskFinding) -> Recommendation:
    target_days = max(item.supplier_lead_days + 7, 14)
    target_stock = round(item.avg_daily_use * target_days)
    quantity = max(0, int(target_stock - item.on_hand))
    rationale = finding.reasons + [
        f"Target coverage is {target_days} days, based on average daily use of {item.avg_daily_use:.1f}.",
        "This is a draft estimate; a reviewer must validate policy, budget and supplier constraints."
    ]
    return Recommendation(recommendation_id=str(uuid4()), medicine_id=item.medicine_id,
        medicine_name=item.medicine_name, suggested_quantity=quantity,
        days_of_cover=finding.days_of_cover, rationale=rationale)

def run_workflow(items, repository):
    def assess_node(state):
        return {"findings": [assess_item(item) for item in state["items"]]}
    def draft_node(state):
        by_id = {item.medicine_id: item for item in state["items"]}
        drafts = [draft_recommendation(by_id[f.medicine_id], f) for f in state["findings"] if f.stockout_risk or f.expiry_risk]
        for recommendation in drafts:
            repository.save_recommendation(recommendation)
        return {"recommendations": drafts}
    try:
        from typing import TypedDict
        from langgraph.graph import StateGraph, START, END
        class WorkflowState(TypedDict, total=False):
            items: list
            findings: list
            recommendations: list
        graph = StateGraph(WorkflowState)
        graph.add_node("assess_risk", assess_node)
        graph.add_node("draft_recommendations", draft_node)
        graph.add_edge(START, "assess_risk")
        graph.add_edge("assess_risk", "draft_recommendations")
        graph.add_edge("draft_recommendations", END)
        result = graph.compile().invoke({"items": items})
        return result["findings"], result["recommendations"], "langgraph"
    except ImportError:
        state = assess_node({"items": items})
        result = draft_node({"items": items, "findings": state["findings"]})
        return state["findings"], result["recommendations"], "deterministic-fallback"
