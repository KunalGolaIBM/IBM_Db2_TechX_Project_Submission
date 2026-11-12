"""Long-term project memory for AI assistants, stored in IBM Db2 through Haystack.

Two Haystack pipelines over `ibm-db-haystack`'s `IBMDb2DocumentStore`:

    remember:  Document -> OllamaDocumentEmbedder (Granite) -> DocumentWriter -> Db2 MEMORY_VECTORS
    recall:    query    -> OllamaTextEmbedder (Granite)     -> IBMDb2EmbeddingRetriever (VECTOR_DISTANCE)

Each memory carries its project, kind (decision / convention / gotcha / todo),
tags, author (the IDE that saved it) and timestamp as Db2-stored metadata, so
recall can be filtered per project and per kind inside the database.
"""

import hashlib
import time
from typing import Any, Dict, List, Optional

from ..config import ShipSafeConfig
from ..llm.granite import require_models

KINDS = ("decision", "convention", "gotcha", "todo")
TABLE = "MEMORY_VECTORS"
MAX_TEXT = 4000


class ProjectMemory:
    def __init__(self, config: ShipSafeConfig, table: str = TABLE):
        from haystack import Pipeline
        from haystack.components.writers import DocumentWriter
        from haystack.document_stores.types import DuplicatePolicy
        from haystack.utils import Secret
        from haystack_integrations.components.embedders.ollama import OllamaDocumentEmbedder, OllamaTextEmbedder
        from haystack_integrations.components.retrievers.ibm_db import IBMDb2EmbeddingRetriever
        from haystack_integrations.document_stores.ibm_db import IBMDb2DocumentStore

        self.config = config
        db2, llm = config.db2, config.llm
        self.store = IBMDb2DocumentStore(
            database=db2.database, hostname=db2.host, port=db2.port,
            username=Secret.from_token(db2.username), password=Secret.from_token(db2.password),
            schema=db2.schema, use_ssl=db2.security == "SSL", table_name=table,
            embedding_dim=llm.embed_dimension, distance_metric="COSINE")

        self.indexing = Pipeline()
        self.indexing.add_component("embedder", OllamaDocumentEmbedder(model=llm.embed_model, url=llm.host, progress_bar=False,
                                                                       timeout=llm.timeout_s))
        self.indexing.add_component("writer", DocumentWriter(document_store=self.store, policy=DuplicatePolicy.OVERWRITE))
        self.indexing.connect("embedder.documents", "writer.documents")

        self.query = Pipeline()
        self.query.add_component("embedder", OllamaTextEmbedder(model=llm.embed_model, url=llm.host, timeout=llm.timeout_s))
        self.query.add_component("retriever", IBMDb2EmbeddingRetriever(document_store=self.store, top_k=5))
        self.query.connect("embedder.embedding", "retriever.query_embedding")

    @staticmethod
    def memory_id(project: str, text: str) -> str:
        """Same text in the same project = same memory (saving twice updates instead of duplicating)."""
        return "mem_" + hashlib.sha256(f"{project}\x00{' '.join(text.split()).lower()}".encode("utf-8")).hexdigest()[:24]

    def remember(self, text: str, kind: str = "decision", project: str = "default",
                 tags: Optional[List[str]] = None, author: str = "unknown") -> Dict[str, Any]:
        from haystack import Document

        text = (text or "").strip()
        if not text:
            raise ValueError("Nothing to remember: text is empty.")
        if len(text) > MAX_TEXT:
            raise ValueError(f"Memories are limited to {MAX_TEXT} characters; save a summary instead.")
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {', '.join(KINDS)}")
        require_models(self.config.llm, chat=False, embed=True)
        doc = Document(id=self.memory_id(project, text), content=text, meta={
            "project": project, "kind": kind, "tags": ",".join(sorted({t.strip().lower() for t in tags or [] if t.strip()})),
            "author": author[:32], "created_at": int(time.time() * 1000)})
        written = self.indexing.run({"embedder": {"documents": [doc]}})["writer"]["documents_written"]
        return {"id": doc.id, "project": project, "kind": kind, "stored": bool(written), "table": f"{self.config.db2.schema}.{TABLE}"}

    def recall(self, query: str, project: Optional[str] = None, top_k: int = 5,
               kind: Optional[str] = None, min_similarity: float = 0.0) -> List[Dict[str, Any]]:
        if not (query or "").strip():
            raise ValueError("query must not be empty")
        require_models(self.config.llm, chat=False, embed=True)
        conditions = []
        if project:
            conditions.append({"field": "meta.project", "operator": "==", "value": project})
        if kind:
            conditions.append({"field": "meta.kind", "operator": "==", "value": kind})
        filters = {"operator": "AND", "conditions": conditions} if conditions else None
        docs = self.query.run({"embedder": {"text": query.strip()},
                               "retriever": {"filters": filters, "top_k": max(1, min(int(top_k), 25))}})["retriever"]["documents"]
        out = []
        for d in docs:
            similarity = round(1.0 - float(d.score), 4)  # Db2 returns COSINE distance
            if similarity < min_similarity:
                continue
            out.append({"id": d.id, "text": d.content, "kind": d.meta.get("kind"), "project": d.meta.get("project"),
                        "tags": [t for t in (d.meta.get("tags") or "").split(",") if t], "author": d.meta.get("author"),
                        "created_at": d.meta.get("created_at"), "score": similarity})
        return out

    def forget(self, memory_id: str) -> None:
        self.store.delete_documents([memory_id])

    def count(self, project: Optional[str] = None) -> int:
        if project:
            return self.store.count_documents_by_filter({"field": "meta.project", "operator": "==", "value": project})
        return self.store.count_documents()

    def close(self) -> None:
        self.store.close()
