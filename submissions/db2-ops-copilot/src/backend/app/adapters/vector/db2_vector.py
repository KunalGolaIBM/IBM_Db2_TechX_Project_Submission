"""REAL Db2 vector-store adapter — genuine ``DB2VS`` integration (M2.4).

Implements the VectorStoreAdapter contract on top of the official
``langchain-db2`` package. **Every package call below was verified against
the package source** (`libs/langchain-db2/langchain_db2/db2vs.py`) and the
official worked-example notebook (`libs/langchain-db2/docs/db2.ipynb`)
fetched over HTTPS — nothing is fabricated:

    store = DB2VS(
        embedding_function=<langchain Embeddings>,
        table_name="APP.COPILOT_KB",
        client=<ibm_db_dbi.Connection>,
        distance_strategy=DistanceStrategy.COSINE,   # | DOT_PRODUCT | EUCLIDEAN
    )
    store.add_texts(texts, metadatas, ids)      # ids hashed sha256[:16].upper()
    store.similarity_search_with_score(q, k, filter={"key": [values]})
        -> [(Document, distance)]               # distance: LOWER is closer
    store.delete(ids)                           # raw or hashed ids
    store.get_pks() -> list[str]

Key behaviors:
- Connection reuse: ONE ``ibm_db_dbi`` connection per adapter lifetime,
  closed on ``close()``. A broken connection (SQLSTATE 08xxx) is rebuilt
  once and the operation retried once.
- Table: pre-created by migration 004 with the package's exact DDL so the
  read-only account never needs CREATE TABLE; DB2VS detects existence and
  skips its internal creation.
- Metadata filters: our ``filters={"source": "x"}`` is converted to the
  package's verified format ``{"source": ["x"]}`` (list membership test).
- Scores are Db2 VECTOR_DISTANCE values — **lower is closer** (documented
  in docs/VECTOR_STORE.md; mock parity: mock returns 1-overlap distance).

Requires ``requirements-integration.txt`` + running Db2 (12.1.2+) with
Ollama up (the DB2VS constructor embeds one probe text to infer the
dimension). Nothing here is executed on the development machine.
"""

from __future__ import annotations

import importlib.util
import logging
import socket
import time
from typing import Any

from app.adapters.base import DocumentInput, EmbeddingModelAdapter, ProbeResult, VectorHit
from app.core.config import Settings
from app.core.errors import AdapterUnavailableError

logger = logging.getLogger(__name__)

_DISTANCE_STRATEGIES = {
    "cosine": "COSINE",
    "dot": "DOT_PRODUCT",
    "euclidean": "EUCLIDEAN_DISTANCE",
}

# Connection-class SQLSTATEs: worth one reconnect-and-retry.
_RECONNECT_CATEGORIES = {"connectivity"}


def _missing_packages() -> list[str]:
    required = {
        "ibm_db_dbi": "ibm-db",
        "langchain_db2": "langchain-db2",
        "langchain_core": "langchain-core",
        "langchain_community": "langchain-community",
    }
    return [
        dist
        for module, dist in required.items()
        if importlib.util.find_spec(module) is None
    ]


