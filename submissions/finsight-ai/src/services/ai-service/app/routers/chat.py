from fastapi import APIRouter, Depends, Header, HTTPException
from app.models.schemas import ChatRequest, ChatResponse
from app.services.assistant import assistant_service
from app.config import settings

router = APIRouter(prefix="/api/ai", tags=["Assistant"])

@router.post("/chat", response_model=ChatResponse)
def chat_with_assistant(
    request: ChatRequest,
    x_service_token: str = Header(default="dev_internal_secret_token")
):
    # Enforce internal service authentication
    if settings.ai_service_internal_token and x_service_token != settings.ai_service_internal_token:
        raise HTTPException(status_code=401, detail="Invalid service authorization token.")

    user_id = request.user_id or settings.demo_user_id
    response = assistant_service.process_query(request.message, user_id=user_id, mode=request.mode)
    return response

@router.get("/status")
def get_ai_status(
    x_service_token: str = Header(...)
):
    if settings.ai_service_internal_token and x_service_token != settings.ai_service_internal_token:
        raise HTTPException(status_code=401, detail="Invalid service authorization token.")

    return {
        "status": "ONLINE",
        "mode_active": "LLM" if settings.gemini_api_key else "DETERMINISTIC",
        "engine_name": "Mode A: Deterministic Db2 SQL Engine" if not settings.gemini_api_key else f"Mode B: LangChain + {settings.llm_model}",
        "llm_configured": bool(settings.gemini_api_key),
        "llm_model": settings.llm_model if settings.gemini_api_key else "none (awaiting GEMINI_API_KEY)",
        "vector_engine": "IBM Db2 12.1 Native Vector (BAAI/bge-small-en-v1.5 384-dim)",
        "grounding": "IBM Db2 12.1.5.0 (FINDB)",
        "capabilities": [
            "Category-level spending & monthly aggregations",
            "Highest/lowest expense identification",
            "Multi-month income vs. outflow comparison",
            "Top merchant expenditure rankings",
            "Recurring subscriptions and utility monitoring",
            "Pending vs. posted transaction differentiation",
            "Mathematical statistical outlier & anomaly explanation",
            "Semantic cosine distance vector search (384-dim)"
        ]
    }
