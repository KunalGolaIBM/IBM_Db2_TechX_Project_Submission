import json
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.app.database.base import get_db
from backend.app.schemas.safety_schemas import AIIncidentAssistanceRequest, AIIncidentAssistanceResponse
from backend.app.api.deps import get_current_user
from backend.app.models.entities import User, Incident, AIAnalysisRecord, AuditEvent
from backend.app.ai.crewai.agents import crew_orchestrator
from backend.app.ai.haystack.rag_pipeline import retrieve_safety_guidance

router = APIRouter(prefix="/ai", tags=["AI Safety Intelligence"])

@router.post("/incident-assistance", response_model=AIIncidentAssistanceResponse)
def get_incident_ai_assistance(
    req: AIIncidentAssistanceRequest,
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
        incident = db.query(Incident).filter(Incident.id == req.incident_id).first()
        if incident is None:
            raise HTTPException(status_code=404, detail="Incident not found")

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
        db.add(AuditEvent(
            user_id=current_user.id,
            action="ai_triage",
            resource_type="incident",
            resource_id=str(incident.id),
            details_json=json.dumps({"priority": workflow_result["suggested_priority"]}),
        ))
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
        persisted_analysis_id=persisted_id
    )

@router.get("/guidance", response_model=Dict[str, Any])
def query_knowledge_base(
    query: str = Query(..., description="Safety question or emergency topic"),
    category: Optional[str] = Query(None, description="Optional category filter"),
    current_user: User = Depends(get_current_user)
):
    """
    Direct interface to the BM25 knowledge base for verified SOPs and civic guidance.
    """
    return retrieve_safety_guidance(query=query, category=category)
