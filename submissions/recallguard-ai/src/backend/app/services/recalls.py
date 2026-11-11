"""Recall campaigns: generation from a verified investigation, human approval, simulated execution."""
from __future__ import annotations

import secrets
from typing import Any

from app.agents.orchestrator import latest_run, run_outputs
from app.database import Database

from .common import InvalidState, NotFound, audit, dumps, loads, new_id, ts
from .incidents import get_incident, transition

_RC_COLS = ("recall_id, incident_id, title, recall_class, recall_status, risk_score, risk_class, risk_breakdown, plan_json, "
            "verification_json, instructions, generated_by, decided_by, decided_at, decision_comment, created_at, updated_at")


def generate_recall(db: Database, incident_id: str, actor: str, role: str, run_id: str | None = None) -> dict[str, Any]:
    inc = get_incident(db, incident_id)
    run = latest_run(db, incident_id) if not run_id else {"run_id": run_id, "status": None}
    if not run:
        raise InvalidState("No investigation has been run for this incident")
    outs = run_outputs(db, run["run_id"])
    if "verification" not in outs:
        raise InvalidState(f"Investigation {run['run_id']} has not completed verification yet")
    plan, risk, ver = outs["recall_planning"], outs["risk_assessment"], outs["verification"]
    if inc["incident_status"] not in ("RECALL_RECOMMENDED",):
        raise InvalidState(f"Incident is {inc['incident_status']}; a recall can only be generated from RECALL_RECOMMENDED")
    rid = new_id("RC")
    instructions = "\n\n".join(n.instruction for n in plan.notifications)
    with db.transaction():
        db.execute("UPDATE recall_campaigns SET recall_status = 'SUPERSEDED', updated_at = ? WHERE incident_id = ? "
                   "AND recall_status IN ('DRAFT','PENDING_APPROVAL','REJECTED')", (ts(), incident_id))
        db.execute(
            f"INSERT INTO recall_campaigns ({_RC_COLS}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (rid, incident_id, plan.title[:200], plan.recall_class, "PENDING_APPROVAL", risk.score, risk.classification,
             risk.model_dump_json(), plan.model_dump_json(), ver.model_dump_json(), instructions, f"run:{run['run_id']}",
             None, None, None, ts(), ts()))
        db.executemany(
            "INSERT INTO recall_affected_items (item_id, recall_id, batch_id, product_id, location_kind, location_ref, quantity_units, "
            "priority, inclusion_basis, reason, evidence_refs, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            [(f"{rid}-I{n:03d}", rid, i.batch_id, i.product_id, i.location_kind, i.location_ref, i.quantity_units, i.priority,
              i.inclusion_basis, i.reason[:600], "; ".join(i.evidence_refs)[:600], ts()) for n, i in enumerate(plan.items)])
        transition(db, incident_id, "PENDING_APPROVAL", actor, role, f"Recall {rid} generated and awaiting approval")
        audit(db, actor, role, "RECALL_GENERATED", "RECALL", rid,
              {"incident_id": incident_id, "run_id": run["run_id"], "items": len(plan.items), "units": plan.total_units,
               "verification": ver.verdict, "risk": risk.score})
    return get_recall(db, rid)


def get_recall(db: Database, recall_id: str) -> dict[str, Any]:
    r = db.query_one(f"SELECT {_RC_COLS} FROM recall_campaigns WHERE recall_id = ?", (recall_id,))
    if not r:
        raise NotFound(f"Recall {recall_id} not found")
    r["risk"] = loads(r.pop("risk_breakdown"), {})
    r["plan"] = loads(r.pop("plan_json"), {})
    r["verification"] = loads(r.pop("verification_json"), {})
    r["items"] = db.query(
        "SELECT i.item_id, i.batch_id, i.product_id, p.product_name, i.location_kind, i.location_ref, v.loc_name AS location_name, v.city, "
        "i.quantity_units, i.priority, i.inclusion_basis, i.reason, i.evidence_refs FROM recall_affected_items i "
        "JOIN finished_products p ON p.product_id = i.product_id LEFT JOIN v_locations v ON v.loc_ref = i.location_ref "
        "WHERE i.recall_id = ? ORDER BY i.priority, i.location_ref, i.batch_id", (recall_id,))
    r["actions"] = list_actions(db, recall_id)
    r["incident"] = get_incident(db, r["incident_id"])
    r["progress"] = progress(r["actions"], r["items"])
    return r


def list_recalls(db: Database, status: str | None = None) -> list[dict[str, Any]]:
    sql = ("SELECT r.recall_id, r.incident_id, r.title, r.recall_class, r.recall_status, r.risk_score, r.risk_class, r.decided_by, "
           "r.decided_at, r.created_at, i.source_ref, i.contaminant, "
           "(SELECT COUNT(*) FROM recall_affected_items x WHERE x.recall_id = r.recall_id) AS item_count, "
           "(SELECT COALESCE(SUM(x.quantity_units),0) FROM recall_affected_items x WHERE x.recall_id = r.recall_id) AS units, "
           "(SELECT COALESCE(SUM(a.units_recovered),0) FROM recall_actions a WHERE a.recall_id = r.recall_id) AS units_recovered "
           "FROM recall_campaigns r JOIN contamination_incidents i ON i.incident_id = r.incident_id")
    params: tuple = ()
    if status:
        sql += " WHERE r.recall_status = ?"
        params = (status,)
    return db.query(sql + " ORDER BY r.created_at DESC, r.recall_id", params)


