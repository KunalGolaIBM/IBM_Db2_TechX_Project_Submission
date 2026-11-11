"""GET /api/v1/status — dashboard view: database, models, vector store."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.deps import build_status_service
from app.schemas.status import StatusResponse

router = APIRouter(tags=["status"])


@router.get("/status", response_model=StatusResponse)
def get_status(request: Request) -> StatusResponse:
    return build_status_service(request).status()
