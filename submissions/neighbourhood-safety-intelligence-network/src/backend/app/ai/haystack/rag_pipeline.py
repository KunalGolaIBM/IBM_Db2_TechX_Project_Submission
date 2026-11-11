import logging
import re
from typing import List, Dict, Any, Optional

from haystack import Document, Pipeline
from haystack.components.retrievers.in_memory import InMemoryBM25Retriever
from haystack.document_stores.in_memory import InMemoryDocumentStore

from backend.app.ai.haystack.documents import APPROVED_CIVIC_SAFETY_DOCUMENTS

logger = logging.getLogger("neighbourhood_safety.haystack")

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of",
    "with", "by", "from", "up", "about", "into", "over", "after", "is", "are",
    "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "what", "how", "should", "when", "where", "who", "which", "can", "my", "i",
}


def _keywords(text: str) -> set:
    return {w for w in re.findall(r"\b[a-zA-Z0-9_-]{2,}\b", text.lower()) if w not in _STOPWORDS}


class HaystackDocumentStore:
    """
    Retrieval over the approved civic safety protocols using Haystack:
    an InMemoryDocumentStore indexed with BM25 and an InMemoryBM25Retriever
    wrapped in a Haystack Pipeline, with metadata filtering by category.
    """

    def __init__(self, top_k: int = 3):
        self.document_store = InMemoryDocumentStore(bm25_algorithm="BM25Okapi")
        self.document_store.write_documents([
            Document(
                id=doc["id"],
                content=f"{doc['title']}. {doc['content']}",
                meta={
                    "title": doc["title"],
                    "category": doc["category"],
                    "source": doc["source"],
                    "body": doc["content"],
                },
            )
            for doc in APPROVED_CIVIC_SAFETY_DOCUMENTS
        ])
        self.pipeline = Pipeline()
        self.pipeline.add_component(
            "retriever", InMemoryBM25Retriever(document_store=self.document_store, top_k=top_k)
        )
        logger.info(
            "Haystack BM25 store indexed %d approved civic safety documents.",
            self.document_store.count_documents(),
        )

    def query(self, query_text: str, category: Optional[str] = None, top_k: int = 3) -> Dict[str, Any]:
        """
        Runs the Haystack retrieval pipeline and returns cited results, or an explicit
        'not found' state when no protocol shares meaningful keywords with the query.
        """
        q_terms = _keywords(query_text)
        if not q_terms:
            return {
                "results": [],
                "found": False,
                "message": "Query was empty or contained no searchable keywords.",
            }

        retriever_input: Dict[str, Any] = {"query": query_text, "top_k": top_k}
        if category:
            retriever_input["filters"] = {"field": "meta.category", "operator": "==", "value": category}

        documents: List[Document] = self.pipeline.run({"retriever": retriever_input})["retriever"]["documents"]

        # BM25 always ranks something; only keep documents that actually share keywords with the query.
        relevant = [d for d in documents if q_terms & _keywords(d.content or "")]

        if not relevant:
            return {
                "results": [],
                "found": False,
                "message": "No approved safety protocol matched the specific query criteria. Please consult on-duty responders.",
                "query": query_text,
            }

        results = [
            {
                "document_id": d.id,
                "title": d.meta["title"],
                "category": d.meta["category"],
                "excerpt": d.meta["body"],
                "source": d.meta["source"],
                "relevance_score": round(float(d.score or 0.0), 3),
            }
            for d in relevant
        ]
        return {
            "results": results,
            "found": True,
            "count": len(results),
            "top_source": results[0]["source"],
            "query": query_text,
        }


# Global singleton document store
haystack_store = HaystackDocumentStore()


def retrieve_safety_guidance(query: str, category: Optional[str] = None) -> Dict[str, Any]:
    return haystack_store.query(query_text=query, category=category)
