"""Adapter registry — selects mock vs. real implementations from settings.

``ADAPTER_MODE=mock`` (default) builds every service adapter from the ``mock_*``
implementations: fully offline, deterministic, safe for development and CI.

``ADAPTER_MODE=real`` builds the real adapters (Db2, Ollama, LangChain).
Real adapters construct without side effects: they do not connect at startup;
their ``ping()`` reports true availability so ``/api/v1/health`` stays honest.

The SQL validator is always the real local sqlglot gate (no service needed).
"""

from __future__ import annotations

import logging

from app.adapters.audit.db2_audit import Db2AuditAdapter
from app.adapters.audit.mock_audit import MockAuditAdapter
from app.adapters.base import ProbeResult
from app.adapters.db.db2_db import Db2DatabaseAdapter
from app.adapters.db.mock_db import MockDatabaseAdapter
from app.adapters.embeddings.mock_embeddings import MockEmbeddingModelAdapter
from app.adapters.embeddings.ollama_embeddings import OllamaEmbeddingsAdapter
from app.adapters.llm.mock_llm import MockChatModelAdapter
from app.adapters.llm.ollama_chat import OllamaChatAdapter
from app.adapters.orchestration.mock_orchestrator import MockOrchestrator
from app.adapters.orchestration.langchain_orchestrator import LangChainOrchestrator
from app.adapters.sql_validator import build_validator
from app.adapters.vector.db2_vector import Db2VectorStoreAdapter
from app.adapters.vector.mock_vector import MockVectorStoreAdapter
from app.core.config import Settings

logger = logging.getLogger(__name__)


class AdapterRegistry:
    """Holds the active adapter instances for the application lifetime."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.mode = settings.adapter_mode
        self.validator = build_validator(settings)

        if settings.is_mock:
            self.database = MockDatabaseAdapter(settings)
            self.vector_store = MockVectorStoreAdapter(settings)
            self.chat_model = MockChatModelAdapter(settings)
            self.embeddings = MockEmbeddingModelAdapter(settings)
            self.audit = MockAuditAdapter(settings)
            self.orchestrator = MockOrchestrator(settings, validator=self.validator)
        else:
            self.database = Db2DatabaseAdapter(settings)
            self.embeddings = OllamaEmbeddingsAdapter(settings)
            self.vector_store = Db2VectorStoreAdapter(
                settings, embeddings=self.embeddings
            )
            self.chat_model = OllamaChatAdapter(settings)
            self.audit = Db2AuditAdapter(settings)
            self.orchestrator = LangChainOrchestrator(
                settings,
                chat_model=self.chat_model,
                embeddings=self.embeddings,
                vector_store=self.vector_store,
                validator=self.validator,
            )

        self._adapters = (
            self.database,
            self.vector_store,
            self.chat_model,
            self.embeddings,
            self.orchestrator,
            self.audit,
        )
        logger.info(
            "Adapter registry built: mode=%s, adapters=%s",
            self.mode,
            ", ".join(a.provider_id for a in self._adapters),
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> "AdapterRegistry":
        return cls(settings)

    # -- health -----------------------------------------------------------
    @staticmethod
    def _safe_probe(adapter) -> ProbeResult:
        """A crashing probe never breaks health output."""
        name = getattr(adapter, "probe_name", "adapter")
        mode = getattr(adapter, "mode", "mock")
        try:
            return adapter.ping()
        except Exception as exc:  # noqa: BLE001 — health must be total
            logger.exception("probe failed for %s", name)
            return ProbeResult(
                name=name,
                status="unavailable",
                mode=mode,
                latency_ms=0.0,
                detail=f"probe raised {type(exc).__name__}: {exc}",
            )

    def probes(self) -> list[ProbeResult]:
        """Probe every adapter concurrently (order-preserving).

        Probes run in parallel because a refused loopback connection on this
        host takes ~2 s at the OS level; sequential probing would multiply that
        by the number of adapters.
        """
        from concurrent.futures import ThreadPoolExecutor

        workers = min(len(self._adapters), 6)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(self._safe_probe, self._adapters))
        return results

    # -- lifecycle ----------------------------------------------------------
    def close_all(self) -> None:
        for adapter in self._adapters:
            try:
                adapter.close()
            except Exception:  # noqa: BLE001 — shutdown must not raise
                logger.exception("close failed for %s", type(adapter).__name__)
