"""AI Assistant API routes."""

from fastapi import APIRouter, Depends

from auth.dependencies import get_current_user
from db.repositories.member_repo import member_repo
from ai.schemas import ChatRequest, ChatResponse, AssistantStatusResponse
from ai.assistant import ai_assistant
from api.middleware import AppError

router = APIRouter(prefix="/ai", tags=["AI Engine"])


@router.post("/chat", response_model=ChatResponse)
@router.post("/query", response_model=ChatResponse)
def chat_with_assistant(
    body: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    """Ask financial queries about group expenses, balances, and settlements."""
    if body.group_id:
        member = member_repo.get_member_by_group_and_user(
            body.group_id, current_user["user_id"]
        )
        if not member:
            raise AppError(403, "Access denied. You are not a member of this group.")

    result = ai_assistant.ask(message=body.message, group_id=body.group_id)
    return result


@router.get("/status", response_model=AssistantStatusResponse)
def get_ai_status(
    current_user: dict = Depends(get_current_user),
):
    """Get the current configuration and readiness status of the AI assistant."""
    return ai_assistant.get_status()
