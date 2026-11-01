from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.agent.coordinator import IncidentCoordinator
from app.ai.knowledge_retriever import KnowledgeDocument, knowledge_retriever
from app.db.connection import db_manager
from app.db.repository import Db2IncidentRepository
from app.models.incident import (
    HealthResponse,
    Incident,
    IncidentCreateRequest,
    IncidentListResponse,
    IncidentResponse,
    IncidentSeverity,
    IncidentStatus,
    IncidentUpdateRequest,
)

logger = logging.getLogger("api")


def create_app(
    repository: Db2IncidentRepository | None = None,
    coordinator: IncidentCoordinator | None = None,
) -> FastAPI:
    repo = repository or Db2IncidentRepository(db_manager)
    coord = coordinator or IncidentCoordinator(repo)

    # Initialize schema on startup
    repo.init_schema()

    app = FastAPI(
        title="Db2 WorkRelay Intelligence API",
        version="1.0.0",
        description="Enterprise AI-powered incident management and knowledge retrieval backed by IBM Db2.",
    )

    router = APIRouter()

    # Exception handler for structured API error handling
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "status_code": exc.status_code,
                "message": exc.detail,
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc: Exception):
        logger.error("Unhandled server exception: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": True,
                "status_code": 500,
                "message": "Internal Server Error",
                "details": str(exc),
            },
        )

    # 1. Health check endpoint
    @router.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        db_health = repo.mgr.check_health()
        ai_health = knowledge_retriever.get_status()
        return HealthResponse(
            status="healthy" if db_health.get("connected") else "degraded",
            service="db2-workrelay-intelligence",
            version="1.0.0",
            db2_connected=bool(db_health.get("connected")),
            db2_mode=repo.mgr.active_mode,
            ai_status=ai_health,
        )

    # 2. Incident registration
    @router.post("/incidents", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
    def create_incident(req: IncidentCreateRequest) -> IncidentResponse:
        incident = Incident(
            title=req.title,
            description=req.description,
            service=req.service,
            severity=req.severity or IncidentSeverity.MEDIUM,
            metadata=req.metadata,
        )
        if req.severity is None:
            incident.metadata["auto_classify"] = True

        result = coord.handle(incident)
        return IncidentResponse(incident=result)

    # 3. Incident retrieval (list with query parameters)
    @router.get("/incidents", response_model=IncidentListResponse)
    def list_incidents(
        status: str | None = Query(None, description="Filter by status (e.g. OPEN, RESOLVED)"),
        severity: str | None = Query(None, description="Filter by severity (LOW, MEDIUM, HIGH, CRITICAL)"),
        service: str | None = Query(None, description="Filter by service name"),
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ) -> IncidentListResponse:
        status_val = status if isinstance(status, str) else None
        severity_val = severity if isinstance(severity, str) else None
        service_val = service if isinstance(service, str) else None
        limit_val = limit if isinstance(limit, int) else 50
        offset_val = offset if isinstance(offset, int) else 0

        items, total = repo.list(status=status_val, severity=severity_val, service=service_val, limit=limit_val, offset=offset_val)
        return IncidentListResponse(items=items, total=total, limit=limit_val, offset=offset_val)

    # 4. Incident retrieval by ID
    @router.get("/incidents/{incident_id}", response_model=IncidentResponse)
    def get_incident(incident_id: str) -> IncidentResponse:
        incident = repo.get(incident_id)
        if incident is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident '{incident_id}' not found.",
            )
        return IncidentResponse(incident=incident)

    # 5. Incident status / severity / resolution updates
    @router.patch("/incidents/{incident_id}", response_model=IncidentResponse)
    def update_incident(incident_id: str, req: IncidentUpdateRequest) -> IncidentResponse:
        updated = repo.patch(
            incident_id=incident_id,
            title=req.title,
            description=req.description,
            severity=req.severity,
            status=req.status,
            resolution=req.resolution,
            escalation_reason=req.escalation_reason,
            metadata=req.metadata,
        )
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident '{incident_id}' not found for update.",
            )
        return IncidentResponse(incident=updated)

    # 6. Knowledge retrieval query endpoint
    @router.post("/knowledge/query")
    def query_knowledge(payload: dict[str, Any]) -> dict[str, Any]:
        query_text = payload.get("query", "").strip()
        if not query_text:
            raise HTTPException(status_code=400, detail="Query text is required.")
        service = payload.get("service")
        top_k = int(payload.get("top_k", 2))
        return knowledge_retriever.query(query_text, service=service, top_k=top_k)

    # 7. Ingest new runbook into knowledge base
    @router.post("/knowledge/ingest", status_code=status.HTTP_201_CREATED)
    def ingest_knowledge(payload: dict[str, Any]) -> dict[str, str]:
        doc_id = payload.get("doc_id")
        title = payload.get("title")
        content = payload.get("content")
        resolution = payload.get("resolution_steps")
        if not all([doc_id, title, content, resolution]):
            raise HTTPException(status_code=400, detail="Fields doc_id, title, content, resolution_steps required.")

        doc = KnowledgeDocument(
            doc_id=doc_id,
            title=title,
            category=payload.get("category", "general"),
            service=payload.get("service", "general"),
            content=content,
            resolution_steps=resolution,
            metadata=payload.get("metadata", {}),
        )
        knowledge_retriever.ingest_document(doc)
        return {"status": "ingested", "doc_id": doc_id}

    app.include_router(router)
    return app

app = create_app()
