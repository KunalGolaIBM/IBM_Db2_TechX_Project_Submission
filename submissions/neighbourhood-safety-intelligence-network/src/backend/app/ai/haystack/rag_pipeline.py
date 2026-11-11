"""Safety-protocol retrieval: Haystack BM25, fused with Db2 vector search when available.

* Keyword path: a Haystack 2 Pipeline with an InMemoryBM25Retriever over the approved protocols.
* Semantic path: VECTOR_DISTANCE over protocol embeddings stored in IBM Db2
  (see ai/semantic/db2_vector_store.py), active in DATABASE_MODE=db2.
* The two rankings are merged with reciprocal rank fusion (RRF), so a protocol found by both
  rises to the top, and either path alone still works.
"""
import logging
import re
from typing import Any, Dict, List, Optional

from haystack import Document, Pipeline
from haystack.components.retrievers.in_memory import InMemoryBM25Retriever
from haystack.document_stores.in_memory import InMemoryDocumentStore

from backend.app.ai.haystack.documents import APPROVED_CIVIC_SAFETY_DOCUMENTS
from backend.app.ai.semantic.db2_vector_store import vector_store

logger = logging.getLogger("neighbourhood_safety.haystack")

RRF_K = 60  # standard reciprocal-rank-fusion constant

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of",
    "with", "by", "from", "up", "about", "into", "over", "after", "is", "are",
    "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "what", "how", "should", "when", "where", "who", "which", "can", "my", "i",
}


def _keywords(text: str) -> set:
    return {w for w in re.findall(r"\b[a-zA-Z0-9_-]{2,}\b", text.lower()) if w not in _STOPWORDS}


class HaystackDocumentStore:
    """Haystack InMemoryDocumentStore (BM25) + InMemoryBM25Retriever in a Pipeline, with category filters."""

    def __init__(self):
        self.docs_by_id: Dict[str, Dict[str, Any]] = {d["id"]: d for d in APPROVED_CIVIC_SAFETY_DOCUMENTS}
        self.document_store = InMemoryDocumentStore(bm25_algorithm="BM25Okapi")
        self.document_store.write_documents([
            Document(id=d["id"], content=f"{d['title']}. {d['content']}", meta={"category": d["category"]})
            for d in APPROVED_CIVIC_SAFETY_DOCUMENTS
        ])
        self.pipeline = Pipeline()
        self.pipeline.add_component("retriever", InMemoryBM25Retriever(document_store=self.document_store))
        logger.info("Haystack BM25 store indexed %d approved civic safety documents.",
                    self.document_store.count_documents())

    def _bm25(self, query_text: str, category: Optional[str], top_k: int) -> List[Document]:
        params: Dict[str, Any] = {"query": query_text, "top_k": top_k}
        if category:
            params["filters"] = {"field": "meta.category", "operator": "==", "value": category}
        documents = self.pipeline.run({"retriever": params})["retriever"]["documents"]
        # BM25 always ranks something; keep only documents that share real keywords with the query.
        q_terms = _keywords(query_text)
        return [d for d in documents if q_terms & _keywords(d.content or "")]

    def query(self, query_text: str, category: Optional[str] = None, top_k: int = 3) -> Dict[str, Any]:
        if not _keywords(query_text):
            return {"results": [], "found": False, "retrieval_mode": "none",
                    "message": "Query was empty or contained no searchable keywords."}

        bm25_hits = self._bm25(query_text, category, top_k)
        vector_hits = [h for h in vector_store.search_protocols(query_text, k=top_k)
                       if not category or self.docs_by_id.get(h.key, {}).get("category") == category]

        fused: Dict[str, float] = {}
        bm25_scores: Dict[str, float] = {}
        distances: Dict[str, float] = {}
        for rank, doc in enumerate(bm25_hits):
            fused[doc.id] = fused.get(doc.id, 0.0) + 1.0 / (RRF_K + rank + 1)
            bm25_scores[doc.id] = float(doc.score or 0.0)
        for rank, hit in enumerate(vector_hits):
            fused[hit.key] = fused.get(hit.key, 0.0) + 1.0 / (RRF_K + rank + 1)
            distances[hit.key] = hit.distance

        mode = "hybrid (Haystack BM25 + Db2 VECTOR_DISTANCE)" if vector_store.enabled else "Haystack BM25"
        if not fused:
            return {"results": [], "found": False, "retrieval_mode": mode, "query": query_text,
                    "message": "No approved safety protocol matched the query. Please consult on-duty responders."}

        ranked = sorted(fused, key=lambda doc_id: fused[doc_id], reverse=True)[:top_k]
        results = []
        for doc_id in ranked:
            d = self.docs_by_id[doc_id]
            results.append({
                "document_id": doc_id,
                "title": d["title"],
                "category": d["category"],
                "excerpt": d["content"],
                "source": d["source"],
                "relevance_score": round(fused[doc_id] * 100, 3),
                "matched_by": "+".join(m for m, hit in (("bm25", doc_id in bm25_scores),
                                                        ("vector", doc_id in distances)) if hit),
                "bm25_score": round(bm25_scores[doc_id], 3) if doc_id in bm25_scores else None,
                "vector_distance": round(distances[doc_id], 4) if doc_id in distances else None,
            })
        return {"results": results, "found": True, "count": len(results), "retrieval_mode": mode,
                "top_source": results[0]["source"], "query": query_text}


# Global singleton document store
haystack_store = HaystackDocumentStore()


def retrieve_safety_guidance(query: str, category: Optional[str] = None) -> Dict[str, Any]:
    return haystack_store.query(query_text=query, category=category)
