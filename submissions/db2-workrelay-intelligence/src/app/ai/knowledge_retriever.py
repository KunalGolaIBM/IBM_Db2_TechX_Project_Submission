from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

from app.ai.sample_runbooks import SAMPLE_RUNBOOKS

logger = logging.getLogger("ai_knowledge_retriever")

try:
    from llama_index.core import Document
    LLAMA_INDEX_AVAILABLE = True
except ImportError:
    Document = None
    LLAMA_INDEX_AVAILABLE = False


@dataclass
class KnowledgeDocument:
    doc_id: str
    title: str
    category: str
    service: str
    content: str
    resolution_steps: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_llama_document(self) -> Any:
        if not LLAMA_INDEX_AVAILABLE or Document is None:
            return None
        text = f"{self.title}\nService: {self.service}\nCategory: {self.category}\n{self.content}\nResolution: {self.resolution_steps}"
        return Document(text=text, doc_id=self.doc_id, extra_info=self.metadata)


class IncidentKnowledgeRetriever:
    """
    Operational knowledge retrieval engine.
    Provides deterministic symptom and keyword overlap matching over
    curated operational runbooks and historical incident post-mortems.
    """

    def __init__(self) -> None:
        self.documents: dict[str, KnowledgeDocument] = {}
        self._llama_available = LLAMA_INDEX_AVAILABLE
        self._retrieval_mode = "deterministic_keyword_matching"

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
            self.ingest_document(doc)

    def get_status(self) -> dict[str, Any]:
        """Return operational status of the runbook retrieval engine."""
        return {
            "llama_index_available": self._llama_available,
            "retrieval_mode": self._retrieval_mode,
            "embeddings_enabled": False,
            "vector_store": "none (in-memory runbook catalog)",
            "total_documents": len(self.documents),
            "engine_ready": True,
        }

    def ingest_document(self, doc: KnowledgeDocument) -> None:
        self.documents[doc.doc_id] = doc

    def query(
        self,
        query_text: str,
        service: str | None = None,
        top_k: int = 2,
    ) -> dict[str, Any]:
        """
        Retrieve relevant runbooks matching an operational incident query
        via token overlap and service context scoring.
        """
        terms = set(re.findall(r"\w+", query_text.lower()))

        scored_docs: list[tuple[float, KnowledgeDocument]] = []
        for doc in self.documents.values():
            if service and service.lower() != "all" and service.lower() != doc.service.lower():
                if not (service.lower().startswith("db") and doc.service.lower() == "database"):
                    continue

            doc_text = f"{doc.title} {doc.content} {doc.resolution_steps} {doc.service}".lower()
            doc_terms = set(re.findall(r"\w+", doc_text))

            overlap = len(terms.intersection(doc_terms))
            score = overlap / max(len(terms), 1)

            if service and service.lower() == doc.service.lower():
                score += 0.3

            if score > 0:
                scored_docs.append((score, doc))

        scored_docs.sort(key=lambda x: x[0], reverse=True)
        top_matches = scored_docs[:top_k]

        results = []
        for score, d in top_matches:
            results.append({
                "doc_id": d.doc_id,
                "title": d.title,
                "category": d.category,
                "service": d.service,
                "score": round(score, 3),
                "resolution_steps": d.resolution_steps,
                "summary": d.content[:150] + ("..." if len(d.content) > 150 else ""),
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
