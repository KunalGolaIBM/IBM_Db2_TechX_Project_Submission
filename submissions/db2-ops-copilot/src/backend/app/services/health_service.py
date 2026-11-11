"""Business services — thin orchestration over adapters (adapter-agnostic)."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from app.adapters.registry import AdapterRegistry
from app.core.config import Settings
from app.schemas.common import HealthResponse, Probe, ReadyResponse

logger = logging.getLogger(__name__)


class HealthService:
    """Aggregates adapter probes into the /api/v1/health payload."""

    def __init__(self, settings: Settings, registry: AdapterRegistry) -> None:
        self._settings = settings
        self._registry = registry

    def _checks(self) -> list[Probe]:
        return [
            Probe(
                name=p.name,
                status=p.status,
                mode=p.mode,
                latency_ms=round(p.latency_ms, 2),
                detail=p.detail,
            )
            for p in self._registry.probes()
        ]

    def health(self, started_at: float) -> HealthResponse:
        checks = self._checks()
        overall = "ok" if all(c.status == "ok" for c in checks) else "degraded"
        return HealthResponse(
            status=overall,
            version=self._settings.app_version,
            api_version="v1",
            mode=self._settings.adapter_mode,
            uptime_seconds=round(max(time.time() - started_at, 0.0), 3),
            timestamp=datetime.now(timezone.utc).isoformat(),
            checks=checks,
        )

    def ready(self, started_at: float) -> tuple[ReadyResponse, bool]:
        """Readiness for orchestrators — unlike /health, this one can 503.

        Returns the payload plus ``is_ready``; the endpoint maps
        ``is_ready=False`` to HTTP 503 so container orchestrators/CI gates
        can wait for full readiness while /health stays a liveness signal.
        """
        checks = self._checks()
        is_ready = bool(checks) and all(c.status == "ok" for c in checks)
        return (
            ReadyResponse(
                status="ready" if is_ready else "not_ready",
                version=self._settings.app_version,
                api_version="v1",
                mode=self._settings.adapter_mode,
                uptime_seconds=round(max(time.time() - started_at, 0.0), 3),
                timestamp=datetime.now(timezone.utc).isoformat(),
                checks=checks,
            ),
            is_ready,
        )
