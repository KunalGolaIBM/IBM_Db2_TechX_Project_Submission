from fastapi import APIRouter
from backend.app.database.db2_connection import db2_manager
from backend.app.core.config import settings

router = APIRouter(tags=["Health"])

@router.get("/health")
def get_health():
    db2_status = db2_manager.status
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database": {
            "engine": "IBM Db2 Enterprise",
            "driver_available": db2_status["driver_available"],
            "configured": db2_status["configured"],
            "connected": db2_status["connected"],
            "fallback_storage": "Active SQLite/Local Repository",
        },
        "ai": {
            "embedding_model": settings.EMBEDDING_MODEL,
            "dimensions": settings.EMBEDDING_DIM,
            "scoring_engine": "Multi-Factor Eligibility + Vector Relevance",
        }
    }

