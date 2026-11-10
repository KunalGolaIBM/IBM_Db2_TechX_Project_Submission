from fastapi import APIRouter
from ..database import db_manager

router = APIRouter(tags=["Health & Status"])

@router.get("/health")
def health_check():
    """System health check endpoint."""
    db_stat = db_manager.get_status()
    return {
        "status": "healthy" if db_stat.get("connected") else "degraded",
        "service": "Db2Sentinel AI Backend",
        "database_mode": db_stat.get("active_mode"),
        "database_engine": db_stat.get("engine")
    }

@router.get("/db2/status")
def db2_status():
    """Detailed IBM Db2 connection diagnostics."""
    return db_manager.get_status()
