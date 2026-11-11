"""FastAPI application implementing docs/API_CONTRACT.md (v1.1.0).

Connections by role (least privilege):
* analytical SQL and the registry hash check run as the read-only reader (DB2_READER_USER);
* audit writes and audit reads run as the audit account (DB2_AUDIT_USER: INSERT + SELECT on
  QUERY_AUDIT_LOG only);
* only /api/health uses the admin connection (catalog checks).
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Callable

from fastapi import Depends, FastAPI, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from metricguard import API_CONTRACT_VERSION, __version__
from metricguard.config import get_settings
from metricguard.core.examples import EXAMPLES
from metricguard.core.registry import (
    DATA_COVERAGE_END,
    DATA_COVERAGE_START,
    DIMENSIONS,
    FILTERS,
    METRICS,
    registry_fingerprint,
)
from metricguard.analysis.pipeline import AnalysisService, audit_record, render_response
from metricguard.db import Db2Client, Db2Error
from metricguard.planner import PlannerUnavailableError, build_planner

from . import audit_repo
from .schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    AuditDetail,
    AuditListResponse,
    DatabaseHealth,
    DataCoverage,
    DimensionInfo,
    ErrorBody,
    ErrorCode,
    ErrorDetail,
    ErrorResponse,
    ExampleInfo,
    ExamplesResponse,
    FilterInfo,
    HealthResponse,
    MetricInfo,
    MetricsResponse,
    PlannerHealth,
    RegistryHealth,
    ValidationStatus,
)

settings = get_settings()
log = logging.getLogger("metricguard.api")

app = FastAPI(
    title="MetricGuard API",
    version=API_CONTRACT_VERSION,
    description="Trustworthy AI analytics on IBM Db2: governed metrics, inspectable SQL, verification and audit.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

_ERRORS: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse, "description": "Not found"},
    422: {"model": ErrorResponse, "description": "Invalid request"},
    503: {"model": ErrorResponse, "description": "Database unavailable"},
}


def _error(status: int, code: ErrorCode, message: str, *, details=None, sqlstate=None, request_id=None) -> JSONResponse:
    body = ErrorResponse(
        request_id=request_id,
        error=ErrorBody(code=code, message=message, details=details or [], sqlstate=sqlstate),
    )
    return JSONResponse(status_code=status, content=body.model_dump(mode="json"))


@app.exception_handler(RequestValidationError)
async def _validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        ErrorDetail(field=".".join(str(p) for p in e["loc"] if p not in ("body", "query", "path")) or None,
                    issue=e["msg"])
        for e in exc.errors()
    ]
    return _error(422, ErrorCode.INVALID_REQUEST, "Request validation failed.", details=details)


@app.exception_handler(Exception)
async def _internal_handler(_: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error: %s", type(exc).__name__)
    return _error(500, ErrorCode.INTERNAL_ERROR, "Unexpected server error.")


@app.exception_handler(Db2Error)
async def _db2_handler(request: Request, exc: Db2Error) -> JSONResponse:
    # An intermittent 503 on GET /api/audit was seen once and never reproduced. Log enough to tell a
    # connection failure from a query failure. Db2Error text is already sanitized (no PWD); the
    # response body stays generic.
    log.warning("Db2 error -> 503 on %s %s (SQLSTATE %s, SQLCODE %s): %s", request.method, request.url.path,
                exc.sqlstate, exc.sqlcode, str(exc)[:300])
    return _error(503, ErrorCode.DATABASE_UNAVAILABLE, "IBM Db2 is unavailable.", sqlstate=exc.sqlstate)


# --------------------------------------------------------------------------------------
@app.get("/api/health", response_model=HealthResponse, responses={503: {"model": HealthResponse}})
def health() -> JSONResponse:
    db_health: DatabaseHealth
    hash_match: bool | None = None
    try:
        start = time.perf_counter()
        with Db2Client(settings) as db:
            info = db.server_identity()
            latency = round((time.perf_counter() - start) * 1000, 1)
            tables = db.scalar(
                "SELECT COUNT(*) FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TYPE = 'T' AND TABNAME IN "
                "('ORDERS','ORDER_ITEMS','PRODUCTS','REFUNDS','METRIC_DEFINITIONS','QUERY_AUDIT_LOG')",
                (settings.db2_schema,),
            )
            if tables == 6:
                stored = {
                    (r[0], r[1]): r[2].strip()
                    for r in db.query(
                        "SELECT METRIC_NAME, METRIC_VERSION, DEFINITION_HASH FROM METRICGUARD.METRIC_DEFINITIONS "
                        "WHERE LIFECYCLE_STATUS = 'APPROVED'"
                    ).rows
                }
                hash_match = all(stored.get((m.name, m.version)) == m.definition_hash() for m in METRICS.values())
        db_health = DatabaseHealth(
            status="up", server_version=f"{info['dbms_name']} {info['dbms_version']}", service_level=info["service_level"],
            database=settings.db2_database, schema_name=settings.db2_schema, latency_ms=latency,
            tables_present=tables,
        )
    except Db2Error as exc:
        db_health = DatabaseHealth(
            status="down", database=settings.db2_database, schema_name=settings.db2_schema,
            error=ErrorBody(code=ErrorCode.DATABASE_UNAVAILABLE, message="IBM Db2 is unavailable.",
                            sqlstate=exc.sqlstate),
        )
    ok = db_health.status == "up" and db_health.tables_present == 6 and hash_match is True
    body = HealthResponse(
        status="ok" if ok else "degraded",
        api_version=API_CONTRACT_VERSION,
        service_version=__version__,
        time=datetime.now(timezone.utc),
        database=db_health,
        registry=RegistryHealth(metrics=len(METRICS), fingerprint=registry_fingerprint(), db_hash_match=hash_match),
        planner=_planner_health(),
    )
    return JSONResponse(status_code=200 if db_health.status == "up" else 503, content=body.model_dump(mode="json"))


@app.get("/api/metrics", response_model=MetricsResponse)
def metrics() -> MetricsResponse:
    return MetricsResponse(
        registry_fingerprint=registry_fingerprint(),
        data_coverage=DataCoverage(start_date=DATA_COVERAGE_START, end_date=DATA_COVERAGE_END),
        metrics=[
            MetricInfo(
                **m.model_dump(exclude={"measures", "formula"}, mode="json"),
                definition_hash=m.definition_hash(),
            )
            for m in METRICS.values()
        ],
        dimensions=[
            DimensionInfo(name=d.name, display_name=d.display_name, description=d.description,
                          data_type=d.data_type, allowed_values=d.allowed_values)
            for d in DIMENSIONS.values()
        ],
        filters=[
            FilterInfo(name=f.name, display_name=f.display_name, operators=list(f.operators),
                       allowed_values=f.allowed_values)
            for f in FILTERS.values()
        ],
    )


@app.get("/api/examples", response_model=ExamplesResponse)
def examples() -> ExamplesResponse:
    return ExamplesResponse(
        examples=[
            ExampleInfo(id=e.id, question=e.question, category=e.category, description=e.description,
                        expected_status=ValidationStatus(e.expected_status))
            for e in EXAMPLES
        ]
    )


# --------------------------------------------------------------------------------------
# Dependencies (overridable in tests through app.dependency_overrides)
# --------------------------------------------------------------------------------------
_service_cache: dict[str, AnalysisService | None] = {}


def get_analysis_service() -> AnalysisService | None:
    if "default" not in _service_cache:
        planner = build_planner(settings)
        _service_cache["default"] = AnalysisService(settings, planner) if planner else None
    return _service_cache["default"]


def _audit_client() -> Db2Client:
    return Db2Client(settings, role="audit" if settings.audit_configured else "admin")


def get_audit_writer() -> Callable[[dict[str, Any]], bool]:
    def write(record: dict[str, Any]) -> bool:
        try:
            with _audit_client() as db:
                audit_repo.insert(db, record)
            return True
        except Db2Error as exc:
            log.warning("audit write failed (SQLSTATE %s)", exc.sqlstate)
            return False

    return write


def get_audit_reader() -> Db2Client:
    return _audit_client()


def _planner_health() -> PlannerHealth:
    service = get_analysis_service()
    if service is None:
        return PlannerHealth(status="not_configured")
    p = service.planner
    return PlannerHealth(status="ready", provider=p.provider,
                         model=p.model, execution_mode=p.execution_mode)


@app.post("/api/analyze", response_model=AnalyzeResponse,
          responses={**_ERRORS, 503: {"model": ErrorResponse, "description": "Planner unavailable"},
                     500: {"model": ErrorResponse, "description": "Internal error"}})
def analyze(
    req: AnalyzeRequest,
    service: Annotated[AnalysisService | None, Depends(get_analysis_service)],
    write_audit: Annotated[Callable[[dict[str, Any]], bool], Depends(get_audit_writer)],
) -> JSONResponse:
    if service is None:
        return _error(503, ErrorCode.PLANNER_UNAVAILABLE, "The configured AI provider has no credentials "
                      "(AI_PROVIDER=meta needs MODEL_API_KEY; anthropic needs ANTHROPIC_API_KEY). "
                      "MetricGuard does not fall back to the demo planner; set AI_PROVIDER=demo to use it.")
    try:
        outcome = service.analyze(req.question, max_rows=req.options.max_rows)
    except PlannerUnavailableError as exc:
        return _error(503, ErrorCode.PLANNER_UNAVAILABLE, str(exc))
    body = render_response(outcome)
    AnalyzeResponse.model_validate(body)  # contract check before anything is persisted
    persisted = write_audit(audit_record(outcome, body))
    body["audit"] = {"persisted": persisted, "url": f"/api/audit/{outcome.request_id}" if persisted else None}
    return JSONResponse(content=AnalyzeResponse.model_validate(body).model_dump(mode="json"))


@app.get("/api/audit", response_model=AuditListResponse, responses=_ERRORS)
def audit_list(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    status: ValidationStatus | None = None,
) -> AuditListResponse:
    with get_audit_reader() as db:
        items, total = audit_repo.list_summaries(db, limit=limit, offset=offset,
                                                 status=status.value if status else None)
    return AuditListResponse(items=items, total=total, limit=limit, offset=offset)


@app.get("/api/audit/{request_id}", response_model=AuditDetail, responses=_ERRORS)
def audit_detail(request_id: Annotated[uuid.UUID, Path(description="UUID returned by /api/analyze")]):
    with get_audit_reader() as db:
        detail = audit_repo.get_detail(db, str(request_id))
    if detail is None:
        return _error(404, ErrorCode.AUDIT_NOT_FOUND, f"No audit record for request_id {request_id}.",
                      request_id=str(request_id))
    return AuditDetail(**detail)
