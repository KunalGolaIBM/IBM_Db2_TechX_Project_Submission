import json
from typing import Any, Dict, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from backend.app.database.base import get_db
from backend.app.schemas.safety_schemas import AIIncidentAssistanceRequest, AIIncidentAssistanceResponse
from backend.app.api.deps import get_current_user, is_staff
from backend.app.api.v1.incidents import _get_visible_incident
from backend.app.core.audit import record_audit
from backend.app.core.config import settings
from backend.app.models.entities import User, AIAnalysisRecord
from backend.app.ai.crewai.agents import crew_orchestrator
from backend.app.ai.haystack.rag_pipeline import retrieve_safety_guidance

router = APIRouter(prefix="/ai", tags=["AI Safety Intelligence"])

@router.post("/incident-assistance", response_model=AIIncidentAssistanceResponse)
def get_incident_ai_assistance(
    req: AIIncidentAssistanceRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Executes bounded CrewAI multi-agent workflow:
    1. IncidentIntakeAgent structures the text and flags missing info.
    2. SafetyTriageAssistant determines risk and preliminary priority.
    3. KnowledgeAssistant queries the BM25 knowledge base for verified municipal SOPs.

    If `incident_id` is supplied, the analysis is stored in `ai_analysis_records`
    (one row per incident, updated on re-run) and an `audit_events` row is written.
    """
    incident = None
    if req.incident_id is not None:
        incident = _get_visible_incident(db, req.incident_id, current_user)
        # Only the reporter or verified staff may attach an analysis to an incident.
        if not is_staff(current_user) and incident.reporter_id != current_user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only run triage on your own incidents.")

    workflow_result = crew_orchestrator.run_incident_assistance_workflow(
        raw_text=req.raw_text,
        reported_category=req.incident_type,
        location=req.location_address
    )

    persisted_id = None
    if incident is not None:
        record = db.query(AIAnalysisRecord).filter(AIAnalysisRecord.incident_id == incident.id).first()
        if record is None:
            record = AIAnalysisRecord(incident_id=incident.id)
            db.add(record)
        record.intake_summary = req.raw_text[:4000]
        record.suggested_priority = workflow_result["suggested_priority"]
        record.triage_reasoning = workflow_result["triage_reasoning"]
        record.recommended_actions_json = json.dumps(workflow_result["immediate_safety_checklist"])
        record.retrieved_protocols_json = json.dumps(workflow_result["retrieved_civic_protocols"])
        record_audit(db, "ai_triage", "incident", incident.id, user_id=current_user.id, request=request,
                     details={"priority": workflow_result["suggested_priority"]})
        db.commit()
        db.refresh(record)
        persisted_id = record.id

    return AIIncidentAssistanceResponse(
        parsed_category=workflow_result["parsed_category"],
        extracted_location=workflow_result["extracted_location"],
        suggested_priority=workflow_result["suggested_priority"],
        triage_reasoning=workflow_result["triage_reasoning"],
        missing_critical_info=workflow_result["missing_critical_info"],
        immediate_safety_checklist=workflow_result["immediate_safety_checklist"],
        retrieved_civic_protocols=workflow_result["retrieved_civic_protocols"],
        advisory_notice=workflow_result["advisory_notice"],
        persisted_analysis_id=persisted_id,
        escalated=workflow_result["escalated"],
        workflow_steps=workflow_result["workflow_steps"],
    )

@router.get("/guidance", response_model=Dict[str, Any])
def query_knowledge_base(
    query: str = Query(..., min_length=3, max_length=500, description="Safety question or emergency topic"),
    category: Optional[Literal["emergency_response", "child_safety", "elder_care", "hazard_mitigation",
                               "transit_safety", "responder_procedures"]] = Query(None, description="Protocol category filter"),
    audience: Optional[Literal["residents", "women", "guardians", "seniors", "caregivers", "responders"]] = Query(
        None, description="Only protocols written for this audience"),
    current_user: User = Depends(get_current_user),
):
    """Hybrid retrieval (Haystack BM25 + IBM Db2 vector search) with metadata filters; every result
    cites the passage that matched."""
    return retrieve_safety_guidance(query=query, category=category, audience=audience)


class CrewBriefingRequest(BaseModel):
    raw_text: str = Field(..., min_length=3, max_length=2000)
    incident_type: Optional[str] = Field(default=None, max_length=50)


@router.post("/crew-briefing", response_model=Dict[str, Any])
def crew_briefing(
    req: CrewBriefingRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Rule-based triage (CrewAI Flow) plus a multi-agent briefing written by IBM Granite through a
    CrewAI Crew, grounded in protocols retrieved from IBM Db2. If the local LLM is unavailable the
    rule-based result is still returned, with ``briefing_error`` explaining why."""
    from backend.app.ai.crewai.crew import run_briefing

    triage = crew_orchestrator.run_incident_assistance_workflow(req.raw_text, reported_category=req.incident_type)
    protocols = [{"title": p["title"], "source": p["source"], "cited_passage": p["protocol_snippet"], "excerpt": p["protocol_snippet"]}
                 for p in triage["retrieved_civic_protocols"]]
    briefing, error = None, None
    if settings.ENABLE_LLM_BRIEFING:
        try:
            briefing = run_briefing(req.raw_text, triage, protocols)
        except Exception as exc:  # degrade gracefully: the rule-based triage is always available
            error = f"LLM briefing unavailable: {type(exc).__name__}"
    else:
        error = "LLM briefing disabled by ENABLE_LLM_BRIEFING"
    record_audit(db, "ai_crew_briefing", "triage", None, user_id=current_user.id, request=request,
                 details={"priority": triage["suggested_priority"], "llm": briefing is not None,
                          "grounded": bool(briefing and briefing["grounded"])})
    db.commit()
    return {"triage": triage, "briefing": briefing, "briefing_error": error}
