"""Runs API Endpoints."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel

from backend.app.engine.exceptions import (
    InvalidActionError,
    PlanEngineError,
    PlanValidationError,
    UnsupportedResourceError,
)
from backend.app.engine.normalizer import parse_and_normalize
from backend.app.engine.orchestrator import (
    VerificationOrchestrator,
    get_verification_orchestrator,
)
from backend.app.engine.predictor import ImpactPredictor
from backend.app.models.error import APIError
from backend.app.models.run import Run, RunStatus, build_run_summary
from backend.app.models.verification import VerificationResult
from backend.app.repositories.run_repo import RunRepository, get_run_repository

router = APIRouter(prefix="/runs", tags=["Runs"])


class SubmitVerificationResponse(BaseModel):
    """Response returned upon submitting state for verification."""
    run_id: str
    status: RunStatus


class GetVerificationResponse(BaseModel):
    """Verification report details."""
    run_id: str
    status: RunStatus
    results: list[VerificationResult]


@router.post("", response_model=Run, status_code=status.HTTP_201_CREATED)
async def create_run(
    request: Request,
    strict: bool = Query(default=False, description="If true, unsupported resources cause HTTP 400 rejection"),
    repo: RunRepository = Depends(get_run_repository),
) -> Run:
    """Ingest a Terraform plan JSON artifact, validate, parse, predict, and return the complete Run report."""
    body = await request.body()
    if not body or not body.strip():
        raise APIError(
            code="INVALID_PAYLOAD",
            message="Request body cannot be empty.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        plan_artifact = json.loads(body)
    except json.JSONDecodeError as err:
        raise APIError(
            code="INVALID_PAYLOAD",
            message=f"Malformed JSON: {err.msg}.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if not isinstance(plan_artifact, dict):
        raise APIError(
            code="INVALID_PAYLOAD",
            message="Plan artifact must be a valid JSON object.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        norm_result = parse_and_normalize(plan_artifact, strict_supported_only=strict)
    except PlanValidationError as err:
        raise APIError(
            code="INVALID_PLAN",
            message=str(err),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    except UnsupportedResourceError as err:
        raise APIError(
            code="UNSUPPORTED_RESOURCE",
            message=str(err),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    except InvalidActionError as err:
        raise APIError(
            code="MALFORMED_ACTION",
            message=str(err),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    except PlanEngineError as err:
        raise APIError(
            code="INVALID_PLAN",
            message=str(err),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    predictor = ImpactPredictor()
    findings, predictions = predictor.evaluate(norm_result.changes)

    summary = build_run_summary(
        changes=norm_result.changes,
        findings=findings,
        unsupported_resources=norm_result.unsupported_resources,
        ignored_noops=norm_result.ignored_noops,
        ignored_reads=norm_result.ignored_reads,
    )

    run = Run(
        run_id=str(uuid.uuid4()),
        created_at=datetime.now(timezone.utc).isoformat(),
        status=RunStatus.PREDICTED,
        summary=summary,
        changes=norm_result.changes,
        findings=findings,
        predictions=predictions,
        unsupported_resources=norm_result.unsupported_resources,
        ignored_noops=norm_result.ignored_noops,
        ignored_reads=norm_result.ignored_reads,
        verification_results=[],
    )
    repo.save(run)

    return run


@router.get("/{run_id}", response_model=Run)
async def get_run(
    run_id: str,
    repo: RunRepository = Depends(get_run_repository),
) -> Run:
    """Retrieve full details of an analysis run by its UUID."""
    run = repo.get(run_id)
    if not run:
        raise APIError(
            code="RUN_NOT_FOUND",
            message=f"Run '{run_id}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return run


@router.post("/{run_id}/verification", response_model=SubmitVerificationResponse)
async def submit_verification(
    run_id: str,
    state_artifact: dict[str, Any],
    region: Optional[str] = Query(default=None, description="Optional target AWS region override"),
    repo: RunRepository = Depends(get_run_repository),
    orchestrator: VerificationOrchestrator = Depends(get_verification_orchestrator),
) -> SubmitVerificationResponse:
    """Submit a Terraform State JSON artifact to trigger post-deployment verification."""
    run = repo.get(run_id)
    if not run:
        raise APIError(
            code="RUN_NOT_FOUND",
            message=f"Run '{run_id}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    updated_run = orchestrator.verify_run(run=run, state_artifact=state_artifact, region=region)
    repo.save(updated_run)

    return SubmitVerificationResponse(
        run_id=updated_run.run_id,
        status=updated_run.status,
    )


@router.get("/{run_id}/verification", response_model=GetVerificationResponse)
async def get_verification(
    run_id: str,
    repo: RunRepository = Depends(get_run_repository),
) -> GetVerificationResponse:
    """Retrieve verification results for a run."""
    run = repo.get(run_id)
    if not run:
        raise APIError(
            code="RUN_NOT_FOUND",
            message=f"Run '{run_id}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return GetVerificationResponse(
        run_id=run.run_id,
        status=run.status,
        results=run.verification_results,
    )


@router.get("/{run_id}/audit")
async def get_run_audit_trail(
    run_id: str,
    repo: RunRepository = Depends(get_run_repository),
) -> dict[str, Any]:
    """Retrieve the immutable Db2 audit history for an infrastructure change run."""
    run = repo.get(run_id)
    if not run:
        raise APIError(
            code="RUN_NOT_FOUND",
            message=f"Run '{run_id}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    events = repo.get_audit_history(run_id)
    return {"run_id": run_id, "audit_events": events}


@router.get("/governance/summary")
async def get_governance_summary(
    repo: RunRepository = Depends(get_run_repository),
) -> dict[str, Any]:
    """Retrieve aggregated infrastructure change governance metrics from Db2."""
    return {
        "high_risk_changes": repo.get_high_risk_changes(),
        "verification_metrics": repo.get_verification_metrics(),
    }

