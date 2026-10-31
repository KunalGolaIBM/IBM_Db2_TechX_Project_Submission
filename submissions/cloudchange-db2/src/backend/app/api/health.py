"""Health and Liveness API Endpoints."""

from typing import Any
from fastapi import APIRouter
from backend.app.config import settings

router = APIRouter(tags=["System"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Liveness probe verifying service availability."""
    return {
        "status": "healthy",
        "service": "cloudchange-api",
        "version": settings.VERSION,
    }


@router.get("/health/db2")
async def db2_health_check() -> dict[str, Any]:
    """Dedicated health check verifying IBM Db2 connectivity status."""
    from backend.app.db2.connection import Db2ConnectionManager
    cm = Db2ConnectionManager()
    is_live = cm.check_connection()
    return {
        "service": "cloudchange-api",
        "backend": "ibm_db2",
        "connected": is_live,
        "configured": cm.config.is_configured(),
        "database": cm.config.database,
        "host": cm.config.host,
        "port": cm.config.port,
    }
