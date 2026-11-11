"""Contamination incidents and the human-in-the-loop state machine."""
from __future__ import annotations

from typing import Any

from app.database import Database

from .common import InvalidState, NotFound, audit, new_id, now, ts
from .traceability import resolve_node

STATES = ("REPORTED", "INVESTIGATING", "EVIDENCE_REVIEW", "RECALL_RECOMMENDED", "PENDING_APPROVAL",
          "APPROVED", "REJECTED", "EXECUTING", "COMPLETED")

# Allowed transitions. Only humans move PENDING_APPROVAL -> APPROVED/REJECTED (enforced at API layer by role).
TRANSITIONS: dict[str, set[str]] = {
    "REPORTED": {"INVESTIGATING"},
    "INVESTIGATING": {"EVIDENCE_REVIEW", "REPORTED"},
    "EVIDENCE_REVIEW": {"RECALL_RECOMMENDED", "INVESTIGATING"},
    "RECALL_RECOMMENDED": {"PENDING_APPROVAL", "INVESTIGATING"},
    "PENDING_APPROVAL": {"APPROVED", "REJECTED", "INVESTIGATING"},
    "APPROVED": {"EXECUTING"},
    "REJECTED": {"INVESTIGATING"},
    "EXECUTING": {"COMPLETED"},
    "COMPLETED": set(),
}

_COLS = ("incident_id, title, source_kind, source_ref, contaminant, contamination_category, severity, supplier_id, "
         "reported_by, discovered_at, incident_status, description, is_demo, created_at, updated_at")


def transition(db: Database, incident_id: str, target: str, actor: str, role: str, reason: str = "") -> dict[str, Any]:
    inc = get_incident(db, incident_id)
    cur = inc["incident_status"]
    if cur == target:
        return inc
    if target not in TRANSITIONS.get(cur, set()):
        raise InvalidState(f"Incident {incident_id}: transition {cur} -> {target} is not allowed")
    n = db.execute("UPDATE contamination_incidents SET incident_status = ?, updated_at = ? WHERE incident_id = ? AND incident_status = ?",
                   (target, ts(), incident_id, cur))
    if n != 1:
        raise InvalidState(f"Incident {incident_id} changed concurrently; retry")
    audit(db, actor, role, "INCIDENT_STATUS_CHANGED", "INCIDENT", incident_id, {"from": cur, "to": target, "reason": reason})
    return get_incident(db, incident_id)


def create_incident(db: Database, data: dict[str, Any], actor: str, role: str) -> dict[str, Any]:
    node = resolve_node(db, data["source_ref"])  # raises NotFound for unknown lot/batch -> no orphan incidents
    supplier_id = data.get("supplier_id") or node.get("supplier_id")
    if supplier_id and not db.query_one("SELECT supplier_id FROM suppliers WHERE supplier_id = ?", (supplier_id,)):
        raise NotFound(f"Supplier {supplier_id} not found")
    inc_id = new_id("INC")
    discovered = data.get("discovered_at") or now()
    with db.transaction():
        db.execute(
            f"INSERT INTO contamination_incidents ({_COLS}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (inc_id, data["title"], node["kind"], node["ref"], data["contaminant"], data["contamination_category"],
             data["severity"], supplier_id, actor, ts(discovered) if not isinstance(discovered, str) else discovered.replace("T", " ")[:19],
             "REPORTED", data.get("description"), 1 if data.get("is_demo") else 0, ts(), ts()))
        audit(db, actor, role, "INCIDENT_CREATED", "INCIDENT", inc_id,
              {"source": node["ref"], "severity": data["severity"], "contaminant": data["contaminant"]})
    return get_incident(db, inc_id)


def get_incident(db: Database, incident_id: str) -> dict[str, Any]:
    r = db.query_one(
        f"SELECT i.{_COLS.replace(', ', ', i.')}, s.supplier_name FROM contamination_incidents i "
        "LEFT JOIN suppliers s ON s.supplier_id = i.supplier_id WHERE i.incident_id = ?", (incident_id,))
    if not r:
        raise NotFound(f"Incident {incident_id} not found")
    r["is_demo"] = bool(r["is_demo"])
    return r


def list_incidents(db: Database, status: str | None = None) -> list[dict[str, Any]]:
    sql = (f"SELECT i.{_COLS.replace(', ', ', i.')}, s.supplier_name, "
           "(SELECT COUNT(*) FROM evidence_documents d WHERE d.incident_id = i.incident_id) AS evidence_count, "
           "(SELECT MAX(r.recall_id) FROM recall_campaigns r WHERE r.incident_id = i.incident_id AND r.recall_status <> 'SUPERSEDED') AS recall_id "
           "FROM contamination_incidents i LEFT JOIN suppliers s ON s.supplier_id = i.supplier_id")
    params: tuple = ()
    if status:
        sql += " WHERE i.incident_status = ?"
        params = (status,)
    rows = db.query(sql + " ORDER BY i.discovered_at DESC, i.incident_id", params)
    for r in rows:
        r["is_demo"] = bool(r["is_demo"])
    return rows


def add_comment(db: Database, incident_id: str, body: str, actor: str, role: str) -> dict[str, Any]:
    get_incident(db, incident_id)
    cid = new_id("CMT")
    db.execute("INSERT INTO incident_comments (comment_id, incident_id, author, author_role, body, created_at) VALUES (?,?,?,?,?,?)",
               (cid, incident_id, actor, role, body[:2000], ts()))
    audit(db, actor, role, "COMMENT_ADDED", "INCIDENT", incident_id, {"comment_id": cid})
    return {"comment_id": cid, "incident_id": incident_id, "author": actor, "author_role": role, "body": body[:2000]}


def list_comments(db: Database, incident_id: str) -> list[dict[str, Any]]:
    return db.query("SELECT comment_id, incident_id, author, author_role, body, created_at FROM incident_comments "
                    "WHERE incident_id = ? ORDER BY created_at, comment_id", (incident_id,))
