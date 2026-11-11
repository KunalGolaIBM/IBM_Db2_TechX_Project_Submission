"""GET /api/v1/audit — recent audit entries (Db2 APP_AUDIT in real mode)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import get_registry
from app.adapters.registry import AdapterRegistry
from app.schemas.audit import AuditEntryModel, AuditResponse

router = APIRouter(tags=["audit"])


@router.get("/audit", response_model=AuditResponse)
def get_audit(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    registry: AdapterRegistry = Depends(get_registry),
) -> AuditResponse:
    entries = registry.audit.list_recent(limit=limit)
    return AuditResponse(
        entries=[
            AuditEntryModel(
                id=e.id,
                timestamp=e.timestamp,
                operation=e.operation or "chat",
                intent=e.intent,
                question=e.question,
                status=e.status,
                latency_ms=e.latency_ms,
                detail=e.detail,
                request_id=e.request_id,
            )
            for e in entries
        ],
        total=len(entries),
        mock=registry.mode == "mock",
    )
