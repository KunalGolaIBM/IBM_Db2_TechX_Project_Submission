"""REST API v1. All business logic lives in app.services / app.agents."""
from __future__ import annotations

import platform
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.agents import orchestrator
from app.core.config import get_settings
from app.core.security import Principal, get_principal, require
from app.database import db_status, get_db
from app.schemas.api import ActionUpdate, CommentCreate, Decision, GenerateRecall, IncidentCreate, Reinvestigate, VerificationUpdate
from app.services import dashboard, demo, evidence, incidents, recalls
from app.services.bootstrap import SAMPLE_LAB_REPORT
from app.services.traceability import affected_set, impact_analysis, trace_graph

router = APIRouter()


def _redact_supplier(obj: Any, p: Principal) -> Any:
    """Supplier contact details are visible only to roles with supplier:sensitive."""
    if p.can("supplier:sensitive"):
        return obj
    if isinstance(obj, dict):
        return {k: ("[restricted]" if k in ("contact_email", "contact_phone") else _redact_supplier(v, p)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact_supplier(x, p) for x in obj]
    return obj


# ------------------------------------------------------------------ system
@router.get("/health", tags=["system"])
def health() -> dict[str, Any]:
    s = get_settings()
    db = db_status()
    return {
        "status": "ok" if db.get("connected") else "degraded",
        "app": s.app_name,
        "database": db,
        "ai": {"provider": s.llm_provider, "model": s.llm_model or None, "configured": s.llm_configured,
               "mode": "CREWAI_LLM" if s.llm_configured else "DETERMINISTIC_FALLBACK",
               "note": None if s.llm_configured else "No LLM credentials: agents run in clearly-labelled deterministic fallback mode."},
        "integrations": _integrations(),
        "python": platform.python_version(),
    }


def _integrations() -> dict[str, Any]:
    out = {}
    for mod, name in (("ibm_db", "ibm_db"), ("crewai", "crewai"), ("langchain_db2", "langchain-db2")):
        try:
            m = __import__(mod)
            out[name] = {"installed": True, "version": getattr(m, "__version__", "installed")}
        except Exception as exc:  # pragma: no cover
            out[name] = {"installed": False, "error": str(exc)[:120]}
    db = get_db()
    out["retrieval_engine"] = evidence.retrieval_engine(db)
    return out


@router.get("/dashboard/summary", tags=["dashboard"])
def dashboard_summary(p: Principal = Depends(require("read"))):
    return dashboard.summary(get_db())


@router.get("/audit-logs", tags=["audit"])
def audit_logs(entity_ref: str | None = Query(default=None, max_length=40), limit: int = Query(default=200, ge=1, le=1000),
               p: Principal = Depends(require("read"))):
    return dashboard.audit_logs(get_db(), entity_ref, limit)


# ------------------------------------------------------------------ incidents
@router.get("/incidents", tags=["incidents"])
def list_incidents(status_filter: str | None = Query(default=None, alias="status"), p: Principal = Depends(require("read"))):
    return incidents.list_incidents(get_db(), status_filter)


@router.post("/incidents", status_code=status.HTTP_201_CREATED, tags=["incidents"])
def create_incident(body: IncidentCreate, p: Principal = Depends(require("incident:write"))):
    return incidents.create_incident(get_db(), body.model_dump(), p.user_id, p.role)


@router.get("/incidents/{incident_id}", tags=["incidents"])
def get_incident(incident_id: str, p: Principal = Depends(require("read"))):
    db = get_db()
    inc = incidents.get_incident(db, incident_id)
    inc["comments"] = incidents.list_comments(db, incident_id)
    inc["evidence"] = evidence.list_documents(db, incident_id=incident_id)
    inc["recalls"] = [r for r in recalls.list_recalls(db) if r["incident_id"] == incident_id]
    inc["allowed_transitions"] = sorted(incidents.TRANSITIONS.get(inc["incident_status"], set()))
    return inc


@router.post("/incidents/{incident_id}/investigate", status_code=status.HTTP_202_ACCEPTED, tags=["investigation"])
def investigate(incident_id: str, background: bool = True, p: Principal = Depends(require("investigate"))):
    try:
        return orchestrator.start_investigation(get_db(), incident_id, p.user_id, p.role, background=background)
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.post("/incidents/{incident_id}/reinvestigate", status_code=status.HTTP_202_ACCEPTED, tags=["investigation"])
def reinvestigate(incident_id: str, body: Reinvestigate, p: Principal = Depends(require("investigate"))):
    db = get_db()
    if body.reason:
        incidents.add_comment(db, incident_id, f"Re-investigation requested: {body.reason}", p.user_id, p.role)
    try:
        return orchestrator.start_investigation(db, incident_id, p.user_id, p.role, background=True)
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.get("/incidents/{incident_id}/investigation", tags=["investigation"])
def get_investigation(incident_id: str, p: Principal = Depends(require("read"))):
    db = get_db()
    incidents.get_incident(db, incident_id)
    run = orchestrator.latest_run(db, incident_id)
    if not run:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No investigation run yet for this incident")
    return run


@router.post("/incidents/{incident_id}/comments", status_code=status.HTTP_201_CREATED, tags=["incidents"])
def add_comment(incident_id: str, body: CommentCreate, p: Principal = Depends(require("comment"))):
    return incidents.add_comment(get_db(), incident_id, body.body, p.user_id, p.role)


# ------------------------------------------------------------------ supply chain
@router.get("/supply-chain/trace/{ref}", tags=["supply-chain"])
def trace(ref: str, incident_id: str | None = None, p: Principal = Depends(require("read"))):
    db = get_db()
    affected: set[str] = set()
    sources = ([incidents.get_incident(db, incident_id)] if incident_id else
               [i for i in incidents.list_incidents(db) if i["incident_status"] not in ("COMPLETED", "REJECTED")])
    for inc in sources:
        affected |= affected_set(db, inc["source_ref"])
    return trace_graph(db, ref, affected)


@router.get("/supply-chain/impact/{lot_id}", tags=["supply-chain"])
def impact(lot_id: str, p: Principal = Depends(require("read"))):
    return _redact_supplier(impact_analysis(get_db(), lot_id), p)


@router.get("/supply-chain/catalog", tags=["supply-chain"])
def catalog(p: Principal = Depends(require("read"))):
    db = get_db()
    return {
        "lots": db.query("SELECT l.lot_id, i.ingredient_name, s.supplier_name, l.received_date, l.lot_status FROM ingredient_lots l "
                         "JOIN ingredients i ON i.ingredient_id = l.ingredient_id JOIN suppliers s ON s.supplier_id = l.supplier_id ORDER BY l.lot_id"),
        "batches": db.query("SELECT b.batch_id, b.batch_type, b.description, b.production_date, b.batch_status, p.product_name FROM production_batches b "
                            "LEFT JOIN finished_products p ON p.product_id = b.product_id ORDER BY b.batch_id"),
        "suppliers": _redact_supplier(db.query("SELECT supplier_id, supplier_name, country, region, certification, risk_tier, contact_email, "
                                               "contact_phone FROM suppliers ORDER BY supplier_id"), p),
    }


# ------------------------------------------------------------------ recalls
@router.get("/recalls", tags=["recalls"])
def list_recalls(status_filter: str | None = Query(default=None, alias="status"), p: Principal = Depends(require("read"))):
    return recalls.list_recalls(get_db(), status_filter)


@router.post("/recalls/generate", status_code=status.HTTP_201_CREATED, tags=["recalls"])
def generate(body: GenerateRecall, p: Principal = Depends(require("recall:generate"))):
    return recalls.generate_recall(get_db(), body.incident_id, p.user_id, p.role, body.run_id)


@router.get("/recalls/{recall_id}", tags=["recalls"])
def get_recall(recall_id: str, p: Principal = Depends(require("read"))):
    return recalls.get_recall(get_db(), recall_id)


@router.post("/recalls/{recall_id}/approve", tags=["recalls"])
def approve(recall_id: str, body: Decision, p: Principal = Depends(require("recall:approve"))):
    return recalls.approve(get_db(), recall_id, p.user_id, p.role, body.comment)


@router.post("/recalls/{recall_id}/reject", tags=["recalls"])
def reject(recall_id: str, body: Decision, p: Principal = Depends(require("recall:approve"))):
    return recalls.reject(get_db(), recall_id, p.user_id, p.role, body.comment)


@router.post("/recalls/{recall_id}/actions/{action_id}", tags=["recalls"])
def update_action(recall_id: str, action_id: str, body: ActionUpdate, p: Principal = Depends(require("recall:execute"))):
    return recalls.update_action(get_db(), recall_id, action_id, body.status, body.units_recovered, p.user_id, p.role, body.notes)


@router.post("/recalls/{recall_id}/simulate-acknowledgements", tags=["recalls"])
def simulate_acks(recall_id: str, p: Principal = Depends(require("recall:execute"))):
    return recalls.simulate_acknowledgements(get_db(), recall_id, p.user_id, p.role)


@router.post("/recalls/{recall_id}/complete", tags=["recalls"])
def complete(recall_id: str, body: Decision, p: Principal = Depends(require("recall:execute"))):
    return recalls.complete(get_db(), recall_id, p.user_id, p.role, body.comment)


# ------------------------------------------------------------------ evidence
@router.get("/evidence", tags=["evidence"])
def list_evidence(incident_id: str | None = None, doc_type: str | None = None, p: Principal = Depends(require("read"))):
    return evidence.list_documents(get_db(), incident_id, doc_type)


@router.get("/evidence/search", tags=["evidence"])
def search_evidence(q: str = Query(min_length=2, max_length=300), k: int = Query(default=8, ge=1, le=25),
                    incident_id: str | None = None, p: Principal = Depends(require("read"))):
    return evidence.search(get_db(), q, k, incident_id)


@router.post("/evidence/upload", status_code=status.HTTP_201_CREATED, tags=["evidence"])
async def upload_evidence(file: UploadFile = File(...), incident_id: str | None = Form(default=None),
                          doc_type: str | None = Form(default=None), p: Principal = Depends(require("evidence:write"))):
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"File exceeds {get_settings().max_upload_mb} MB limit")
    return evidence.ingest_document(get_db(), filename=file.filename or "upload", data=data, uploaded_by=p.user_id, role=p.role,
                                    incident_id=incident_id or None, doc_type=doc_type or None)


