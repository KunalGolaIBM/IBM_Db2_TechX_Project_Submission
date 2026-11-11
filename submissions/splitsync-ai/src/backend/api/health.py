"""Health check router for SplitSync AI."""

import logging
from typing import Any
from fastapi import APIRouter

try:
    from config import settings
except ImportError:
    from backend.config import settings

try:
    from db.connection import health_check
except ImportError:
    from backend.db.connection import health_check

logger = logging.getLogger("splitsync.health")

router = APIRouter(tags=["Health"])


def _check_db2_health() -> str:
    """Execute Db2 connectivity health check and return normalized status."""
    try:
        result = health_check()
        if isinstance(result, dict):
            status = result.get("status", "disconnected")
            if status == "connected":
                return "connected"
            message = result.get("message", "unknown error")
            return f"disconnected: {message}"
        elif isinstance(result, tuple):
            is_ok, msg = result
            return "connected" if is_ok else f"disconnected: {msg}"
        elif isinstance(result, bool):
            return "connected" if result else "disconnected: check failed"
        elif isinstance(result, str):
            return result
        return "connected"
    except Exception as exc:
        logger.warning("Db2 connection check failed: %s", exc)
        return f"disconnected: {exc}"


@router.get("/health")
async def get_health() -> dict[str, Any]:
    """Return health status of the backend and external dependencies."""
    try:
        db2_status = _check_db2_health()
    except Exception as exc:
        logger.error("Health check error: %s", exc)
        db2_status = f"disconnected: {exc}"

    return {
        "status": "healthy",
        "db2": db2_status,
        "version": "1.0.0",
        "environment": settings.app_env,
        "payment_mode": settings.payment_mode,
        "ai_provider": settings.ai_provider,
    }
