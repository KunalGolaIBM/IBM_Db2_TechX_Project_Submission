"""
Haystack Integration for IBM Db2
Implements IBMDb2DocumentStore and IBMDb2EmbeddingRetriever for semantic
opportunity matching with COSINE distance and 384-dimensional dense vectors.
Gracefully provides a local vector store fallback for environments where
native C-extension drivers are restricted by operating system policy.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import date
from app.core.config import settings
from app.ai.embeddings import generate_embedding
from app.ai.vector_search import cosine_similarity

logger = logging.getLogger("cloud_loop.haystack")

class HaystackDb2Service:
    def __init__(self):
        self._store = None
        self._is_native = False
        self._fallback_docs: List[Dict[str, Any]] = []

    def get_document_store(self, recreate_table: bool = False):
        """
        Initializes and returns the IBMDb2DocumentStore if credentials and driver are available.
        Otherwise initializes the fallback semantic memory store.
        """
        if self._store is not None and not recreate_table:
            return self._store

        if settings.is_db2_configured:
            try:
                from haystack.utils import Secret
                from haystack_integrations.document_stores.ibm_db import IBMDb2DocumentStore

                logger.info(
                    f"Initializing IBMDb2DocumentStore on {settings.host}:{settings.DB2_PORT}/{settings.database_name} "
                    f"schema={settings.DB2_SCHEMA} table={settings.DB2_TABLE_KB} dim={settings.EMBEDDING_DIM}"
                )
                self._store = IBMDb2DocumentStore(
                    database=settings.database_name,
                    hostname=settings.host,
                    port=settings.DB2_PORT,
                    username=Secret.from_token(settings.username),
                    password=Secret.from_token(settings.password),
                    schema=settings.DB2_SCHEMA,
                    table_name=settings.DB2_TABLE_KB,
                    embedding_dim=settings.EMBEDDING_DIM,
                    distance_metric=settings.DISTANCE_METRIC,
                    recreate_table=recreate_table,
                )
                self._is_native = True
                logger.info("IBMDb2DocumentStore successfully connected to live Db2.")
                return self._store
            except Exception as e:
                logger.warning(
                    f"IBMDb2DocumentStore live connection unavailable ({e}). "
                    "Operating via unified fallback vector store."
                )

        self._is_native = False
        return self

    def write_documents(self, documents: List[Any], policy: str = "OVERWRITE") -> int:
        """
        Writes Haystack Document objects to IBM Db2 or fallback store.
        """
        if self._is_native and self._store is not None:
            return self._store.write_documents(documents, policy=policy)

        # Fallback in-memory index
        written = 0
        for doc in documents:
            doc_id = getattr(doc, "id", None) or (doc.get("id") if isinstance(doc, dict) else None)
            content = getattr(doc, "content", None) or (doc.get("content", "") if isinstance(doc, dict) else "")
            meta = getattr(doc, "meta", None) or (doc.get("meta", {}) if isinstance(doc, dict) else {})
            embedding = getattr(doc, "embedding", None) or (doc.get("embedding") if isinstance(doc, dict) else None)

            if not embedding and content:
                embedding = generate_embedding(content)

            self._fallback_docs = [d for d in self._fallback_docs if d["id"] != doc_id]
            self._fallback_docs.append({
                "id": doc_id,
                "content": content,
                "meta": meta,
                "embedding": embedding
            })
            written += 1
        return written

    def count_documents(self) -> int:
        if self._is_native and self._store is not None:
            return self._store.count_documents()
        return len(self._fallback_docs)

    def search(
        self,
        query: str,
        query_embedding: Optional[List[float]] = None,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Performs semantic vector search with optional metadata filtering.
        Filters run inside Db2 when native store is active.
        """
        if not query_embedding:
            query_embedding = generate_embedding(query)

        if self._is_native and self._store is not None:
            try:
                from haystack_integrations.components.retrievers.ibm_db import IBMDb2EmbeddingRetriever

                retriever = IBMDb2EmbeddingRetriever(document_store=self._store, top_k=top_k)
                res = retriever.run(query_embedding=query_embedding, filters=filters)
                docs = res.get("documents", [])
                return [
                    {
                        "id": d.id,
                        "content": d.content,
                        "score": getattr(d, "score", 0.0),
                        "meta": d.meta
                    }
                    for d in docs
                ]
            except Exception as e:
                logger.error(f"Native IBM Db2 vector search failed: {e}. Using fallback.")

        # Resilient fallback search
        results = []
        today_str = date.today().isoformat()

        for d in self._fallback_docs:
            meta = d.get("meta", {})

            # Filter out expired
            dl = meta.get("deadline")
            if dl and dl < today_str:
                continue

            # Apply metadata filters (e.g. meta.kind or meta.opportunity_type)
            if filters:
                field = filters.get("field", "")
                val = filters.get("value")
                op = filters.get("operator", "==")
                if field.startswith("meta."):
                    k = field[5:]
                    actual = meta.get(k)
                    if op in ("==", "="):
                        if actual != val:
                            continue
                    elif op in ("in", "$in"):
                        if actual not in val:
                            continue

            emb = d.get("embedding")
            if emb:
                score = cosine_similarity(query_embedding, emb)
            else:
                score = 0.5

            results.append({
                "id": d["id"],
                "content": d["content"],
                "score": round(score, 4),
                "meta": meta
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

haystack_db2_service = HaystackDb2Service()
