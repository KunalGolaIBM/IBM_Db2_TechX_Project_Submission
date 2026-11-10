"""Investigation, evidence, recommendation and review endpoints (all authenticated)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from civiclens.agent import investigate
from civiclens.api.deps import get_db
from civiclens.auth import Analyst, AnyUser, Principal, Reviewer
from civiclens.config import get_settings
from civiclens.db import investigation_repo as inv_repo
from civiclens.db.connection import Db2Session
from civiclens.domain.errors import ForbiddenError, NotFoundError
from civiclens.domain.investigation_models import (
    AuditEntry,
    DecisionRequest,
    EvidenceCreate,
    EvidenceItem,
    GeneratorType,
    Investigation,
    InvestigationCreate,
    InvestigationStatus,
    Recommendation,
    RecommendationDraft,
    RecommendationListItem,
    RecommendationStatus,
    RunRequest,
    RunResult,
)

router = APIRouter(prefix="/api", tags=["investigations"])
DB = Annotated[Db2Session, Depends(get_db)]
User = Annotated[Principal, AnyUser]
AnalystUser = Annotated[Principal, Analyst]
ReviewerUser = Annotated[Principal, Reviewer]


@router.post("/investigations", response_model=Investigation, status_code=201)
def create_investigation(user: AnalystUser, body: InvestigationCreate, db: DB) -> Investigation:
    return inv_repo.create_investigation(
        db, title=body.title, question=body.question, created_by=user.user_id
    )


@router.get("/investigations", response_model=list[Investigation])
def list_investigations(
    user: User,
    db: DB,
    status: InvestigationStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=inv_repo.MAX_LIST)] = 50,
) -> list[Investigation]:
    return inv_repo.list_investigations(db, status=status, limit=limit)


@router.get("/investigations/{investigation_id}", response_model=Investigation)
def get_investigation(investigation_id: int, user: User, db: DB) -> Investigation:
    return inv_repo.require_investigation(db, investigation_id)


@router.get("/investigations/{investigation_id}/evidence", response_model=list[EvidenceItem])
def get_evidence(investigation_id: int, user: User, db: DB) -> list[EvidenceItem]:
    inv_repo.require_investigation(db, investigation_id)
    return inv_repo.list_evidence(db, investigation_id)


@router.post("/investigations/{investigation_id}/evidence", response_model=list[EvidenceItem])
def attach_evidence(
    investigation_id: int, body: EvidenceCreate, user: AnalystUser, db: DB
) -> list[EvidenceItem]:
    inv_repo.add_evidence(db, investigation_id, body.complaint_ids, note=body.note)
    return inv_repo.list_evidence(db, investigation_id)


@router.get("/investigations/{investigation_id}/audit", response_model=list[AuditEntry])
def get_audit(
    investigation_id: int,
    user: User,
    db: DB,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[AuditEntry]:
    inv_repo.require_investigation(db, investigation_id)
    return inv_repo.audit_history(db, investigation_id, limit=limit)


@router.get("/investigations/{investigation_id}/recommendations", response_model=list[Recommendation])
def get_recommendations(investigation_id: int, user: User, db: DB) -> list[Recommendation]:
    inv_repo.require_investigation(db, investigation_id)
    return inv_repo.list_recommendations(db, investigation_id)


@router.post(
    "/investigations/{investigation_id}/recommendations", response_model=Recommendation, status_code=201
)
def propose_recommendation(
    investigation_id: int, body: RecommendationDraft, user: AnalystUser, db: DB
) -> Recommendation:
    """Manual proposal by an analyst. Same evidence validation as the agents; always PROPOSED."""
    with db.transaction():
        rec_id = inv_repo.create_recommendation(
            db,
            investigation_id,
            body,
            generator=GeneratorType.MANUAL,
            model_name=None,
            actor_id=user.user_id,
        )
        inv_repo.transition_status(
            db,
            investigation_id,
            from_statuses=[InvestigationStatus.OPEN],
            to_status=InvestigationStatus.PENDING_REVIEW,
        )
    rec = inv_repo.get_recommendation(db, rec_id)
    assert rec is not None
    return rec


@router.post("/investigations/{investigation_id}/run", response_model=RunResult)
def run_investigation(
    investigation_id: int, user: AnalystUser, db: DB, body: RunRequest | None = None
) -> RunResult:
    return investigate.run_investigation(
        db,
        investigation_id,
        requested_by=user.user_id,
        request=body or RunRequest(),
        settings=get_settings(),
    )


@router.get("/recommendations", response_model=list[RecommendationListItem])
def list_all_recommendations(
    user: User,
    db: DB,
    status: RecommendationStatus | None = None,
    generator: GeneratorType | None = None,
    investigation_id: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=inv_repo.MAX_REC_LIST)] = 50,
) -> list[RecommendationListItem]:
    """Reviewer queue and history across investigations (pending first, then by priority)."""
    return inv_repo.list_recommendations_all(
        db, status=status, generator=generator, investigation_id=investigation_id, limit=limit
    )


@router.get("/recommendations/{recommendation_id}", response_model=Recommendation)
def get_recommendation(recommendation_id: int, user: User, db: DB) -> Recommendation:
    rec = inv_repo.get_recommendation(db, recommendation_id)
    if rec is None:
        raise NotFoundError("Recommendation not found.", code="RECOMMENDATION_NOT_FOUND")
    return rec


@router.post("/recommendations/{recommendation_id}/decision", response_model=Recommendation)
def decide_recommendation(
    recommendation_id: int, body: DecisionRequest, user: ReviewerUser, db: DB
) -> Recommendation:
    """Approve or reject. The reviewer is the authenticated principal, never a body field."""
    try:
        return inv_repo.decide(
            db,
            recommendation_id,
            reviewer=user.user_id,
            decision=body.decision,
            comment=body.comment,
        )
    except ForbiddenError as exc:
        inv_repo.record_denied(
            db,
            actor_id=user.user_id,
            action="REVIEW_DENIED",
            investigation_id=exc.details.get("investigation_id"),
            reason=exc.code,
        )
        raise
