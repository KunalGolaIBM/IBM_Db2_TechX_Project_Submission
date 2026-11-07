"""Verification submission and retrieval."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, Response

from app.api.deps import get_pipeline, get_repository
from app.db.repository import Db2Repository
from app.schemas.verification import (
    VerificationListResponse,
    VerificationResponse,
    VerificationSummary,
    VerifyRequest,
)
from app.services.pipeline import VerificationPipeline
from app.services.report_generator import build_json_report, build_markdown_report

router = APIRouter(tags=["verification"])


@router.post("/api/verify", response_model=VerificationResponse)
def verify(
    request: VerifyRequest,
    pipeline: VerificationPipeline = Depends(get_pipeline),
) -> VerificationResponse:
    result = pipeline.verify(
        submitted_text=request.submitted_text,
        document_ids=request.document_ids,
        evidence_text=request.evidence_text,
        evidence_title=request.evidence_title,
    )
    return VerificationResponse(**result)


@router.get("/api/verifications", response_model=VerificationListResponse)
def list_verifications(
    limit: int = 25,
    repository: Db2Repository = Depends(get_repository),
) -> VerificationListResponse:
    safe_limit = max(1, min(limit, 100))
    sessions = repository.list_sessions(limit=safe_limit)
    return VerificationListResponse(
        verifications=[VerificationSummary(**session) for session in sessions]
    )


@router.get("/api/verifications/{session_id}/export")
def export_verification(
    session_id: int = Path(gt=0),
    format: str = Query("json", pattern="^(json|markdown|md)$"),
    repository: Db2Repository = Depends(get_repository),
) -> Response:
    session = repository.get_session(session_id)
    if format in ("markdown", "md"):
        body = build_markdown_report(session)
        media_type = "text/markdown; charset=utf-8"
        extension = "md"
    else:
        body = build_json_report(session)
        media_type = "application/json"
        extension = "json"
    return Response(
        content=body,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="aegis-session-{session_id}.{extension}"'
        },
    )


@router.get("/api/verifications/{session_id}", response_model=VerificationResponse)
def get_verification(
    session_id: int = Path(gt=0),
    repository: Db2Repository = Depends(get_repository),
) -> VerificationResponse:
    return VerificationResponse(**repository.get_session(session_id))
