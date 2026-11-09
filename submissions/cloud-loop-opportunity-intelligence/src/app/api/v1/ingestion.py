from fastapi import APIRouter, Depends, Query
from typing import List
from backend.app.schemas.ingestion import IngestionBatchRequest, IngestionRunResponse
from backend.app.services.ingestion_service import ingestion_service
from backend.app.repositories.ingestion_repository import ingestion_repo
from backend.app.core.security import verify_admin_key

router = APIRouter(prefix="/ingestion", tags=["Data Ingestion & Provenance"])

@router.post("", dependencies=[Depends(verify_admin_key)])
def ingest_batch(payload: IngestionBatchRequest):
    result = ingestion_service.ingest_records(
        source=payload.source,
        raw_items=payload.items,
    )
    return result

@router.get("/runs", response_model=List[IngestionRunResponse])
def get_ingestion_runs(limit: int = Query(10, ge=1, le=50)):
    return [IngestionRunResponse(**r) for r in ingestion_repo.list_runs(limit=limit)]

