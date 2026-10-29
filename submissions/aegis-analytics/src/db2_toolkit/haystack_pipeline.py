"""Deepset Haystack 2.x Integration for IBM Db2 (ibm-db-haystack).

Implements Db2DocumentStore and Db2EmbeddingRetriever for end-to-end
financial QA and document search.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from db2_toolkit.connection import Db2ConnectionManager, get_db2_pool
from db2_toolkit.langchain_agent import _cosine_similarity, _simple_embedding


@dataclass
class HaystackDocument:
    """Document representation compatible with Haystack 2.x."""

    content: str
    id: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    score: Optional[float] = None


class Db2DocumentStore:
    """Haystack 2.x Document Store backed by IBM Db2 LUW."""

    def __init__(
        self,
        table_name: str = "DB2_VECTOR_STORE",
        connection_manager: Optional[Db2ConnectionManager] = None,
    ) -> None:
        self.table_name = table_name.upper()
        self.pool = connection_manager or get_db2_pool()

    def count_documents(self) -> int:
        """Returns the total number of documents stored."""
        sql = f"SELECT COUNT(*) FROM {self.table_name}"
        rows = self.pool.execute_query(sql)
        if rows:
            first_val = list(rows[0].values())[0]
            return int(first_val)
        return 0

    def write_documents(self, documents: List[HaystackDocument]) -> int:
        """Writes documents to the Db2 table."""
        count = 0
        for idx, doc in enumerate(documents):
            doc_id = doc.id or f"haystack_{int(datetime.now(timezone.utc).timestamp())}_{idx}"
            embedding = doc.embedding or _simple_embedding(doc.content)
            meta_json = json.dumps(doc.meta)

            if self.pool.is_mock:
                self.pool.sandbox.execute_statement(
                    f"INSERT INTO {self.table_name}",
                    {
                        "DOC_ID": doc_id,
                        "CONTENT": doc.content,
                        "METADATA_JSON": meta_json,
                        "EMBEDDING": embedding,
                        "CREATED_AT": datetime.now(timezone.utc).isoformat(),
                    },
                )
            else:
                sql = (
                    f"INSERT INTO {self.table_name} (DOC_ID, CONTENT, METADATA_JSON, EMBEDDING, CREATED_AT) "
                    f"VALUES (?, ?, ?, ?, CURRENT TIMESTAMP)"
                )
                self.pool.execute_statement(sql, (doc_id, doc.content, meta_json, json.dumps(embedding)))
            count += 1
        return count

    def get_all_documents(self) -> List[HaystackDocument]:
        """Fetches all documents from storage."""
        sql = f"SELECT DOC_ID, CONTENT, METADATA_JSON, EMBEDDING FROM {self.table_name} FETCH FIRST 100 ROWS ONLY"
        rows = self.pool.execute_query(sql)
        docs = []
        for r in rows:
            content = r.get("CONTENT", "")
            raw_meta = r.get("METADATA_JSON", "{}")
            meta = json.loads(raw_meta) if isinstance(raw_meta, str) else raw_meta
            emb = r.get("EMBEDDING")
            if isinstance(emb, str):
                try:
                    emb = json.loads(emb)
                except Exception:
                    emb = _simple_embedding(content)
            elif not isinstance(emb, list):
                emb = _simple_embedding(content)

            docs.append(
                HaystackDocument(
                    id=r.get("DOC_ID"),
                    content=content,
                    meta=meta,
                    embedding=emb,
                )
            )
        return docs


class Db2EmbeddingRetriever:
    """Haystack 2.x Retriever retrieving documents from Db2DocumentStore."""

    def __init__(self, document_store: Db2DocumentStore, top_k: int = 3) -> None:
        self.document_store = document_store
        self.top_k = top_k

    def run(self, query_text: str, top_k: Optional[int] = None) -> Dict[str, List[HaystackDocument]]:
        """Retrieves top-k closest documents to the query string."""
        k = top_k or self.top_k
        query_vec = _simple_embedding(query_text)
        all_docs = self.document_store.get_all_documents()

        scored: List[HaystackDocument] = []
        for doc in all_docs:
            if doc.embedding:
                score = _cosine_similarity(query_vec, doc.embedding)
                scored.append(
                    HaystackDocument(
                        id=doc.id,
                        content=doc.content,
                        meta=doc.meta,
                        embedding=doc.embedding,
                        score=round(score, 4),
                    )
                )

        scored.sort(key=lambda d: d.score or 0.0, reverse=True)
        return {"documents": scored[:k]}


class Db2HaystackPipeline:
    """Orchestrates an end-to-end Haystack 2.x pipeline over IBM Db2."""

    def __init__(self, document_store: Optional[Db2DocumentStore] = None) -> None:
        self.doc_store = document_store or Db2DocumentStore()
        self.retriever = Db2EmbeddingRetriever(document_store=self.doc_store)

    def run_qa(self, query: str) -> Dict[str, Any]:
        """Runs retrieval and answer synthesis."""
        retrieval_res = self.retriever.run(query)
        docs = retrieval_res["documents"]

        if docs:
            top_doc = docs[0]
            answer = f"According to record ({top_doc.id}): {top_doc.content}"
        else:
            answer = "No matching financial records found in IBM Db2 document store."

        return {
            "query": query,
            "answer": answer,
            "retrieved_documents": [
                {"id": d.id, "content": d.content, "score": d.score, "meta": d.meta}
                for d in docs
            ],
        }

