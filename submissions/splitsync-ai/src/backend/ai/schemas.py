"""AI Assistant request and response schemas."""

from typing import Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Payload for conversational financial query."""

    message: str = Field(..., min_length=1, max_length=2000, description="User question")
    group_id: Optional[str] = Field(None, description="Optional target group ID context")


class ChatResponse(BaseModel):
    """Response containing assistant answer and tool citations."""

    response: str
    group_id: Optional[str] = None
    tools_used: list[str] = []


class AssistantStatusResponse(BaseModel):
    """Status of AI assistant and configured providers."""

    provider: str
    model: str
    is_live_llm: bool
    tools_available: list[str]
