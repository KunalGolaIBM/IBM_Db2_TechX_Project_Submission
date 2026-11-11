from fastapi import APIRouter, Depends
from app.core.security import verify_internal_api_key
from app.schemas.stats import DashboardStatsResponse
from app.repositories.stats_repository import stats_repo

router = APIRouter(prefix="/stats", tags=["Dashboard Statistics"])

@router.get("", response_model=DashboardStatsResponse)
def get_dashboard_stats(
    _auth: bool = Depends(verify_internal_api_key),
):
    """
    GET /api/v1/stats
    Returns SQL aggregated metrics computed over CLOUDLOOP.V_ACTIVE_OPPORTUNITIES:
    - Counts per kind
    - Opportunities closing within 7 days
    - Total active opportunities
    """
    stats = stats_repo.get_dashboard_stats()
    return DashboardStatsResponse(
        counts_per_kind=stats["counts_per_kind"],
        closing_within_7_days=stats["closing_within_7_days"],
        total_active=stats["total_active"],
    )
