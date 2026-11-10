from fastapi import APIRouter, Header, HTTPException
from app.models.schemas import SearchRequest, SearchResponse, SearchResultItem, IndexRequest, IndexResponse
from app.services.vector_store import vector_store_service
from app.config import settings

router = APIRouter(prefix="/api/ai", tags=["Semantic Search"])

@router.post("/search", response_model=SearchResponse)
def semantic_search(
    request: SearchRequest,
    x_service_token: str = Header(default="dev_internal_secret_token")
):
    if settings.ai_service_internal_token and x_service_token != settings.ai_service_internal_token:
        raise HTTPException(status_code=401, detail="Invalid service authorization token.")

    user_id = request.user_id or settings.demo_user_id
    results = vector_store_service.similarity_search(request.query, user_id=user_id, limit=request.limit)

    items = [SearchResultItem(**r) for r in results]
    return SearchResponse(
        query=request.query,
        total_results=len(items),
        results=items,
        embedding_model=settings.embedding_model
    )

@router.post("/index-transactions", response_model=IndexResponse)
def index_transactions(
    request: IndexRequest,
    x_service_token: str = Header(default="dev_internal_secret_token")
):
    if settings.ai_service_internal_token and x_service_token != settings.ai_service_internal_token:
        raise HTTPException(status_code=401, detail="Invalid service authorization token.")

    user_id = request.user_id or settings.demo_user_id
    res = vector_store_service.index_user_transactions(user_id=user_id)

    return IndexResponse(
        status="SUCCESS",
        indexed_count=res["indexed_count"],
        dimension=res["dimension"],
        table="FINSIGHT.TRANSACTION_EMBEDDINGS"
    )
