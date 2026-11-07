"""Health endpoints. Liveness never depends on external services."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.api.deps import get_repository
from app.core.config import get_settings
from app.core.errors import DatabaseUnavailableError
from app.db.repository import Db2Repository
from app.schemas.common import DbHealthResponse, HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])

VERSION = "0.2.0"


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=VERSION,
        environment=settings.aegis_env,
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model,
        database=settings.db2_database,
    )


@router.get(
    "/api/db/health",
    response_model=DbHealthResponse,
    responses={503: {"model": DbHealthResponse, "description": "IBM Db2 is unreachable"}},
)
def db_health(repository: Db2Repository = Depends(get_repository)):
    settings = get_settings()
    try:
        details = repository.health()
        return DbHealthResponse(
            connected=True,
            database=settings.db2_database,
            host=settings.db2_host,
            schema_name=details["schema"],
            server=details["server"],
            server_time=details["server_time"],
            tables=details["tables"],
            missing_tables=details["missing_tables"],
        )
    except DatabaseUnavailableError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "connected": False,
                "database": settings.db2_database,
                "host": settings.db2_host,
                "schema": settings.db2_schema,
                "tables": [],
                "missing_tables": [],
                "message": "IBM Db2 is not reachable. Start the database and verify credentials.",
            },
        )
    except Exception:
        logger.exception("Database health check failed")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "connected": False,
                "database": settings.db2_database,
                "host": settings.db2_host,
                "schema": settings.db2_schema,
                "tables": [],
                "missing_tables": [],
                "message": "The database health check failed. See server logs for diagnostics.",
            },
        )
