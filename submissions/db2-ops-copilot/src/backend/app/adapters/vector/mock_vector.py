"""Mock vector-store adapter — deterministic keyword-overlap retrieval.

Stands in for the real ``DB2VS`` (langchain-db2) vector store during offline
development and tests.

Score semantics MATCH the real adapter: ``score`` is a DISTANCE
(``1 - token_overlap_ratio``) — **lower is closer**, exactly like Db2's
VECTOR_DISTANCE returned by DB2VS. Results are sorted ascending.
"""

from __future__ import annotations

import re

from app.adapters.base import DocumentInput, ProbeResult, VectorHit
from app.core.config import Settings

_WORD_RE = re.compile(r"[a-z0-9]+")

_SEED_DOCUMENTS: list[DocumentInput] = [
    DocumentInput(
        text=(
            "DB2VS (langchain-db2) stores text embeddings in a Db2 VECTOR column "
            "and retrieves them with VECTOR_DISTANCE similarity search, so the "
            "vector store lives inside Db2 rather than a side-car database."
        ),
        metadata={
            "id": "seed-vector-db2vs",
            "source": "langchain-docs",
            "title": "Db2 vector store (DB2VS)",
            "topic": "rag",
        },
    ),
    DocumentInput(
        text=(
            "SYSCAT.TABLES and SYSCAT.COLUMNS are Db2 catalog views used to "
            "introspect table and column metadata for schema-aware SQL generation."
        ),
        metadata={
            "id": "seed-syscat-introspection",
            "source": "db2-docs",
            "title": "Catalog view introspection",
            "topic": "catalog",
        },
    ),
    DocumentInput(
        text=(
            "FETCH FIRST n ROWS ONLY caps the number of rows returned by a Db2 "
            "query and is the standard way to enforce result-set row limits."
        ),
        metadata={
            "id": "seed-fetch-first",
            "source": "db2-docs",
            "title": "Row limits with FETCH FIRST",
            "topic": "sql",
        },
    ),
    DocumentInput(
        text=(
            "The official db2-sqlglot-dialect plugin registers a 'db2' dialect "
            "for sqlglot so generated SQL can be parsed and validated as AST "
            "before any execution."
        ),
        metadata={
            "id": "seed-sqlglot-db2",
            "source": "ibm-github",
            "title": "IBM SQLGlot Db2 dialect",
            "topic": "validation",
        },
    ),
    DocumentInput(
        text=(
            "An audit table records every copilot request: timestamp, intent, "
            "question, generated SQL, status and latency for enterprise traceability."
        ),
        metadata={
            "id": "seed-audit-design",
            "source": "internal-design",
            "title": "Audit logging design",
            "topic": "audit",
        },
    ),
]


def _tokens(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


class MockVectorStoreAdapter:
    """In-memory vector store with deterministic scoring (distance-based)."""

    probe_name = "vector_store"
    provider_id = "mock"
    mode = "mock"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()
        self._documents: list[DocumentInput] = list(_SEED_DOCUMENTS)
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
            detail=f"mock vector store ready ({len(self._documents)} seeded documents)",
        )

    def similarity_search(
        self, query: str, k: int = 4, filters: dict | None = None
    ) -> list[VectorHit]:
        query_tokens = _tokens(query)
        hits: list[VectorHit] = []
        for doc in self._documents:
            if filters:
                if any(doc.metadata.get(key) != value for key, value in filters.items()):
                    continue
            doc_tokens = _tokens(doc.text)
            union = query_tokens | doc_tokens
            overlap = len(query_tokens & doc_tokens) / len(union) if union else 0.0
            # Distance semantics (lower = closer), matching VECTOR_DISTANCE.
            distance = round(1.0 - overlap, 4)
            hits.append(
                VectorHit(
                    content=doc.text, score=distance, metadata=dict(doc.metadata)
                )
            )
        hits.sort(key=lambda h: h.score)  # ascending: closest first
        return hits[: max(k, 0)]

    def upsert_documents(self, documents: list[DocumentInput]) -> int:
        """Insert documents; ones with a known metadata ``id`` replace prior
        rows for that id (mirrors DB2VS delete-then-add upsert semantics)."""
        added = 0
        for doc in documents:
            doc_id = doc.metadata.get("id")
            if doc_id is not None:
                self._documents = [
                    d for d in self._documents if d.metadata.get("id") != doc_id
                ]
            self._documents.append(doc)
            added += 1
        return added

    def delete(self, ids: list[str]) -> int:
        """Delete by metadata id (the mock's stand-in for hashed PKs)."""
        wanted = set(ids)
        before = len(self._documents)
        self._documents = [
            d for d in self._documents if d.metadata.get("id") not in wanted
        ]
        return before - len(self._documents)

    def count(self) -> int:
        return len(self._documents)

    def close(self) -> None:
        self._closed = True
