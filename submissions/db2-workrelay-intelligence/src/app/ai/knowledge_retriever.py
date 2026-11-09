from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, List

from pydantic import Field

from app.ai.sample_runbooks import SAMPLE_RUNBOOKS

logger = logging.getLogger("ai_knowledge_retriever")

try:
    from langchain_core.callbacks import CallbackManagerForRetrieverRun
    from langchain_core.documents import Document as LCDocument
    from langchain_core.retrievers import BaseRetriever
    LANGCHAIN_AVAILABLE = True
except ImportError:
    CallbackManagerForRetrieverRun = None
    LCDocument = None
    BaseRetriever = None
    LANGCHAIN_AVAILABLE = False


@dataclass
class KnowledgeDocument:
    doc_id: str
    title: str
    category: str
    service: str
    content: str
    resolution_steps: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_langchain_document(self) -> Any:
        """Convert domain KnowledgeDocument into a LangChain Document object."""
        if not LANGCHAIN_AVAILABLE or LCDocument is None:
            return None
        text = (
            f"Title: {self.title}\n"
            f"Service: {self.service}\n"
            f"Category: {self.category}\n"
            f"Content: {self.content}\n"
            f"Resolution: {self.resolution_steps}"
        )
        meta = {
            "doc_id": self.doc_id,
            "title": self.title,
            "category": self.category,
            "service": self.service,
            "resolution_steps": self.resolution_steps,
            **self.metadata,
        }
        return LCDocument(page_content=text, metadata=meta)

    def to_llama_document(self) -> Any:
        """Compatibility alias for document conversion."""
        return self.to_langchain_document()


if LANGCHAIN_AVAILABLE and BaseRetriever is not None:
    class LangChainRunbookRetriever(BaseRetriever):
        """
        Deterministic LangChain BaseRetriever implementation for operational runbooks.
        Performs keyword/token overlap matching and service context weighting
        over LangChain Document objects without external LLM or vector DB dependencies.
        """
        documents: List[Any] = Field(default_factory=list)
        default_top_k: int = 2

        def _score_document(
            self,
            doc: Any,
            query_terms: set[str],
            service: str | None = None,
        ) -> float:
            doc_service = str(doc.metadata.get("service", "")).lower()
            if service and service.lower() != "all" and service.lower() != doc_service:
                if not (service.lower().startswith("db") and doc_service == "database"):
                    return 0.0

            doc_text = f"{doc.metadata.get('title', '')} {doc.page_content} {doc.metadata.get('resolution_steps', '')} {doc_service}".lower()
            doc_terms = set(re.findall(r"\w+", doc_text))

            overlap = len(query_terms.intersection(doc_terms))
            score = overlap / max(len(query_terms), 1)

            if service and service.lower() == doc_service:
                score += 0.3
            elif doc_service in query_terms:
                score += 0.2

            return score

        def _get_relevant_documents(
            self,
            query: str,
            *,
            run_manager: Any = None,
        ) -> List[Any]:
            # Parse optional service directive from query string (e.g. "query text service:database")
            service = None
            match = re.search(r"service:(\S+)", query)
            if match:
                service = match.group(1)
                clean_query = re.sub(r"service:\S+", "", query).strip()
            else:
                clean_query = query

            terms = set(re.findall(r"\w+", clean_query.lower()))
            scored: list[tuple[float, Any]] = []

            for doc in self.documents:
                score = self._score_document(doc, terms, service=service)
                if score > 0:
                    scored_doc = LCDocument(
                        page_content=doc.page_content,
                        metadata={**doc.metadata, "score": round(score, 3)},
                    )
                    scored.append((score, scored_doc))

            scored.sort(key=lambda x: x[0], reverse=True)
            return [d for _, d in scored[:self.default_top_k]]
else:
    class LangChainRunbookRetriever:  # type: ignore
        def __init__(self, documents: list[Any] | None = None, default_top_k: int = 2):
            self.documents = documents or []
            self.default_top_k = default_top_k

        def invoke(self, query: str) -> list[Any]:
            return []


