"""Investigation cases, simulation, AI investigation, and review workflow router."""

from __future__ import annotations

import math
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status

from api.db import db_connection, db_transaction
from api.models import (
    AuditEventResponse,
    CaseDetail,
    CaseEvidence,
    CasePriorityType,
    CaseStatusType,
    CaseSummary,
    InvestigationRequest,
    InvestigationResponse,
    PaginatedResponse,
    ReviewDecisionCreate,
    ReviewDecisionResponse,
    SimulationRequest,
    SimulationResponse,
)
from api.services.cases import (
    CaseNotFoundError,
    ConcurrencyConflictError,
    InvalidStateTransitionError,
    get_case_detail,
    get_case_evidence,
    list_case_audit_events,
    list_cases,
    record_case_review,
)
from api.services.investigations import (
    LLMProviderExecutionError,
    LLMProviderNotConfiguredError,
    execute_agent_investigation,
)
from api.services.simulations import (
    CaseNotFoundError as SimCaseNotFoundError,
    InvalidSimulationParameterError,
    UnsupportedSimulationTypeError,
    execute_simulation,
)

router = APIRouter(prefix="/api/v1/cases", tags=["Investigation Cases"])


@router.get("", response_model=PaginatedResponse[CaseSummary], summary="List Investigation Cases")
def get_cases(
    page: int = Query(default=1, ge=1, description="Page number"),
    limit: int = Query(default=20, ge=1, le=100, description="Items per page"),
    status: Optional[CaseStatusType] = Query(default=None, description="Filter by case status"),
    priority: Optional[CasePriorityType] = Query(default=None, description="Filter by priority"),
    search: Optional[str] = Query(default=None, description="Search PO number, supplier, or item"),
):
    """Retrieve paginated list of procurement anomaly investigation cases."""
    with db_connection() as conn:
        items, total = list_cases(
            conn, page=page, limit=limit, status=status, priority=priority, search=search
        )
        pages = math.ceil(total / limit) if total > 0 else 1
        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            pages=pages,
        )


@router.get("/{id}", response_model=CaseDetail, summary="Get Case Details")
def get_case(id: int):
    """Retrieve complete metadata and rule findings for a single investigation case."""
    with db_connection() as conn:
        try:
            return get_case_detail(conn, id)
        except CaseNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "CASE_NOT_FOUND", "message": str(e), "retryable": False}},
            )


@router.get("/{id}/evidence", response_model=CaseEvidence, summary="Get Case Evidence Records")
def get_evidence(id: int):
    """Retrieve exact Db2 source records (table and id) for audit inspection."""
    with db_connection() as conn:
        try:
            return get_case_evidence(conn, id)
        except CaseNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "CASE_NOT_FOUND", "message": str(e), "retryable": False}},
            )


@router.post("/{id}/simulations", response_model=SimulationResponse, summary="Execute Counterfactual Simulation")
def create_simulation(id: int, payload: SimulationRequest):
    """Execute counterfactual simulation in memory and persist result in Db2 SCENARIO_RUNS."""
    try:
        with db_transaction() as conn:
            return execute_simulation(
                conn,
                case_id=id,
                simulation_type=payload.simulation_type,
                parameters=payload.parameters.model_dump(),
            )
    except (CaseNotFoundError, SimCaseNotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "CASE_NOT_FOUND", "message": str(e), "retryable": False}},
        )
    except UnsupportedSimulationTypeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "UNSUPPORTED_SIMULATION_TYPE", "message": str(e), "retryable": False}},
        )
    except InvalidSimulationParameterError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_PARAMETERS", "message": str(e), "retryable": False}},
        )


@router.post("/{id}/investigations", response_model=InvestigationResponse, summary="Execute AI Evidence Investigation")
def create_investigation(id: int, payload: Optional[InvestigationRequest] = None):
    """Execute LangChain AI evidence investigation using scoped read-only Db2 tools."""
    max_calls = payload.max_tool_calls if payload else 8
    try:
        with db_transaction() as conn:
            return execute_agent_investigation(
                conn,
                case_id=id,
                max_tool_calls=max_calls,
            )
    except CaseNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "CASE_NOT_FOUND", "message": str(e), "retryable": False}},
        )
    except LLMProviderNotConfiguredError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "LLM_PROVIDER_NOT_CONFIGURED", "message": str(e), "retryable": False}},
        )
    except LLMProviderExecutionError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": {"code": "LLM_PROVIDER_ERROR", "message": str(e), "retryable": True}},
        )


@router.post("/{id}/submit-review", response_model=ReviewDecisionResponse, summary="Submit Review Decision")
@router.post("/{id}/reviews", response_model=ReviewDecisionResponse, summary="Submit Review Decision (Alias)")
def submit_review(id: int, payload: ReviewDecisionCreate):
    """Record an auditor review decision with optimistic locking in a single atomic Db2 transaction."""
    try:
        with db_transaction() as conn:
            return record_case_review(
                conn,
                case_id=id,
                decision=payload.decision,
                reviewer=payload.reviewer,
                reviewer_notes=payload.reviewer_notes,
                rationale=payload.rationale,
                expected_version=payload.expected_version,
            )
    except CaseNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "CASE_NOT_FOUND", "message": str(e), "retryable": False}},
        )
    except ConcurrencyConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "CONCURRENCY_CONFLICT", "message": str(e), "retryable": True}},
        )
    except InvalidStateTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_STATE_TRANSITION", "message": str(e), "retryable": False}},
        )


@router.get("/{id}/audit", response_model=list[AuditEventResponse], summary="Get Case Audit Trail")
def get_audit_trail(id: int):
    """Retrieve chronological audit trail of all actions and state transitions for a case."""
    with db_connection() as conn:
        try:
            get_case_detail(conn, id)  # verify existence
            return list_case_audit_events(conn, id)
        except CaseNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "CASE_NOT_FOUND", "message": str(e), "retryable": False}},
            )
