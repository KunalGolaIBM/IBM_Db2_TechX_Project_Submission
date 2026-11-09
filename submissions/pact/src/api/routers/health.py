"""Health and readiness endpoints for PACT service."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from api.db import check_db2_health
from api.models import HealthStatus

router = APIRouter(tags=["Health"])


@router.get("/health/live", summary="Liveness Probe")
def health_live():
    """Verify that FastAPI application process is up and running."""
    return {"status": "ALIVE"}


@router.get("/health/ready", response_model=HealthStatus, summary="Readiness Probe")
def health_ready():
    """Verify that FastAPI can execute queries against genuine IBM Db2 PACTDB."""
    try:
        health_data = check_db2_health()
        return health_data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "DB2_CONNECTION_FAILED",
                    "message": f"IBM Db2 readiness probe failed: {str(e)}",
                    "retryable": True,
                }
            },
        )

