"""
IBM Db2 Native Vector Store Integration via `llama-index-vector-stores-db2` (`DB2LlamaVS`).

Supports two transparent execution modes:
1. Live IBM Db2 LUW 12.1.2+ (`VECTOR(384, FLOAT32)` + `SYSTOOLS.BSON2JSON` pushdown)
2. Offline Cosine + Metadata-Filter Simulator backed by `MockDb2Connection`
   when `is_live_db2_available()` is False (avoiding driver tuple crashes).
"""
import logging
from typing import Any, Dict, List, Optional

import numpy as np

try:
    from llama_index.core.schema import TextNode
    from llama_index.core.vector_stores.types import (
        VectorStoreQuery,
        VectorStoreQueryResult,
        MetadataFilters,
    )
    from llama_index.vector_stores.db2 import DB2LlamaVS, DistanceStrategy
except ImportError:
    TextNode = None
    VectorStoreQuery = None

    class VectorStoreQueryResult:
        def __init__(self, nodes=None, similarities=None, ids=None):
            self.nodes = nodes or []
            self.similarities = similarities or []
            self.ids = ids or []

    MetadataFilters = None
    DB2LlamaVS = None

    class DistanceStrategy:
        COSINE = "COSINE"

from src.db import get_dbi_connection, is_live_db2_available
from src.security import validate_doc_id

logger = logging.getLogger("bakebox.vector_store")


def _matches_metadata_filters(metadata: Dict[str, Any], filters: Any) -> bool:
    """Evaluate LlamaIndex MetadataFilters (or plain dict predicates) cleanly."""
    if not filters:
        return True

    filter_list = getattr(filters, "filters", None)
    if filter_list is None and isinstance(filters, dict):
        for k, v in filters.items():
            if k == "__max_price":
                p = metadata.get("price")
                if p is None or float(p) > float(v):
                    return False
            elif isinstance(v, (list, tuple, set)):
                if metadata.get(k) not in v:
                    return False
            elif metadata.get(k) != v:
                return False
        return True

    condition_raw = getattr(filters, "condition", "and")
    condition = str(getattr(condition_raw, "value", condition_raw)).lower()
    outcomes: List[bool] = []
    for f in (filter_list or []):
        key = getattr(f, "key", None)
        val = getattr(f, "value", None)
        raw_op = getattr(f, "operator", "==")
        op = str(getattr(raw_op, "value", raw_op)).lower()
        actual = metadata.get(key)

        if op in ("==", "eq"):
            outcomes.append(actual == val)
        elif op in ("!=", "ne"):
            outcomes.append(actual != val)
        elif op in ("in", "filteroperator.in"):
            outcomes.append(actual in (val or []))
        elif op in ("<=", "lte"):
            outcomes.append(actual is not None and float(actual) <= float(val))
        elif op in (">=", "gte"):
            outcomes.append(actual is not None and float(actual) >= float(val))
        else:
            outcomes.append(actual == val)

    if not outcomes:
        return True
    return any(outcomes) if condition == "or" else all(outcomes)


