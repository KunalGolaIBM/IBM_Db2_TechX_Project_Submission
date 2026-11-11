from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.opportunities import router as opportunities_router
from app.api.v1.search import router as search_router
from app.api.v1.match import router as match_router
from app.api.v1.recommendations import router as recommendations_router
from app.api.v1.tracking import router as tracking_router
from app.api.v1.newsletter import router as newsletter_router
from app.api.v1.stats import router as stats_router
from app.api.v1.ingestion import router as ingestion_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(health_router)
api_v1_router.include_router(opportunities_router)
api_v1_router.include_router(search_router)
api_v1_router.include_router(match_router)
api_v1_router.include_router(recommendations_router)
api_v1_router.include_router(tracking_router)
api_v1_router.include_router(newsletter_router)
api_v1_router.include_router(stats_router)
api_v1_router.include_router(ingestion_router)
