"""Status service — dashboard-facing view of database, models and vector store."""

from __future__ import annotations

from datetime import datetime, timezone

from app.adapters.base import ProbeResult
from app.adapters.registry import AdapterRegistry
from app.core.config import Settings
from app.schemas.status import (
    DatabaseStatus,
    ModelStatus,
    StatusResponse,
    VectorStoreStatus,
)


class StatusService:
    def __init__(self, settings: Settings, registry: AdapterRegistry) -> None:
        self._settings = settings
        self._registry = registry

    def status(self) -> StatusResponse:
        # One parallel probe pass (registry.probes probes concurrently);
        # results are mapped by probe name.
        probe_map = {p.name: p for p in self._registry.probes()}
        fallback = ProbeResult(
            name="unknown",
            status="unavailable",
            mode=self._registry.mode,
            latency_ms=0.0,
            detail="probe missing",
        )
        db_probe = probe_map.get("database", fallback)
        vector_probe = probe_map.get("vector_store", fallback)
        llm_probe = probe_map.get("llm", fallback)
        embed_probe = probe_map.get("embeddings", fallback)

        try:
            doc_count = self._registry.vector_store.count()
        except Exception:  # noqa: BLE001 — count is informational only
            doc_count = -1

        return StatusResponse(
            timestamp=datetime.now(timezone.utc).isoformat(),
            adapter_mode=self._settings.adapter_mode,
            database=DatabaseStatus(
                provider=self._registry.database.provider_id,
                connected=db_probe.status == "ok",
                host=self._settings.db2_host,
                port=self._settings.db2_port,
                database=self._settings.db2_dbname,
                detail=db_probe.detail,
            ),
            vector_store=VectorStoreStatus(
                provider=self._registry.vector_store.provider_id,
                document_count=doc_count,
                detail=vector_probe.detail,
            ),
            llm=ModelStatus(
                provider=self._registry.chat_model.provider_id,
                model=self._settings.ollama_llm_model,
                available=llm_probe.status == "ok",
                detail=llm_probe.detail,
            ),
            embeddings=ModelStatus(
                provider=self._registry.embeddings.provider_id,
                model=self._settings.ollama_embed_model,
                available=embed_probe.status == "ok",
                detail=embed_probe.detail,
                dimensions=self._settings.embedding_dimensions,
            ),
        )