def _decide(db: Database, recall_id: str, status: str, actor: str, role: str, comment: str) -> dict[str, Any]:
    rc = db.query_one("SELECT recall_status, incident_id FROM recall_campaigns WHERE recall_id = ?", (recall_id,))
    if not rc:
        raise NotFound(f"Recall {recall_id} not found")
    if rc["recall_status"] != "PENDING_APPROVAL":
        raise InvalidState(f"Recall {recall_id} is {rc['recall_status']}; only PENDING_APPROVAL can be decided")
    with db.transaction():
        db.execute("UPDATE recall_campaigns SET recall_status = ?, decided_by = ?, decided_at = ?, decision_comment = ?, updated_at = ? "
                   "WHERE recall_id = ? AND recall_status = 'PENDING_APPROVAL'", (status, actor, ts(), comment[:2000], ts(), recall_id))
        transition(db, rc["incident_id"], status, actor, role, f"Recall {recall_id} {status.lower()}: {comment}")
        audit(db, actor, role, f"RECALL_{status}", "RECALL", recall_id, {"comment": comment})
    return get_recall(db, recall_id)


def approve(db: Database, recall_id: str, actor: str, role: str, comment: str) -> dict[str, Any]:
    _decide(db, recall_id, "APPROVED", actor, role, comment)
    return execute(db, recall_id, actor, role)


def reject(db: Database, recall_id: str, actor: str, role: str, comment: str) -> dict[str, Any]:
    if not comment.strip():
        raise InvalidState("A rejection requires a comment explaining why")
    return _decide(db, recall_id, "REJECTED", actor, role, comment)


