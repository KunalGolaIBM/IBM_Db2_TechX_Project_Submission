"""
GitMind 2.0 — IBM Db2 Vector Store Integration

Implements native vector search over IBM Db2 using the official `langchain-db2`
`DB2VS` connector:
- Native Db2 VECTOR data type and VECTOR_DISTANCE execution
- Cosine distance strategy
- Dynamic dimension detection based on embedding model
- Deterministic, stable chunk and document identifiers
- Strict repository isolation and metadata filtering
- Batch ingestion with error reconciliation
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_db2 import DB2VS
from langchain_db2.db2vs import DistanceStrategy

import config
from data.db2.connection import Db2ConnectionManager, get_connection_manager

logger = logging.getLogger("gitmind.db2.vector_store")


def stable_vector_id(repo_id: str, artifact_type: str, source_key: str, chunk_index: int = 0) -> str:
    """
    Generate a deterministic document identifier.
    e.g. 'repo123:commit:abc1234:0'
    """
    return f"{repo_id}:{artifact_type}:{source_key}:{chunk_index}"


class Db2VectorStore:
    """
    Production vector store wrapper around langchain-db2 DB2VS.
    """

    def __init__(
        self,
        table_name: Optional[str] = None,
        connection_manager: Optional[Db2ConnectionManager] = None,
        embedding_model: Optional[Embeddings] = None,
    ):
        self.table_name = (table_name or config.DB2_VECTOR_TABLE).upper()
        self.connection_manager = connection_manager or get_connection_manager()
        self._embedding_model = embedding_model
        self._db2vs: Optional[DB2VS] = None

    def _get_embeddings(self) -> Embeddings:
        """Lazy load the configured LangChain Embeddings model."""
        if self._embedding_model is None:
            self._embedding_model = config.get_embeddings()
        return self._embedding_model

    def _get_db2vs(self) -> DB2VS:
        """Instantiate and cache the underlying DB2VS instance."""
        if self._db2vs is None:
            if not config.has_embedding_api_key():
                raise ValueError(
                    f"No valid API key configured for embedding provider '{config.EMBEDDING_PROVIDER}'. "
                    "Please set GEMINI_API_KEY or OPENAI_API_KEY in your .env file."
                )
            embeddings = self._get_embeddings()
            conn = self.connection_manager.connect()

            try:
                self._db2vs = DB2VS(
                    embedding_function=embeddings,
                    table_name=self.table_name,
                    client=conn,
                    distance_strategy=DistanceStrategy.COSINE,
                    query="GitMind vector probe",
                    text_field="text",
                )
            except Exception as e:
                try:
                    conn.close()
                except Exception:
                    pass
                raise RuntimeError(
                    f"Failed to initialize Db2 vector store table '{self.table_name}': {e}"
                ) from e

        return self._db2vs

    # -----------------------------------------------------------------------
    # Ingestion Methods
    # -----------------------------------------------------------------------

    def add_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
        batch_size: int = 50,
    ) -> List[str]:
        """
        Ingest text chunks and metadata into Db2 with batching.
        Returns list of inserted vector record IDs.
        """
        if not texts:
            return []

        vs = self._get_db2vs()
        all_ids: List[str] = []

        total = len(texts)
        for i in range(0, total, batch_size):
            batch_texts = texts[i : i + batch_size]
            batch_meta = metadatas[i : i + batch_size] if metadatas else None
            batch_ids = ids[i : i + batch_size] if ids else None

            inserted = vs.add_texts(
                texts=batch_texts,
                metadatas=batch_meta,
                ids=batch_ids,
            )
            all_ids.extend(inserted)

        return all_ids

    def add_documents(
        self,
        documents: List[Document],
        ids: Optional[List[str]] = None,
        batch_size: int = 50,
    ) -> List[str]:
        """Ingest LangChain Document objects into Db2."""
        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        return self.add_texts(texts=texts, metadatas=metadatas, ids=ids, batch_size=batch_size)

    # -----------------------------------------------------------------------
    # Search & Retrieval
    # -----------------------------------------------------------------------

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 5,
        repo_id: Optional[str] = None,
        filter_type: Optional[str] = None,
        extra_filters: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[Document, float]]:
        """
        Semantic similarity search in Db2 returning (Document, cosine_distance).
        Applies metadata filtering for repository isolation.
        """
        if not config.has_embedding_api_key():
            logger.warning(
                f"Vector search skipped: no valid API key configured for '{config.EMBEDDING_PROVIDER}'. "
                "Set GEMINI_API_KEY or OPENAI_API_KEY in .env to enable semantic search."
            )
            return []

        vs = self._get_db2vs()

        filters: Dict[str, Any] = {}
        if repo_id:
            # Set-based lookup ensures exact match in DB2VS filter condition
            filters["repo_id"] = {repo_id}
        if filter_type:
            filters["type"] = {filter_type}
        if extra_filters:
            for k_filt, v_filt in extra_filters.items():
                filters[k_filt] = {v_filt} if not isinstance(v_filt, (set, list, tuple)) else set(v_filt)

        # Retrieve a slightly larger candidate set to guarantee k items after metadata filter
        fetch_k = max(k * 3, 10) if filters else k

        results = vs.similarity_search_with_score(
            query=query,
            k=fetch_k,
            filter=filters if filters else None,
        )

        # Re-verify repository isolation strictly
        filtered: List[Tuple[Document, float]] = []
        for doc, distance in results:
            if repo_id and doc.metadata.get("repo_id") != repo_id:
                continue
            if filter_type and doc.metadata.get("type") != filter_type:
                continue
            filtered.append((doc, distance))
            if len(filtered) >= k:
                break

        return filtered

    def similarity_search(
        self,
        query: str,
        k: int = 5,
        repo_id: Optional[str] = None,
        filter_type: Optional[str] = None,
    ) -> List[Document]:
        """Semantic search returning Documents only."""
        results = self.similarity_search_with_score(
            query=query,
            k=k,
            repo_id=repo_id,
            filter_type=filter_type,
        )
        return [doc for doc, _ in results]

    # -----------------------------------------------------------------------
    # Maintenance & Diagnostics
    # -----------------------------------------------------------------------

    def delete_by_ids(self, ids: List[str]) -> None:
        """Delete specific vectors by their stable source identifiers or hashes."""
        if not ids:
            return

        # Pre-compute the 16-character sha256 hash that DB2VS uses
        processed_ids = [
            hashlib.sha256(_id.encode()).hexdigest()[:16].upper() for _id in ids
        ]

        with self.connection_manager.cursor() as cur:
            placeholders = ",".join(["?"] * len(processed_ids))
            sql = f"DELETE FROM {self.table_name} WHERE id IN ({placeholders})"
            cur.execute(sql, tuple(processed_ids))

    def delete_by_repo(self, repo_id: str) -> int:
        """
        Delete all vectors belonging to a repository (repository isolation).
        """
        with self.connection_manager.cursor() as cur:
            # Db2 stores JSON metadata in BLOB via BSON
            sql = f"""
            DELETE FROM {self.table_name}
            WHERE id IN (
                SELECT id FROM {self.table_name}
                WHERE SYSTOOLS.BSON2JSON(metadata) LIKE ?
            )
            """
            cur.execute(sql, (f'%"{repo_id}"%',))
            return cur.rowcount

    def count(self, repo_id: Optional[str] = None) -> int:
        """Count total vectors or vectors for a specific repository."""
        with self.connection_manager.cursor() as cur:
            if repo_id:
                sql = f"SELECT COUNT(*) FROM {self.table_name} WHERE SYSTOOLS.BSON2JSON(metadata) LIKE ?"
                cur.execute(sql, (f'%"repo_id": "{repo_id}"%',))
            else:
                sql = f"SELECT COUNT(*) FROM {self.table_name}"
                cur.execute(sql)
            row = cur.fetchone()
            return int(row[0]) if row else 0

    def verify_native_vector_distance(self) -> float:
        """
        Executes native Db2 VECTOR_DISTANCE directly on the server to verify execution.
        """
        with self.connection_manager.cursor() as cur:
            cur.execute(
                "VALUES (VECTOR_DISTANCE(VECTOR('[1.0, 0.0]', 2, FLOAT32), "
                "VECTOR('[0.0, 1.0]', 2, FLOAT32), COSINE))"
            )
            row = cur.fetchone()
            if row is None:
                raise RuntimeError("Db2 VECTOR_DISTANCE probe returned no row.")
            return float(row[0])


# Global singleton instance
_global_vector_store: Optional[Db2VectorStore] = None


def get_db2_vector_store() -> Db2VectorStore:
    """Retrieve or create the global Db2VectorStore singleton."""
    global _global_vector_store
    if _global_vector_store is None:
        _global_vector_store = Db2VectorStore()
    return _global_vector_store

