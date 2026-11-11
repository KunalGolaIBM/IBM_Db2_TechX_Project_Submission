"""Tomato contamination demo (TOM-2026-041) — uses the same public services as the UI."""
from __future__ import annotations

from typing import Any

from app.database import Database

from . import evidence as ev
from . import recalls
from .bootstrap import SAMPLE_LAB_REPORT
from .common import audit
from .incidents import create_incident

TOMATO_INCIDENT = {
    "title": "Salmonella Typhimurium in tomato puree lot TOM-2026-041",
    "source_ref": "TOM-2026-041",
    "contaminant": "Salmonella Typhimurium",
    "contamination_category": "MICROBIAL",
    "severity": "CRITICAL",
    "description": "Sahyadri Analytical Food Laboratory report SAFL-2026-11-0457: Salmonella detected in 3 of 5 retained samples.",
    "is_demo": True,
}


def run_tomato_demo(db: Database, actor: str, role: str) -> dict[str, Any]:
    """Server-side one-shot run (used by tests/CLI). The UI runs the same steps one by one."""
    from app.agents.orchestrator import get_run, start_investigation

    steps = []
    inc = create_incident(db, TOMATO_INCIDENT, actor, role)
    steps.append({"step": "incident_registered", "incident_id": inc["incident_id"]})
    doc = ev.ingest_document(db, filename=SAMPLE_LAB_REPORT.name, data=SAMPLE_LAB_REPORT.read_bytes(), uploaded_by=actor, role=role,
                             incident_id=inc["incident_id"], doc_type="LAB_REPORT")
    steps.append({"step": "lab_report_uploaded", "document_id": doc["document_id"], "claims": len(doc["extracted"]["claims"])})
    run = start_investigation(db, inc["incident_id"], actor, role, background=False)
    result = get_run(db, run["run_id"])
    steps.append({"step": "investigation_completed", "run_id": run["run_id"], "status": result["status"], "mode": result["mode"]})
    rc = recalls.generate_recall(db, inc["incident_id"], actor, role)
    steps.append({"step": "recall_generated", "recall_id": rc["recall_id"], "status": rc["recall_status"]})
    return {"incident_id": inc["incident_id"], "document_id": doc["document_id"], "run_id": run["run_id"],
            "recall_id": rc["recall_id"], "steps": steps}


def reset_demo(db: Database, actor: str, role: str) -> dict[str, Any]:
    """Delete demo incidents (is_demo = 1) and everything hanging off them; restore batch statuses."""
    incs = [r["incident_id"] for r in db.query("SELECT incident_id FROM contamination_incidents WHERE is_demo = 1")]
    with db.transaction():
        for iid in incs:
            rids = [r["recall_id"] for r in db.query("SELECT recall_id FROM recall_campaigns WHERE incident_id = ?", (iid,))]
            for rid in rids:
                db.execute("UPDATE production_batches SET batch_status = 'RELEASED' WHERE batch_id IN "
                           "(SELECT batch_id FROM recall_affected_items WHERE recall_id = ?)", (rid,))
                db.execute("DELETE FROM recall_actions WHERE recall_id = ?", (rid,))
                db.execute("DELETE FROM recall_affected_items WHERE recall_id = ?", (rid,))
            db.execute("DELETE FROM recall_campaigns WHERE incident_id = ?", (iid,))
            db.execute("DELETE FROM agent_investigations WHERE incident_id = ?", (iid,))
            db.execute("DELETE FROM incident_affected_lots WHERE incident_id = ?", (iid,))
            db.execute("DELETE FROM incident_comments WHERE incident_id = ?", (iid,))
            docs = [r["document_id"] for r in db.query("SELECT document_id FROM evidence_documents WHERE incident_id = ?", (iid,))]
            for d in docs:
                db.execute("DELETE FROM evidence_chunks WHERE document_id = ?", (d,))
                db.execute("DELETE FROM evidence_documents WHERE document_id = ?", (d,))
            db.execute("DELETE FROM contamination_incidents WHERE incident_id = ?", (iid,))
        audit(db, actor, role, "DEMO_RESET", "SYSTEM", "demo", {"incidents_removed": incs})
    return {"removed_incidents": incs}
