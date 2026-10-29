"""LlamaIndex Vector Store Integration for IBM Db2 (llama-index-vector-stores-db2).

Provides dense document indexing, hybrid semantic vector search,
and metadata filtering for financial filings and research briefs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from db2_toolkit.connection import Db2ConnectionManager, get_db2_pool
from db2_toolkit.langchain_agent import _cosine_similarity, _simple_embedding


@dataclass
class TextNode:
    """Represents a discrete text chunk/node in LlamaIndex."""

    text: str
    node_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None


@dataclass
class VectorStoreQuery:
    """LlamaIndex-style query bundle."""

    query_str: str
    similarity_top_k: int = 5
    filters: Optional[Dict[str, Any]] = None
    query_embedding: Optional[List[float]] = None


@dataclass
class VectorStoreQueryResult:
    """LlamaIndex vector query result."""

    nodes: List[TextNode]
    similarities: List[float]
    ids: List[str]


class Db2LlamaIndexVectorStore:
    """LlamaIndex-compatible vector store storing embeddings in IBM Db2."""

    def __init__(
        self,
        table_name: str = "DB2_VECTOR_STORE",
        connection_manager: Optional[Db2ConnectionManager] = None,
    ) -> None:
        self.table_name = table_name.upper()
        self.pool = connection_manager or get_db2_pool()

    def add(self, nodes: List[TextNode]) -> List[str]:
        """Adds text nodes into IBM Db2 vector storage."""
        added_ids: List[str] = []
        for idx, node in enumerate(nodes):
            node_id = node.node_id or f"node_{int(datetime.now(timezone.utc).timestamp())}_{idx}"
            embedding = node.embedding or _simple_embedding(node.text)

            sql = (
                f"INSERT INTO {self.table_name} (DOC_ID, CONTENT, METADATA_JSON, EMBEDDING, CREATED_AT) "
                f"VALUES (?, ?, ?, ?, CURRENT TIMESTAMP)"
            )
            meta_json = json.dumps(node.metadata)

            if self.pool.is_mock:
                self.pool.sandbox.execute_statement(
                    f"INSERT INTO {self.table_name}",
                    {
                        "DOC_ID": node_id,
                        "CONTENT": node.text,
                        "METADATA_JSON": meta_json,
                        "EMBEDDING": embedding,
                        "CREATED_AT": datetime.now(timezone.utc).isoformat(),
                    },
                )
            else:
                self.pool.execute_statement(
                    sql, (node_id, node.text, meta_json, json.dumps(embedding))
                )

            added_ids.append(node_id)
        return added_ids

    def query(self, query: VectorStoreQuery) -> VectorStoreQueryResult:
        """Executes a dense vector search with optional metadata filtering."""
        query_vec = query.query_embedding or _simple_embedding(query.query_str)

        sql = f"SELECT DOC_ID, CONTENT, METADATA_JSON, EMBEDDING FROM {self.table_name} FETCH FIRST 100 ROWS ONLY"
        rows = self.pool.execute_query(sql)

        scored: List[tuple[TextNode, float, str]] = []
        for r in rows:
            text = r.get("CONTENT", "")
            raw_meta = r.get("METADATA_JSON", "{}")
            meta = json.loads(raw_meta) if isinstance(raw_meta, str) else raw_meta

            # Apply metadata filters if provided
            if query.filters:
                skip = False
                for k, v in query.filters.items():
                    if meta.get(k) != v:
                        skip = True
                        break
                if skip:
                    continue

            emb = r.get("EMBEDDING")
            if isinstance(emb, str):
                try:
                    emb = json.loads(emb)
                except Exception:
                    emb = _simple_embedding(text)
            elif not isinstance(emb, list):
                emb = _simple_embedding(text)

            sim = _cosine_similarity(query_vec, emb)
            node = TextNode(
                text=text,
                node_id=r.get("DOC_ID"),
                metadata=meta,
                embedding=emb,
            )
            scored.append((node, sim, r.get("DOC_ID", "")))

        # Sort by similarity descending
        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[: query.similarity_top_k]

        return VectorStoreQueryResult(
            nodes=[item[0] for item in top],
            similarities=[item[1] for item in top],
            ids=[item[2] for item in top],
        )

    def delete(self, doc_ids: List[str]) -> int:
        """Deletes vectors by ID."""
        deleted = 0
        for doc_id in doc_ids:
            sql = f"DELETE FROM {self.table_name} WHERE DOC_ID = ?"
            deleted += self.pool.execute_statement(sql, (doc_id,))
        return deleted

