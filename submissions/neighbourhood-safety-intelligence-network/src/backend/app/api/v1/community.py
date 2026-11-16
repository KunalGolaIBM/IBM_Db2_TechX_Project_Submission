from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from backend.app.analytics.insights import ACTIVE_STATUSES, CLOSED_STATUSES, compute_insights
from backend.app.database.base import get_db
from backend.app.models.entities import User, Incident, CommunityHazard
from backend.app.schemas.safety_schemas import (
    CommunityInsightsResponse, CommunityHazardCreate, CommunityHazardResponse
)
from backend.app.api.deps import get_current_user
from backend.app.ai.crewai.agents import crew_orchestrator

router = APIRouter(prefix="/community", tags=["Community Insights & Hazards"])

@router.get("/insights", response_model=CommunityInsightsResponse)
def get_community_insights(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    by_status = dict(db.query(Incident.status, func.count(Incident.id)).group_by(Incident.status).all())
    by_type = dict(db.query(Incident.incident_type, func.count(Incident.id)).group_by(Incident.incident_type).all())
    by_priority = dict(db.query(Incident.priority, func.count(Incident.id)).group_by(Incident.priority).all())
    total = sum(by_status.values())
    active = sum(n for s, n in by_status.items() if s in ACTIVE_STATUSES)
    resolved = sum(n for s, n in by_status.items() if s in CLOSED_STATUSES)

    hazards = db.query(CommunityHazard).filter(CommunityHazard.status.in_(["active", "verified"]))         .order_by(CommunityHazard.created_at.desc()).all()
    metrics = compute_insights(db)

    # Transparent heuristic: start at 100 and subtract for open incidents, hazards and missed SLAs.
    health_score = max(0, min(100, 100 - active * 4 - len(hazards) * 3 - metrics["sla_breaches"] * 6))
    advisory = crew_orchestrator.insights_agent.execute(
        total_incidents=total, active_count=active, hazard_count=len(hazards),
    )
    return CommunityInsightsResponse(
        total_incidents=total,
        active_incidents=active,
        resolved_incidents=resolved,
        incidents_by_type=by_type,
        incidents_by_priority=by_priority,
        active_hazards=[CommunityHazardResponse.model_validate(h) for h in hazards],
        safety_health_score=health_score,
        ai_safety_advisory=advisory,
        **metrics,
    )


@router.get("/hazards", response_model=List[CommunityHazardResponse])
def list_hazards(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    hazards = db.query(CommunityHazard).order_by(CommunityHazard.created_at.desc()).all()
    return [CommunityHazardResponse.model_validate(h) for h in hazards]

@router.post("/hazards", response_model=CommunityHazardResponse, status_code=status.HTTP_201_CREATED)
def report_hazard(
    req: CommunityHazardCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    hazard = CommunityHazard(
        reported_by_id=current_user.id,
        title=req.title,
        hazard_type=req.hazard_type,
        severity=req.severity,
        address=req.address,
        latitude=req.latitude,
        longitude=req.longitude,
        status="active" if current_user.role == "resident" else "verified"
    )
    db.add(hazard)
    db.commit()
    db.refresh(hazard)
    return CommunityHazardResponse.model_validate(hazard)