def execute(db: Database, recall_id: str, actor: str, role: str) -> dict[str, Any]:
    """After approval: create per-location actions and send SIMULATED notifications."""
    rc = get_recall(db, recall_id)
    if rc["recall_status"] != "APPROVED":
        raise InvalidState("Only an APPROVED recall can be executed")
    plan = rc["plan"]
    rows = []
    for n in plan.get("notifications", []):
        for act in n["action_types"]:
            rows.append((f"{recall_id}-A{secrets.token_hex(3).upper()}", recall_id, n["location_kind"], n["location_ref"], act,
                         "SENT" if act == "NOTIFY" else "PENDING", n["units_expected"] if act != "NOTIFY" else 0, 0,
                         n["instruction"][:1000] if act == "NOTIFY" else None, "SIMULATED", actor, ts(), ts()))
    with db.transaction():
        db.executemany("INSERT INTO recall_actions (action_id, recall_id, location_kind, location_ref, action_type, action_status, "
                       "units_expected, units_recovered, notes, channel, updated_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        db.execute("UPDATE recall_campaigns SET recall_status = 'EXECUTING', updated_at = ? WHERE recall_id = ?", (ts(), recall_id))
        db.execute("UPDATE production_batches SET batch_status = 'RECALLED' WHERE batch_id IN "
                   "(SELECT DISTINCT batch_id FROM recall_affected_items WHERE recall_id = ?)", (recall_id,))
        transition(db, rc["incident_id"], "EXECUTING", actor, role, "Recall execution started (simulated notifications)")
        audit(db, actor, role, "RECALL_NOTIFICATIONS_SENT", "RECALL", recall_id,
              {"notifications": sum(1 for r in rows if r[4] == "NOTIFY"), "channel": "SIMULATED"})
    return get_recall(db, recall_id)


def list_actions(db: Database, recall_id: str) -> list[dict[str, Any]]:
    return db.query("SELECT a.action_id, a.location_kind, a.location_ref, v.loc_name AS location_name, v.city, a.action_type, a.action_status, "
                    "a.units_expected, a.units_recovered, a.notes, a.channel, a.updated_by, a.updated_at FROM recall_actions a "
                    "LEFT JOIN v_locations v ON v.loc_ref = a.location_ref WHERE a.recall_id = ? ORDER BY a.location_kind, a.location_ref, a.action_type",
                    (recall_id,))


ACTION_FLOW = {"NOTIFY": ("SENT", "ACKNOWLEDGED"), "QUARANTINE": ("PENDING", "IN_PROGRESS", "DONE"), "RECOVER": ("PENDING", "IN_PROGRESS", "DONE")}


def update_action(db: Database, recall_id: str, action_id: str, status: str, units_recovered: int | None, actor: str, role: str,
                  notes: str | None = None) -> dict[str, Any]:
    a = db.query_one("SELECT action_type, action_status, units_expected FROM recall_actions WHERE action_id = ? AND recall_id = ?",
                     (action_id, recall_id))
    if not a:
        raise NotFound(f"Action {action_id} not found")
    rc = db.query_one("SELECT recall_status, incident_id FROM recall_campaigns WHERE recall_id = ?", (recall_id,))
    if rc["recall_status"] != "EXECUTING":
        raise InvalidState("Actions can only be updated while the recall is EXECUTING")
    if status not in ACTION_FLOW[a["action_type"]]:
        raise InvalidState(f"{a['action_type']} actions cannot move to {status}")
    units = a["units_expected"] if (units_recovered is None and status == "DONE") else (units_recovered or 0)
    if units < 0 or units > a["units_expected"] and a["units_expected"] > 0:
        raise InvalidState("units_recovered must be between 0 and units_expected")
    db.execute("UPDATE recall_actions SET action_status = ?, units_recovered = ?, notes = COALESCE(?, notes), updated_by = ?, updated_at = ? "
               "WHERE action_id = ?", (status, units, notes, actor, ts(), action_id))
    audit(db, actor, role, "RECALL_ACTION_UPDATED", "RECALL", recall_id, {"action_id": action_id, "status": status, "units": units})
    return get_recall(db, recall_id)


def simulate_acknowledgements(db: Database, recall_id: str, actor: str, role: str, fraction: float = 0.6) -> dict[str, Any]:
    """Demo helper: a share of locations acknowledge and start/finish recovery (clearly SIMULATED)."""
    rc = get_recall(db, recall_id)
    if rc["recall_status"] != "EXECUTING":
        raise InvalidState("Recall is not executing")
    locs = sorted({a["location_ref"] for a in rc["actions"]})
    chosen = set(locs[: max(1, int(len(locs) * fraction))])
    for a in rc["actions"]:
        if a["location_ref"] not in chosen:
            continue
        if a["action_type"] == "NOTIFY" and a["action_status"] == "SENT":
            db.execute("UPDATE recall_actions SET action_status='ACKNOWLEDGED', updated_by=?, updated_at=? WHERE action_id=?",
                       ("simulated.partner", ts(), a["action_id"]))
        elif a["action_type"] in ("QUARANTINE", "RECOVER") and a["action_status"] == "PENDING":
            done = a["location_ref"] < locs[len(locs) // 3] if len(locs) > 2 else True
            db.execute("UPDATE recall_actions SET action_status=?, units_recovered=?, updated_by=?, updated_at=? WHERE action_id=?",
                       ("DONE" if done else "IN_PROGRESS", a["units_expected"] if done else a["units_expected"] // 2,
                        "simulated.partner", ts(), a["action_id"]))
    audit(db, actor, role, "RECALL_ACKS_SIMULATED", "RECALL", recall_id, {"locations": len(chosen), "channel": "SIMULATED"})
    return get_recall(db, recall_id)


def complete(db: Database, recall_id: str, actor: str, role: str, comment: str = "") -> dict[str, Any]:
    rc = get_recall(db, recall_id)
    if rc["recall_status"] != "EXECUTING":
        raise InvalidState("Only an EXECUTING recall can be completed")
    open_actions = [a for a in rc["actions"] if a["action_status"] not in ("ACKNOWLEDGED", "DONE")]
    if open_actions:
        raise InvalidState(f"{len(open_actions)} action(s) still open; close them before completing")
    with db.transaction():
        db.execute("UPDATE recall_campaigns SET recall_status='COMPLETED', updated_at=? WHERE recall_id=?", (ts(), recall_id))
        transition(db, rc["incident_id"], "COMPLETED", actor, role, comment or "All recall actions closed")
        audit(db, actor, role, "RECALL_COMPLETED", "RECALL", recall_id, {"comment": comment})
    return get_recall(db, recall_id)


def progress(actions: list[dict[str, Any]], items: list[dict[str, Any]]) -> dict[str, Any]:
    notify = [a for a in actions if a["action_type"] == "NOTIFY"]
    phys = [a for a in actions if a["action_type"] in ("QUARANTINE", "RECOVER")]
    expected = sum(a["units_expected"] for a in phys) or sum(i["quantity_units"] for i in items)
    recovered = sum(a["units_recovered"] for a in phys)
    return {
        "locations_notified": len(notify),
        "acknowledged": sum(1 for a in notify if a["action_status"] == "ACKNOWLEDGED"),
        "quarantine_done": sum(1 for a in phys if a["action_type"] == "QUARANTINE" and a["action_status"] == "DONE"),
        "quarantine_total": sum(1 for a in phys if a["action_type"] == "QUARANTINE"),
        "recover_done": sum(1 for a in phys if a["action_type"] == "RECOVER" and a["action_status"] == "DONE"),
        "recover_total": sum(1 for a in phys if a["action_type"] == "RECOVER"),
        "units_expected": expected,
        "units_recovered": recovered,
        "recovery_pct": round(100 * recovered / expected, 1) if expected else 0.0,
        "open_actions": sum(1 for a in actions if a["action_status"] not in ("ACKNOWLEDGED", "DONE")),
    }
