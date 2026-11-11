"""Executive dashboard aggregates (all computed by SQL in Db2)."""
from __future__ import annotations

from typing import Any

from app.database import Database
from app.database.queries import sql

ACTIVE = ("REPORTED", "INVESTIGATING", "EVIDENCE_REVIEW", "RECALL_RECOMMENDED", "PENDING_APPROVAL", "APPROVED", "EXECUTING")


def summary(db: Database) -> dict[str, Any]:
    marks = ",".join("?" for _ in ACTIVE)
    totals = db.query_one(
        "SELECT COUNT(*) AS total_incidents, "
        f"SUM(CASE WHEN incident_status IN ({marks}) THEN 1 ELSE 0 END) AS active_incidents, "
        "SUM(CASE WHEN severity = 'CRITICAL' THEN 1 ELSE 0 END) AS critical_incidents FROM contamination_incidents", ACTIVE) or {}
    # products/batches/locations under investigation: union of every active incident's Db2 impact
    active = db.query(f"SELECT incident_id, source_ref FROM contamination_incidents WHERE incident_status IN ({marks})", ACTIVE)
    batches, products, locations = set(), set(), set()
    for inc in active:
        for b in db.query(sql("impact_batches"), (inc["source_ref"], inc["source_ref"])):
            batches.add(b["batch_id"])
            if b["product_id"]:
                products.add(b["product_id"])
        for h in db.query(sql("impact_hops"), (inc["source_ref"], inc["source_ref"])):
            locations.add(h["dest_ref"])
    recalls = db.query_one(
        "SELECT SUM(CASE WHEN recall_status = 'PENDING_APPROVAL' THEN 1 ELSE 0 END) AS pending_approvals, "
        "SUM(CASE WHEN recall_status IN ('APPROVED','EXECUTING') THEN 1 ELSE 0 END) AS active_recalls, "
        "SUM(CASE WHEN recall_status = 'COMPLETED' THEN 1 ELSE 0 END) AS completed_recalls FROM recall_campaigns") or {}
    risk_dist = db.query("SELECT risk_class, COUNT(*) AS n FROM recall_campaigns WHERE recall_status <> 'SUPERSEDED' GROUP BY risk_class")
    status_dist = db.query("SELECT incident_status, COUNT(*) AS n FROM contamination_incidents GROUP BY incident_status")
    timeline = db.query(
        "SELECT a.occurred_at, a.actor, a.action_name, a.entity_kind, a.entity_ref, a.details FROM audit_logs a "
        "WHERE a.action_name IN ('INCIDENT_CREATED','INVESTIGATION_COMPLETED','RECALL_GENERATED','RECALL_APPROVED','RECALL_REJECTED',"
        "'RECALL_NOTIFICATIONS_SENT','RECALL_COMPLETED','EVIDENCE_UPLOADED') ORDER BY a.occurred_at DESC")[:12]
    network = db.query_one(
        "SELECT (SELECT COUNT(*) FROM suppliers) AS suppliers, (SELECT COUNT(*) FROM ingredient_lots) AS lots, "
        "(SELECT COUNT(*) FROM production_batches) AS batches, (SELECT COUNT(*) FROM finished_products) AS products, "
        "(SELECT COUNT(*) FROM manufacturing_facilities) AS facilities, (SELECT COUNT(*) FROM warehouses) AS warehouses, "
        "(SELECT COUNT(*) FROM distributors) AS distributors, (SELECT COUNT(*) FROM retailers) AS retailers, "
        "(SELECT COUNT(*) FROM shipments) AS shipments, (SELECT COUNT(*) FROM batch_transformations) AS transformations") or {}
    shipments_by_month = db.query(
        "SELECT dest_kind, COUNT(*) AS n FROM shipments GROUP BY dest_kind ORDER BY dest_kind")
    return {
        "kpis": {
            "total_incidents": int(totals.get("total_incidents") or 0),
            "active_incidents": int(totals.get("active_incidents") or 0),
            "critical_incidents": int(totals.get("critical_incidents") or 0),
            "products_under_investigation": len(products),
            "batches_potentially_affected": len(batches),
            "locations_affected": len(locations),
            "pending_approvals": int(recalls.get("pending_approvals") or 0),
            "active_recalls": int(recalls.get("active_recalls") or 0),
            "completed_recalls": int(recalls.get("completed_recalls") or 0),
        },
        "risk_distribution": risk_dist,
        "status_distribution": status_dist,
        "timeline": timeline,
        "network": network,
        "shipments_by_destination": shipments_by_month,
        "engine": db.label,
    }


def audit_logs(db: Database, entity_ref: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 1000))
    if entity_ref:
        rows = db.query("SELECT audit_id, occurred_at, actor, actor_role, action_name, entity_kind, entity_ref, details FROM audit_logs "
                        "WHERE entity_ref = ? OR details LIKE ? ORDER BY occurred_at DESC", (entity_ref, f"%{entity_ref}%"))
    else:
        rows = db.query("SELECT audit_id, occurred_at, actor, actor_role, action_name, entity_kind, entity_ref, details FROM audit_logs "
                        "ORDER BY occurred_at DESC")
    return rows[:limit]
