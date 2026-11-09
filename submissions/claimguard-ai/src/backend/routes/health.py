"""
ClaimGuard AI - Health Check Router
Provides live system and IBM Db2 database health probes.
"""

from datetime import datetime, timezone
from fastapi import APIRouter
from ..config import settings
from ..database.connection import db2_manager
from ..models.schemas import HealthResponse

router = APIRouter(prefix="/api", tags=["System & Health"])


@router.get("/health", response_model=HealthResponse)
def get_system_health():
    """
    Returns full health status of ClaimGuard AI, including live IBM Db2 probe,
    driver availability, and Gemini configuration.
    """
    db_health = db2_manager.check_health()
    overall_status = "healthy" if db_health.get("connected") else ("degraded" if settings.DEMO_MODE else "unhealthy")

    return HealthResponse(
        status=overall_status,
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        database=db_health,
        gemini_configured=bool(settings.GEMINI_API_KEY),
        demo_mode=settings.DEMO_MODE,
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@router.get("/db/health")
def get_db2_health():
    """Detailed IBM Db2 connection diagnosis."""
    return db2_manager.check_health()
