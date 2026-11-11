"""Mock orchestration adapter — deterministic offline pipeline.

Replicates the *shape* of the real LangChain pipeline (intent routing →
retrieval → grounded answer / validated SQL) with canned, honest mock output.
Every reply is clearly marked as mock so no offline result can be mistaken for
a real LLM/Db2 integration result.
"""

from __future__ import annotations

import time

from app.adapters.base import (
    CitationDraft,
    OrchestratorResult,
    ProbeResult,
)
from app.adapters.sql_validator.sqlglot_validator import SqlGlotValidator
from app.core.config import Settings

_DATA_HINTS = (
    "how many",
    "list ",
    "show ",
    "count",
    "average",
    "top ",
    "which server",
    "incident",
    "select ",
    "uptime",
    "severity",
    "rows in",
    "total ",
)

_DOCS_HINTS = (
    "what is",
    "what's",
    "explain",
    "how does",
    "difference",
    "meaning",
    "why ",
    "tell me about",
    "rag",
    "vector",
    "embedding",
    "sqlglot",
    "guardrail",
    "catalog",
    "audit table",
)

_SAFE_SQL = (
    "SELECT SERVER_ID, HOSTNAME, ENVIRONMENT, UPTIME_PCT "
    "FROM DEMO_SERVERS ORDER BY UPTIME_PCT DESC FETCH FIRST 10 ROWS ONLY"
)

_CITATIONS = [
    CitationDraft(
        source="langchain-docs",
        title="Db2 vector store (DB2VS)",
        snippet=(
            "DB2VS stores embeddings in a Db2 VECTOR column and retrieves them "
            "with VECTOR_DISTANCE similarity search."
        ),
        score=0.82,
    ),
    CitationDraft(
        source="db2-docs",
        title="Row limits with FETCH FIRST",
        snippet="FETCH FIRST n ROWS ONLY caps the number of returned rows.",
        score=0.64,
    ),
]


class MockOrchestrator:
    """Deterministic stand-in for the LangChain RAG / text-to-SQL pipeline."""

    probe_name = "orchestrator"
    provider_id = "mock"
    mode = "mock"

    def __init__(
        self,
        settings: Settings | None = None,
        validator: SqlGlotValidator | None = None,
    ) -> None:
        self._settings = settings or Settings()
        self._validator = validator or SqlGlotValidator()
        self._closed = False

    def ping(self) -> ProbeResult:
        if self._closed:
            return ProbeResult(
                name=self.probe_name,
                status="unavailable",
                mode=self.mode,
                latency_ms=0.0,
                detail="mock adapter closed",
            )
        return ProbeResult(
            name=self.probe_name,
            status="ok",
            mode=self.mode,
            latency_ms=0.0,
            detail="mock orchestrator ready (deterministic canned pipeline)",
        )

    def respond(self, message: str, mode: str = "auto") -> OrchestratorResult:
        text = " ".join(message.split())
        lower = text.lower()
        start = time.perf_counter()

        if mode == "rag":
            intent = "docs"
        elif mode == "sql":
            intent = "data"
        elif any(hint in lower for hint in _DATA_HINTS):
            intent = "data"
        elif any(hint in lower for hint in _DOCS_HINTS):
            intent = "docs"
        else:
            intent = "general"

        if intent == "data":
            # The SQL we emit always passes the real validation gate; if a
            # future edit breaks that, drop it instead of shipping invalid SQL.
            validation = self._validator.validate(_SAFE_SQL)
            sql = _SAFE_SQL if validation.valid else None
            reply = (
                "MOCK MODE — simulated answer: the demo fleet has 4 servers "
                "(2 prod, 1 staging, 1 dev) with uptime between 92.10% and "
                "99.95%. The query below was checked by the SQL validation "
                "gate before being shown."
            )
            citations: list[CitationDraft] = []
            retrieval_ms = 0
        elif intent == "docs":
            sql = None
            reply = (
                "MOCK MODE — simulated answer: DB2VS (langchain-db2) keeps "
                "vector embeddings inside a Db2 VECTOR column so the vector "
                "store and the operational database are the same system. "
                "Citations below come from the mocked knowledge base."
            )
            citations = list(_CITATIONS)
            retrieval_ms = 3
        else:
            sql = None
            reply = (
                "MOCK MODE — simulated answer: I'm the Db2 Ops Copilot. Ask me "
                "about Db2 documentation (RAG path) or about your data "
                "(guardrailed text-to-SQL path). No real model was called."
            )
            citations = []
            retrieval_ms = 0

        elapsed = int((time.perf_counter() - start) * 1000)
        return OrchestratorResult(
            reply=reply,
            intent=intent,
            citations=citations,
            sql=sql,
            retrieval_ms=retrieval_ms,
            generation_ms=max(elapsed, 1),
        )

    def close(self) -> None:
        self._closed = True
