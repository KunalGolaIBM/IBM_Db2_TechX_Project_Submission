from fastapi import APIRouter
from datetime import datetime, timezone
from app.core.config import settings
from app.database.db2_connection import db2_manager

router = APIRouter(tags=["Health"])

@router.get("/health")
def health_status():
    """
    GET /health and GET /api/v1/health
    Evaluates service operational state and live IBM Db2 connection.
    """
    db2_status = db2_manager.status
    is_live = bool(db2_status["driver_available"] and db2_status["connected"])

    return {
        "status": "ok",
        "state": "healthy",
        "database": settings.database_name,
        "ai": {
            "engine": "IBM Db2 & Haystack 384-dim COSINE Vector Matcher",
            "model": settings.EMBEDDING_MODEL,
        },
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "db2": {
            "connected": is_live,
            "driver_available": db2_status["driver_available"],
            "driver_error": db2_status["driver_error"],
            "configured": db2_status["configured"],
            "hostname": db2_status["hostname"],
            "database": db2_status["database"],
            "schema": settings.DB2_SCHEMA,
            "mode": "live_db2" if is_live else "local_fallback",
        },
        "haystack": {
            "document_store": "IBMDb2DocumentStore",
            "table": settings.DB2_TABLE_KB,
            "dimension": settings.EMBEDDING_DIM,
            "metric": settings.DISTANCE_METRIC,
        },
    }
