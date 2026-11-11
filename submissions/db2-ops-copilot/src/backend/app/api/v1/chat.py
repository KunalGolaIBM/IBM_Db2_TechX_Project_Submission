"""POST /api/v1/chat — chat workspace entry point."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request

from app.api.deps import build_chat_service
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def post_chat(request: ChatRequest, http_request: Request) -> ChatResponse:
    """Run the copilot flow (mock pipeline in mock mode, LangChain in real mode)."""
    request_id = getattr(http_request.state, "request_id", uuid.uuid4().hex[:16])
    service = build_chat_service(http_request)
    return service.ask(request, request_id)