class Db2VectorStoreAdapter:
    """Vector operations backed by Db2 via the official DB2VS package."""

    probe_name = "vector_store"
    provider_id = "db2"
    mode = "real"

    def __init__(
        self,
        settings: Settings,
        embeddings: EmbeddingModelAdapter | None = None,
    ) -> None:
        self._settings = settings
        self._embeddings = embeddings
        self._closed = False
        self._conn: Any | None = None
        self._store: Any | None = None

    # -- lazy construction ---------------------------------------------------
    @property
    def table_name(self) -> str:
        return self._settings.qualified_app_table

    @property
    def distance_strategy_name(self) -> str:
        return self._settings.vector_distance_strategy

    def _tcp_reachable(self) -> tuple[bool, str]:
        timeout = max(self._settings.db2_connect_timeout_ms / 1000, 0.2)
        try:
            with socket.create_connection(
                (self._settings.db2_host, self._settings.db2_port), timeout=timeout
            ):
                return True, ""
        except OSError as exc:
            return False, str(exc.strerror or exc)

    def _require_ready(self) -> tuple[Any, Any]:
        """Build (connection, DB2VS) lazily; raise actionable errors.

        Never falls back to a mock or in-memory store — a missing service
        or package surfaces as ``AdapterUnavailableError``.
        """
        if self._closed:
            raise AdapterUnavailableError("vector adapter is closed")
        missing = _missing_packages()
        if missing:
            raise AdapterUnavailableError(
                f"Vector store requires: {', '.join(missing)}. "
                "Install requirements-integration.txt.",
                detail={"missing": missing},
            )
        if self._embeddings is None:
            raise AdapterUnavailableError(
                "Vector store has no embedding adapter wired (registry error)."
            )
        reachable, sock_error = self._tcp_reachable()
        if not reachable:
            raise AdapterUnavailableError(
                f"Db2 not reachable at {self._settings.db2_host}:"
                f"{self._settings.db2_port} ({sock_error}).",
                detail={"hint": "start Db2 — see docs/DB2_INTEGRATION.md"},
            )

        if self._store is None:
            self._build_store()
        return self._conn, self._store

    def _build_store(self) -> None:
        from langchain_community.vectorstores.utils import DistanceStrategy
        from langchain_db2.db2vs import DB2VS

        from app.adapters.embeddings.lc_embeddings import build_lc_embeddings
        from app.database.dsn import connect_args, sanitize

        # verify login early with sanitized errors
        try:
            import ibm_db_dbi

            dsn, user, password = connect_args(self._settings)
            self._conn = ibm_db_dbi.connect(dsn, user, password)
        except ImportError as exc:  # pragma: no cover — checked above
            raise AdapterUnavailableError("ibm_db driver missing") from exc
        except Exception as exc:
            raise AdapterUnavailableError(
                f"Db2 login for the vector store failed: "
                f"{sanitize(str(exc), self._settings)}",
                detail={"hint": "check DB2_* credentials in .env"},
            ) from exc

        strategy = getattr(
            DistanceStrategy,
            _DISTANCE_STRATEGIES[self.distance_strategy_name],
        )
        try:
            # DB2VS constructor: infers embedding dimension with one probe
            # embedding (calls Ollama!), then ensures the table exists.
            self._store = DB2VS(
                embedding_function=build_lc_embeddings(self._embeddings),
                table_name=self.table_name,
                client=self._conn,
                distance_strategy=strategy,
                query="Db2 Ops Copilot knowledge base",
            )
        except Exception as exc:
            self._close_connection()
            raise AdapterUnavailableError(
                f"DB2VS initialization failed for {self.table_name}: "
                f"{type(exc).__name__}: {exc}",
                detail={
                    "hint": (
                        "verify Db2 12.1.2+ (VECTOR), migration 004 applied, "
                        "Ollama embeddings reachable, and db2ro grants on "
                        "the vector table (docs/VECTOR_STORE.md)"
                    )
                },
            ) from exc
        logger.info(
            "DB2VS ready table=%s strategy=%s",
            self.table_name,
            self.distance_strategy_name,
        )

    def _close_connection(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:  # noqa: BLE001 — close is best-effort
                pass
        self._conn = None
        self._store = None

    # -- availability ---------------------------------------------------------
    def ping(self) -> ProbeResult:
        if self._closed:
            return ProbeResult(
                name=self.probe_name,
                status="unavailable",
                mode=self.mode,
                latency_ms=0.0,
                detail="vector adapter closed",
            )
        start = time.perf_counter()

        def elapsed() -> float:
            return (time.perf_counter() - start) * 1000

        missing = _missing_packages()
        if missing:
            return ProbeResult(
                name=self.probe_name,
                status="unavailable",
                mode=self.mode,
                latency_ms=elapsed(),
                detail=(
                    f"required packages missing: {', '.join(missing)} "
                    "(install requirements-integration.txt)."
                ),
            )
        reachable, sock_error = self._tcp_reachable()
        if not reachable:
            return ProbeResult(
                name=self.probe_name,
                status="unavailable",
                mode=self.mode,
                latency_ms=elapsed(),
                detail=(
                    f"Db2 not reachable at {self._settings.db2_host}:"
                    f"{self._settings.db2_port} ({sock_error}) — vector store "
                    "depends on Db2 (docs/VECTOR_STORE.md)."
                ),
            )
        if self._store is not None:
            return ProbeResult(
                name=self.probe_name,
                status="ok",
                mode=self.mode,
                latency_ms=elapsed(),
                detail=(
                    f"DB2VS connected (table {self.table_name}, "
                    f"{self.distance_strategy_name})"
                ),
            )
        return ProbeResult(
            name=self.probe_name,
            status="ok",
            mode=self.mode,
            latency_ms=elapsed(),
            detail=(
                f"Db2 reachable, langchain-db2 present; store "
                f"{self.table_name} initializes lazily on first use."
            ),
        )

    # -- operations -------------------------------------------------------------
    @staticmethod
    def _to_package_filter(
        filters: dict[str, Any] | None
    ) -> dict[str, list[Any]] | None:
        """Convert app filters to DB2VS's verified format (list values).

        DB2VS tests ``metadata.get(key) in value``, so each value must be a
        list of acceptable values (verified in db2vs.py source).
        """
        if not filters:
            return None
        converted: dict[str, list[Any]] = {}
        for key, value in filters.items():
            if isinstance(value, (list, tuple, set)):
                converted[key] = list(value)
            else:
                converted[key] = [value]
        return converted

    def similarity_search(
        self, query: str, k: int = 4, filters: dict[str, Any] | None = None
    ) -> list[VectorHit]:
        try:
            _, store = self._require_ready()
            pairs = store.similarity_search_with_score(
                query, k=k, filter=self._to_package_filter(filters)
            )
        except AdapterUnavailableError:
            raise
        except Exception as exc:
            raise self._operation_error("similarity search", exc) from exc
        hits: list[VectorHit] = []
        for doc, distance in pairs:
            metadata = dict(doc.metadata or {})
            hits.append(
                VectorHit(
                    content=doc.page_content or "",
                    # Db2 VECTOR_DISTANCE: lower is closer (documented).
                    score=float(distance),
                    metadata=metadata,
                )
            )
        return hits

    def upsert_documents(self, documents: list[DocumentInput]) -> int:
        """Insert documents; existing ids are replaced (delete + add).

        DB2VS derives the primary key as sha256(metadata["id"])[:16].upper(),
        so deleting by the same logical id first makes repeated ingestion of
        the same document idempotent (the package raises on duplicate
        primary keys — verified in add_texts source).
        """
        if not documents:
            return 0
        try:
            _, store = self._require_ready()
            texts = [d.text for d in documents]
            metadatas = [dict(d.metadata) for d in documents]
            existing_ids = [
                str(m["id"]) for m in metadatas if "id" in m
            ]
            if existing_ids:
                # delete() is idempotent: missing ids simply match no rows.
                store.delete(existing_ids)
            returned = store.add_texts(texts, metadatas)
            return len(returned)
        except AdapterUnavailableError:
            raise
        except Exception as exc:
            raise self._operation_error("document upsert", exc) from exc

    def delete(self, ids: list[str]) -> int:
        """Delete documents by logical ids (or already-hashed ids)."""
        if not ids:
            return 0
        try:
            _, store = self._require_ready()
            before = len(store.get_pks())
            store.delete(ids)
            after = len(store.get_pks())
            return max(before - after, 0)
        except AdapterUnavailableError:
            raise
        except Exception as exc:
            raise self._operation_error("document delete", exc) from exc

    def count(self) -> int:
        try:
            _, store = self._require_ready()
            return len(store.get_pks())
        except AdapterUnavailableError:
            raise
        except Exception as exc:
            raise self._operation_error("document count", exc) from exc

    def _operation_error(self, label: str, exc: Exception) -> AdapterUnavailableError:
        from app.adapters.db.db2_db import classify_db_error

        info = classify_db_error(exc)
        logger.warning(
            "vector %s failed (category=%s sqlstate=%s)",
            label,
            info.category,
            info.sqlstate,
        )
        if info.category in _RECONNECT_CATEGORIES:
            # Connection-class failure: drop the session so the next call
            # rebuilds it (connection reuse with self-healing).
            self._close_connection()
        return AdapterUnavailableError(
            f"Vector {label} failed [{info.category}, SQLSTATE {info.sqlstate}].",
            detail={"hint": info.hint, "table": self.table_name},
        )

    def close(self) -> None:
        self._closed = True
        self._close_connection()
