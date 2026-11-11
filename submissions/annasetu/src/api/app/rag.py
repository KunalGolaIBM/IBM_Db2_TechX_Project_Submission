import hashlib
import json
import logging
import math
import re
from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore

from . import db
from .config import settings

logger = logging.getLogger(__name__)
_VECTOR_READY = False
_VECTOR_ERROR: str | None = None


class LocalFeatureEmbeddings(Embeddings):
    """Small deterministic feature-hash embedder for offline policy retrieval."""

    dimensions = 256

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = re.findall(r"[a-z0-9°−≤≥]+", text.lower())
        features = tokens + [f"{left}_{right}" for left, right in zip(tokens, tokens[1:])]
        for feature in features:
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            number = int.from_bytes(digest, "big")
            vector[number % self.dimensions] += 1.0 if number & (1 << 63) else -1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


def _store(conn) -> VectorStore:
    from langchain_db2 import DB2VS

    try:
        from langchain_db2 import DistanceStrategy
        distance = DistanceStrategy.COSINE_DISTANCE
    except (ImportError, AttributeError):
        distance = None
    args: dict[str, Any] = {
        "embedding_function": LocalFeatureEmbeddings(),
        "table_name": "ANNA_POLICY_VECTOR",
        "client": conn,
    }
    if distance is not None:
        args["distance_strategy"] = distance
    return DB2VS(**args)


def ensure_policy_index() -> bool:
    global _VECTOR_READY, _VECTOR_ERROR
    conn = db.connect()
    try:
        store = _store(conn)
        ids = store.get_pks()
        if not ids:
            documents = db.rows("SELECT DOCUMENT_ID,TITLE,SOURCE_URL,CONTENT FROM POLICY_DOCUMENTS WHERE ACTIVE=1", conn=conn)
            store.add_texts(
                texts=[doc["content"] for doc in documents],
                metadatas=[{"title": doc["title"], "source_url": doc["source_url"], "document_id": doc["document_id"].strip()} for doc in documents],
                ids=[doc["document_id"].strip() for doc in documents],
            )
        _VECTOR_READY = True
        _VECTOR_ERROR = None
        return True
    except Exception as exc:
        _VECTOR_READY = False
        _VECTOR_ERROR = str(exc)
        raise
    finally:
        conn.close()


def ask_policy(question: str) -> dict[str, Any]:
    if not _VECTOR_READY:
        raise RuntimeError(_VECTOR_ERROR or "Db2 vector search is not ready.")
    conn = db.connect()
    try:
        store = _store(conn)
        found = store.similarity_search_with_score(question, k=3)
        sources = []
        for document, score in found:
            sources.append({
                "title": document.metadata.get("title", "Food safety guidance"),
                "source_url": document.metadata.get("source_url", ""),
                "excerpt": document.page_content,
                "similarity_score": float(score),
            })
        if not sources:
            return {"answer": "No matching policy passages were retrieved from Db2. The batch remains subject to human review.", "sources": [], "mode": "Db2 vector retrieval · no language model configured"}
        answer = "Retrieved policy guidance is provided for explanation only. It cannot approve a batch. " + " ".join(source["excerpt"] for source in sources[:2])
        return {"answer": answer, "sources": sources, "mode": "LangChain retrieval over IBM Db2 vector search · no certification"}
    finally:
        conn.close()


def vector_status() -> dict[str, Any]:
    result = {"configured": True, "provider": "langchain-db2 / IBM Db2 vector search", "ready": _VECTOR_READY}
    if _VECTOR_ERROR:
        result["detail"] = _VECTOR_ERROR
    return result
