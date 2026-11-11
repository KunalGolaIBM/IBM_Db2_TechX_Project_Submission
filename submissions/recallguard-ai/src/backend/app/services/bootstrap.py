"""First-start bootstrap: seed evidence documents and replay two historical incidents
through the REAL pipeline (no hand-written results), so the dashboard has history.

  * CHI-2026-017 (chili powder, Salmonella)  -> investigated, approved, executed, COMPLETED
  * MLK-2026-233 (milk powder, presumptive Cronobacter) -> investigated, PENDING_APPROVAL
The tomato scenario (TOM-2026-041) is NOT pre-run: it is the live demo.
"""
from __future__ import annotations

import logging

from app.core.config import BACKEND_DIR
from app.database import Database

from . import evidence as ev
from . import recalls
from .incidents import create_incident

log = logging.getLogger("recallguard.bootstrap")
DOCS = BACKEND_DIR / "db" / "seed" / "documents"
SAMPLE_LAB_REPORT = DOCS / "lab_report_TOM-2026-041.pdf"

SEED_DOC_MAP = {  # quality_reports.document_id placeholder -> file
    "DOC-SEED-0001": ("coa_TOM-2026-041_valle_rosso.txt", "LAB_REPORT", True),
    "DOC-SEED-0002": ("qc_pasteurisation_log_PB-2026-1001.txt", "QC_RECORD", True),
    "DOC-SEED-0003": ("lab_report_CHI-2026-017.txt", "LAB_REPORT", True),
    "DOC-SEED-0004": ("notice_MLK-2026-233_presumptive.txt", "CONTAMINATION_NOTICE", False),
}


def bootstrap_history(db: Database) -> None:
    from app.agents.orchestrator import start_investigation

    if not DOCS.exists():
        log.warning("seed documents missing (run db/seed/generate_documents.py)")
        return
    ids = {}
    for placeholder, (fname, dtype, verified) in SEED_DOC_MAP.items():
        doc = ev.seed_document(db, DOCS / fname, doc_type=dtype, verified=verified)
        ids[placeholder] = doc["document_id"]
        db.execute("UPDATE quality_reports SET document_id = ? WHERE document_id = ?", (doc["document_id"], placeholder))
    ev.seed_document(db, DOCS / "supplier_certificate_SUP-001_fssc22000.txt", doc_type="SUPPLIER_CERTIFICATE", verified=True)

    actor, mgr = ("seed.analyst@recallguard.demo", "analyst"), ("seed.recall.manager@recallguard.demo", "recall_manager")

    # --- historical, completed recall -------------------------------------
    chi = create_incident(db, {"title": "Salmonella in red chili powder lot CHI-2026-017", "source_ref": "CHI-2026-017",
                               "contaminant": "Salmonella spp.", "contamination_category": "MICROBIAL", "severity": "HIGH",
                               "discovered_at": "2026-09-12 10:30:00",
                               "description": "Third-party lab (DAS-2026-09-0211) confirmed Salmonella in 2 of 5 samples."}, *actor)
    db.execute("UPDATE evidence_documents SET incident_id = ? WHERE document_id = ?", (chi["incident_id"], ids["DOC-SEED-0003"]))
    start_investigation(db, chi["incident_id"], *actor, background=False)
    rc = recalls.generate_recall(db, chi["incident_id"], *actor)
    recalls.approve(db, rc["recall_id"], *mgr, "Confirmed lab result; approve Class I recall of seasoning-derived snacks.")
    full = recalls.get_recall(db, rc["recall_id"])
    for a in full["actions"]:
        target = "ACKNOWLEDGED" if a["action_type"] == "NOTIFY" else "DONE"
        recalls.update_action(db, rc["recall_id"], a["action_id"], target, None, "simulated.partner", "system")
    recalls.complete(db, rc["recall_id"], *mgr, "All locations confirmed recovery (simulated).")

    # --- open investigation awaiting approval ---------------------------------
    mlk = create_incident(db, {"title": "Presumptive Cronobacter in milk powder MLK-2026-233", "source_ref": "MLK-2026-233",
                               "contaminant": "Cronobacter spp. (presumptive)", "contamination_category": "MICROBIAL",
                               "severity": "MEDIUM", "discovered_at": "2026-11-02 16:00:00",
                               "description": "Presumptive positive on enrichment; PCR confirmation pending."}, *actor)
    db.execute("UPDATE evidence_documents SET incident_id = ? WHERE document_id = ?", (mlk["incident_id"], ids["DOC-SEED-0004"]))
    start_investigation(db, mlk["incident_id"], *actor, background=False)
    recalls.generate_recall(db, mlk["incident_id"], *actor)
    log.info("bootstrap complete: %s (completed), %s (pending approval)", chi["incident_id"], mlk["incident_id"])
