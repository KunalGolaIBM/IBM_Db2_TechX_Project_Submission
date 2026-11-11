"""GET /api/v1/health — liveness + dependency probes (never requires services).

GET /api/v1/ready — readiness gate for orchestrators: same probes, but
returns HTTP 503 when any check is not ``ok`` (see docs/API_CONTRACT.md).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from app.api.deps import build_health_service, get_started_at
from app.schemas.common import HealthResponse, ReadyResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def get_health(request: Request, started_at: float = Depends(get_started_at)) -> HealthResponse:
    """Probe every configured adapter and report overall status.

    Returns HTTP 200 with ``status: degraded`` when services are unreachable
    (actionable per-check details), because the application itself is healthy.
    """
    service = build_health_service(request)
    return service.health(started_at)


@router.get("/ready", response_model=ReadyResponse)
def get_ready(
    request: Request,
    response: Response,
    started_at: float = Depends(get_started_at),
) -> ReadyResponse:
    """Readiness gate: HTTP 200 when every probe is ok, HTTP 503 otherwise.

    Complements /health (which always answers 200 by design) so container
    orchestrators and CI pipelines get a fail-fast signal without changing
    the degraded-health contract.
    """
    service = build_health_service(request)
    payload, is_ready = service.ready(started_at)
    if not is_ready:
        response.status_code = 503
    return payload
