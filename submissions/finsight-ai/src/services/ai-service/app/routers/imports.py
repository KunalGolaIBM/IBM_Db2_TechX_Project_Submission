import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Header, HTTPException, Query, status

from app.models.schemas import PreviewImportRequest, CommitImportRequest
from app.services.import_service import import_service
from app.routers.internal import verify_service_token

logger = logging.getLogger("finsight.imports.router")

router = APIRouter(prefix="/api/ai/imports", tags=["Imports"])

@router.post("/preview")
def preview_import(
    req: PreviewImportRequest,
    user_id: str = Query(...),
    x_service_token: str = Header(...)
) -> Dict[str, Any]:
    verify_service_token(x_service_token)
    try:
        return import_service.preview_import(
            user_id=user_id,
            filename=req.filename,
            csv_content=req.csv_content,
            custom_mapping=req.column_mapping
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Failed to generate CSV preview: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Preview error: {e}")

@router.post("/commit")
def commit_import(
    req: CommitImportRequest,
    user_id: str = Query(...),
    x_service_token: str = Header(...)
) -> Dict[str, Any]:
    verify_service_token(x_service_token)
    try:
        return import_service.commit_import(
            user_id=user_id,
            import_id=req.import_id,
            filename=req.filename,
            csv_content=req.csv_content,
            custom_mapping=req.column_mapping,
            skip_duplicates=req.skip_duplicates,
            account_id=req.account_id
        )
    except RuntimeError as e:
        if "currently processing" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Failed to commit CSV import: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Import error: {e}")

@router.get("/history")
def list_imports(
    user_id: str = Query(...),
    limit: int = Query(20, ge=1, le=100),
    x_service_token: str = Header(...)
) -> List[Dict[str, Any]]:
    verify_service_token(x_service_token)
    return import_service.list_imports(user_id=user_id, limit=limit)

@router.get("/{import_id}")
def get_import(
    import_id: str,
    user_id: str = Query(...),
    x_service_token: str = Header(...)
) -> Dict[str, Any]:
    verify_service_token(x_service_token)
    res = import_service.get_import(user_id=user_id, import_id=import_id)
    if not res:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import job not found.")
    return res

@router.post("/{import_id}/retry-indexing")
def retry_indexing(
    import_id: str,
    user_id: str = Query(...),
    x_service_token: str = Header(...)
) -> Dict[str, Any]:
    verify_service_token(x_service_token)
    try:
        return import_service.retry_indexing(user_id=user_id, import_id=import_id)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to retry indexing: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
