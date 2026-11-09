from fastapi import APIRouter, HTTPException
from app.models.schemas import HealthResponse, DbHealthResponse
from app.db import db_manager

router = APIRouter(tags=["Health"])

@router.get("/health", response_model=HealthResponse)
def get_health():
    return HealthResponse(
        status="OK",
        service="finsight-ai-service",
        version="0.1.0"
    )

@router.get("/health/db", response_model=DbHealthResponse)
def get_db_health():
    try:
        check = db_manager.health_check()
        return DbHealthResponse(**check)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"IBM Db2 FINDB is unreachable: {e}"
        )
