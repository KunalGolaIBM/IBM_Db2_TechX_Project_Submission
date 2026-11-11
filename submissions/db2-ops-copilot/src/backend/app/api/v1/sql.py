"""SQL routes: the validation gate and the M2 execution path.

- ``POST /api/v1/sql/validate`` — returns HTTP 200 for every well-formed
  *request*: an invalid SQL statement is a successful validation outcome
  (``valid: false`` + violations), not an API error. Malformed requests
  (missing/oversized body) yield the standard 422 error envelope.
- ``POST /api/v1/sql/execute`` — validates (fail-closed), applies the hard
  row cap, runs a best-effort EXPLAIN, executes read-only under the policy
  timeout, and records every attempt in APP.QUERY_EXECUTIONS. Rejections
  raise ``SqlRejectedError`` (422 envelope) after being persisted/audited.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request

from app.api.deps import build_explain_service, build_sql_execution, build_sql_guard
from app.schemas.dba import ExplainRequest, ExplainResponse
from app.schemas.sql import (
    SqlExecutionRequest,
    SqlExecutionResponse,
    SqlValidateRequest,
    SqlValidateResponse,
)

router = APIRouter(tags=["sql"])


@router.post("/sql/validate", response_model=SqlValidateResponse)
def post_sql_validate(
    payload: SqlValidateRequest, request: Request
) -> SqlValidateResponse:
    guard = build_sql_guard(request)
    return guard.validate(payload.sql)


@router.post("/sql/explain", response_model=ExplainResponse)
def post_sql_explain(payload: ExplainRequest, request: Request) -> ExplainResponse:
    """EXPLAIN a validated SELECT without executing it.

    HTTP 200 carries ``status`` OK / UNAVAILABLE / FAILED (graceful fallback
    when Db2, its EXPLAIN tables or the privilege are missing); SQL that fails
    the safety gate is a 422 ``SQL_REJECTED``.
    """
    request_id = getattr(request.state, "request_id", uuid.uuid4().hex[:16])
    return build_explain_service(request).explain(
        payload.sql, request_id=request_id, session_id=payload.session_id
    )


@router.post("/sql/execute", response_model=SqlExecutionResponse)
def post_sql_execute(
    payload: SqlExecutionRequest, request: Request
) -> SqlExecutionResponse:
    """Execute validated SQL with row cap + timeout, under the read-only account.

    Never executes unvalidated SQL: the service re-runs the full gate first
    and raises 422 ``SQL_REJECTED`` for anything that fails it.
    """
    request_id = getattr(request.state, "request_id", uuid.uuid4().hex[:16])
    service = build_sql_execution(request)
    return service.execute(
        payload.sql, request_id=request_id, session_id=payload.session_id
    )