class IncidentKnowledgeRetriever:
    """
    Operational knowledge retrieval engine powered by LangChain.
    Uses LangChain Documents and a custom deterministic BaseRetriever to perform
    symptom and keyword overlap matching over curated operational runbooks.
    """

    def __init__(self) -> None:
        self.documents: dict[str, KnowledgeDocument] = {}
        self.langchain_docs: list[Any] = []
        self._langchain_available = LANGCHAIN_AVAILABLE
        self._retrieval_mode = "langchain_deterministic_keyword_matching"
        self._retriever: LangChainRunbookRetriever | None = None

        # Seed initial knowledge
        for item in SAMPLE_RUNBOOKS:
            doc = KnowledgeDocument(
                doc_id=item["doc_id"],
                title=item["title"],
                category=item["category"],
                service=item["service"],
                content=item["content"],
                resolution_steps=item["resolution_steps"],
                metadata=item.get("metadata", {}),
            )
            self.documents[doc.doc_id] = doc

        self._sync_retriever()

    def _sync_retriever(self) -> None:
        """Rebuild LangChain Documents and refresh the LangChain BaseRetriever."""
        if not self._langchain_available or LCDocument is None:
            self._retriever = None
            return
        self.langchain_docs = [
            doc.to_langchain_document()
            for doc in self.documents.values()
            if doc.to_langchain_document() is not None
        ]
        self._retriever = LangChainRunbookRetriever(
            documents=self.langchain_docs,
            default_top_k=2,
        )

    @property
    def retriever(self) -> LangChainRunbookRetriever | None:
        """Direct access to the underlying LangChain BaseRetriever."""
        if self._retriever is None and self._langchain_available:
            self._sync_retriever()
        return self._retriever

    def get_status(self) -> dict[str, Any]:
        """Return operational status of the runbook retrieval engine."""
        return {
            "langchain_available": self._langchain_available,
            "retriever_class": "LangChainRunbookRetriever" if self._retriever else "none",
            "framework": "LangChain",
            "retrieval_mode": self._retrieval_mode,
            "embeddings_enabled": False,
            "vector_store": "none (in-memory LangChain Document catalog)",
            "total_documents": len(self.documents),
            "total_langchain_documents": len(self.langchain_docs),
            "engine_ready": True,
        }

    def ingest_document(self, doc: KnowledgeDocument) -> None:
        self.documents[doc.doc_id] = doc
        self._sync_retriever()

    def query(
        self,
        query_text: str,
        service: str | None = None,
        top_k: int = 2,
    ) -> dict[str, Any]:
        """
        Retrieve relevant runbooks matching an operational incident query
        via the LangChain BaseRetriever.
        """
        effective_query = f"{query_text} service:{service}" if service else query_text

        # Invoke the LangChain retriever via LangChain's Runnable interface
        if self._langchain_available and self.retriever is not None:
            self.retriever.default_top_k = top_k
            lc_results = self.retriever.invoke(effective_query)
        else:
            lc_results = []

        results = []
        for d in lc_results[:top_k]:
            results.append({
                "doc_id": d.metadata.get("doc_id", ""),
                "title": d.metadata.get("title", ""),
                "category": d.metadata.get("category", ""),
                "service": d.metadata.get("service", ""),
                "score": d.metadata.get("score", 0.0),
                "resolution_steps": d.metadata.get("resolution_steps", ""),
                "summary": d.page_content[:150] + ("..." if len(d.page_content) > 150 else ""),
            })

        if results:
            recommendation = (
                f"Matched {len(results)} relevant runbook(s). "
                f"Top recommendation from '{results[0]['title']}': {results[0]['resolution_steps']}"
            )
        else:
            recommendation = "No high-confidence runbook match found. Follow standard triage and escalate if unresolved."

        return {
            "query": query_text,
            "service_filter": service,
            "matches_count": len(results),
            "matches": results,
            "recommendation": recommendation,
        }


knowledge_retriever = IncidentKnowledgeRetriever()