class _OfflineMockVectorStore:
    """Cosine similarity + MetadataFilter simulator backed by MockDb2Connection."""
    def __init__(self, connection: Any, table_name: str, embed_dim: int):
        self.connection = connection
        self.table_name = table_name
        self.embed_dim = embed_dim

    def add(self, nodes: List[Any]) -> List[str]:
        store = self.connection.tables.setdefault(self.table_name, {})
        ids = []
        for n in nodes:
            nid = getattr(n, "id_", None) or getattr(n, "node_id", None) or str(len(store) + 1)
            emb = list(getattr(n, "embedding", None) or [])
            store[nid] = {
                "node": n,
                "embedding": np.asarray(emb, dtype=np.float32),
                "metadata": dict(getattr(n, "metadata", {}) or {}),
            }
            ids.append(nid)
        return ids

    def query(self, query: Any, filters: Optional[Any] = None) -> VectorStoreQueryResult:
        store = self.connection.tables.get(self.table_name, {})
        if not store:
            return VectorStoreQueryResult(nodes=[], similarities=[], ids=[])

        q_vec = np.asarray(getattr(query, "query_embedding", []), dtype=np.float32)
        q_norm = float(np.linalg.norm(q_vec)) or 1.0
        top_k = int(getattr(query, "similarity_top_k", 5) or 5)
        active_filters = getattr(query, "filters", None) or filters

        scored = []
        for nid, rec in store.items():
            if not _matches_metadata_filters(rec["metadata"], active_filters):
                continue
            d_vec = rec["embedding"]
            if d_vec.size == 0 or d_vec.size != q_vec.size:
                continue
            d_norm = float(np.linalg.norm(d_vec)) or 1.0
            cos_sim = float(np.dot(q_vec, d_vec) / (q_norm * d_norm))
            scored.append((nid, rec["node"], cos_sim))

        scored.sort(key=lambda x: x[2], reverse=True)
        top = scored[:top_k]
        return VectorStoreQueryResult(
            nodes=[item[1] for item in top],
            similarities=[item[2] for item in top],
            ids=[item[0] for item in top],
        )

    def delete(self, doc_id: str) -> None:
        safe_id = validate_doc_id(doc_id)
        store = self.connection.tables.get(self.table_name, {})
        store.pop(safe_id, None)


class BakeboxDb2VectorStore:
    """
    Dual-mode wrapper around official IBM Db2 `DB2LlamaVS` vector store.
    Executes in-engine COSINE distance + BSON metadata filters on live Db2 v12.1.2+,
    or exact cosine + metadata simulation on `MockDb2Connection` offline.
    """
    def __init__(
        self,
        table_name: str = "BB_CHUNKS_VECTOR",
        embed_dim: int = 384,
        distance_strategy: DistanceStrategy = DistanceStrategy.COSINE,
    ):
        self.table_name = table_name
        self.embed_dim = embed_dim
        self.distance_strategy = distance_strategy
        self.is_live_db2 = is_live_db2_available() and (DB2LlamaVS is not None)
        self.connection = get_dbi_connection()

        strat_name = getattr(distance_strategy, "name", str(distance_strategy))
        if self.is_live_db2:
            logger.info(
                "Initializing live DB2LlamaVS on table '%s' (dim=%d, strategy=%s)",
                table_name, embed_dim, strat_name,
            )
            self.vs = DB2LlamaVS(
                _client=self.connection,
                table_name=self.table_name,
                distance_strategy=self.distance_strategy,
                embed_dim=self.embed_dim,
            )
        else:
            logger.info(
                "Initializing offline cosine vector store simulator on '%s' (dim=%d, strategy=%s)",
                table_name, embed_dim, strat_name,
            )
            self.vs = _OfflineMockVectorStore(self.connection, self.table_name, self.embed_dim)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def add_nodes(self, nodes: List[Any]):
        """Ingest TextNode objects with pre-computed 384-d embeddings."""
        return self.vs.add(nodes)

    def query(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Any] = None,
    ) -> VectorStoreQueryResult:
        """
        Execute native vector similarity search with metadata predicate pushdown.
        """
        if VectorStoreQuery is not None and self.is_live_db2:
            q = VectorStoreQuery(
                query_embedding=query_embedding,
                similarity_top_k=top_k,
                filters=filters,
            )
            return self.vs.query(q)

        # In offline simulator, pass lightweight query object + filters directly
        class _SimQuery:
            def __init__(self, emb, k, f):
                self.query_embedding = emb
                self.similarity_top_k = k
                self.filters = f

        return self.vs.query(_SimQuery(query_embedding, top_k, filters))

    def delete_document(self, doc_id: str):
        """Remove a document from Db2 after strict identifier validation (SQLi guard)."""
        safe_doc_id = validate_doc_id(doc_id)
        return self.vs.delete(safe_doc_id)

    def close(self) -> None:
        """Close underlying Db2 connection cleanly."""
        if getattr(self, "connection", None) is not None:
            try:
                if self.is_live_db2:
                    self.connection.close()
                self.connection = None
            except Exception as exc:
                logger.warning("Error closing Db2 vector store connection: %s", exc)