@router.get("/evidence/{document_id}", tags=["evidence"])
def get_evidence(document_id: str, p: Principal = Depends(require("read"))):
    return evidence.get_document(get_db(), document_id)


@router.post("/evidence/{document_id}/verification", tags=["evidence"])
def verify_evidence(document_id: str, body: VerificationUpdate, p: Principal = Depends(require("recall:approve"))):
    return evidence.set_verification(get_db(), document_id, body.status, p.user_id, p.role)


# ------------------------------------------------------------------ demo
@router.get("/demo/sample-lab-report", tags=["demo"])
def sample_report():
    return FileResponse(SAMPLE_LAB_REPORT, media_type="application/pdf", filename=SAMPLE_LAB_REPORT.name)


@router.get("/demo/tomato-incident", tags=["demo"])
def tomato_incident_template():
    return demo.TOMATO_INCIDENT


@router.post("/demo/tomato", status_code=status.HTTP_201_CREATED, tags=["demo"])
def run_demo(p: Principal = Depends(require("investigate"))):
    return demo.run_tomato_demo(get_db(), p.user_id, p.role)


@router.post("/demo/reset", tags=["demo"])
def reset_demo(p: Principal = Depends(require("recall:approve"))):
    return demo.reset_demo(get_db(), p.user_id, p.role)
