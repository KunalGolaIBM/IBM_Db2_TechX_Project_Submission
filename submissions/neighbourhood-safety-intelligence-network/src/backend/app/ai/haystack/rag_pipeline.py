"""Hybrid retrieval of approved safety protocols with Haystack 2 and IBM Db2.

Indexing pipeline (Db2 mode)
    DocumentSplitter -> FastembedDocumentEmbedder -> DocumentWriter(IBMDb2DocumentStore)
Query pipeline (Db2 mode)
    FastembedTextEmbedder -> IBMDb2EmbeddingRetriever --\
    InMemoryBM25Retriever --------------------------------> DocumentJoiner(reciprocal_rank_fusion)

* IBMDb2DocumentStore / IBMDb2EmbeddingRetriever come from IBM's `ibm-db-haystack` package: passages
  live in Db2 with a VECTOR column, metadata is stored as BSON and filtered with JSON_VALUE.
* The same Haystack metadata filters (category, audience) are applied to both retrievers.
* Passages are retrieved, then grouped back to their protocol, so every answer cites the exact
  passage that matched.
* Without Db2 (SQLite tests, local development) the BM25 branch runs on its own.
"""
import logging
import os
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional

# Privacy: never send Haystack usage telemetry from a deployment that handles resident data.
os.environ.setdefault("HAYSTACK_TELEMETRY_ENABLED", "False")

from haystack import Document, Pipeline  # noqa: E402
from haystack.components.joiners import DocumentJoiner  # noqa: E402
from haystack.components.preprocessors import DocumentSplitter  # noqa: E402
from haystack.components.retrievers.in_memory import InMemoryBM25Retriever  # noqa: E402
from haystack.components.writers import DocumentWriter  # noqa: E402
from haystack.document_stores.in_memory import InMemoryDocumentStore  # noqa: E402
from haystack.document_stores.types import DuplicatePolicy  # noqa: E402

from backend.app.ai.haystack.documents import APPROVED_CIVIC_SAFETY_DOCUMENTS  # noqa: E402
from backend.app.core.config import settings  # noqa: E402

logger = logging.getLogger("neighbourhood_safety.haystack")

PASSAGE_TABLE = "NSIN_PROTOCOL_PASSAGES"
# Calibrated with bge-small on the protocol passages: on-topic questions put the right passage first
# with a clear margin over the runner-up; off-topic questions produce near-ties at larger distances.
STRONG_MATCH = 0.40
MAX_DISTANCE = 0.48
MIN_MARGIN = 0.012  # measured: relevant top-2 gaps >= 0.016, off-topic gaps <= 0.007

# Who each protocol is written for (metadata used by audience filters).
PROTOCOL_AUDIENCE = {
    "emergency_response": ["residents", "responders"],
    "child_safety": ["guardians", "responders"],
    "elder_care": ["seniors", "caregivers", "responders"],
    "hazard_mitigation": ["residents", "responders"],
    "transit_safety": ["women", "residents"],
    "responder_procedures": ["responders"],
}
# Triage category -> protocol category, used as a soft ranking prior.
INCIDENT_TO_PROTOCOL_CATEGORY = {
    "sos": "emergency_response",
    "medical": "emergency_response",
    "child_alert": "child_safety",
    "elder_welfare": "elder_care",
    "hazard": "hazard_mitigation",
    "suspicious_activity": "transit_safety",
}
CATEGORY_PRIOR_VOTES = 0.5  # worth half of a first-place vote in the fused ranking

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "from",
    "up", "about", "into", "over", "after", "is", "are", "was", "were", "be", "been", "being", "have",
    "has", "had", "do", "does", "did", "what", "how", "should", "when", "where", "who", "which", "can",
    "my", "i",
}


def _keywords(text: str) -> set:
    return {w for w in re.findall(r"\b[a-zA-Z0-9_-]{2,}\b", text.lower()) if w not in _STOPWORDS}


def build_filters(category: Optional[str] = None, audience: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Haystack metadata filter understood by both the in-memory store and IBMDb2DocumentStore."""
    conditions = []
    if category:
        conditions.append({"field": "meta.category", "operator": "==", "value": category})
    if audience:
        conditions.append({"field": "meta.audience", "operator": "==", "value": audience})
    if not conditions:
        return None
    return conditions[0] if len(conditions) == 1 else {"operator": "AND", "conditions": conditions}


def protocol_documents() -> List[Document]:
    """One Haystack Document per protocol. Audience is stored per passage (one value each) so that
    equality filters work the same way in the in-memory store and in Db2's JSON_VALUE."""
    return [
        Document(
            id=d["id"],
            content=f"{d['title']}. {d['content']}",
            meta={"protocol_id": d["id"], "title": d["title"], "category": d["category"],
                  "source": d["source"], "updated_at": d["updated_at"]},
        )
        for d in APPROVED_CIVIC_SAFETY_DOCUMENTS
    ]


def split_into_passages(docs: List[Document]) -> List[Document]:
    splitter = DocumentSplitter(split_by="word", split_length=60, split_overlap=12)
    passages = splitter.run(documents=docs)["documents"]
    expanded = []
    for i, p in enumerate(passages):
        for audience in PROTOCOL_AUDIENCE.get(p.meta["category"], ["residents"]):
            expanded.append(Document(id=f"{p.meta['protocol_id']}-{i:03d}-{audience}", content=p.content,
                                     meta={**p.meta, "audience": audience, "passage": i}))
    return expanded


class SafetyProtocolRetriever:
    def __init__(self) -> None:
        self.protocols = {d["id"]: d for d in APPROVED_CIVIC_SAFETY_DOCUMENTS}
        self.passages = split_into_passages(protocol_documents())
        self.memory_store = InMemoryDocumentStore(bm25_algorithm="BM25Okapi")
        self.memory_store.write_documents(self.passages)
        self.bm25_pipeline = Pipeline()
        self.bm25_pipeline.add_component("bm25", InMemoryBM25Retriever(document_store=self.memory_store, top_k=12))
        self.hybrid_pipeline: Optional[Pipeline] = None
        # Reciprocal rank fusion of the (gated) keyword and vector rankings.
        self.joiner = DocumentJoiner(join_mode="reciprocal_rank_fusion")
        self.db2_store = None
        self.error: Optional[str] = None
        logger.info("Haystack BM25 store indexed %d passages from %d protocols.",
                    len(self.passages), len(self.protocols))

    # ---- Db2 dense branch ---------------------------------------------------------------------
    @property
    def hybrid(self) -> bool:
        return self.hybrid_pipeline is not None

    def enable_db2(self) -> None:
        """Index passages into IBM Db2 and build the hybrid pipeline. Never raises: on failure
        the service keeps answering with BM25 alone and reports why in /health."""
        if not settings.ENABLE_VECTOR_SEARCH:
            self.error = "disabled by ENABLE_VECTOR_SEARCH"
            return
        try:
            from haystack.utils import Secret
            from haystack_integrations.components.embedders.fastembed import (
                FastembedDocumentEmbedder, FastembedTextEmbedder,
            )
            from haystack_integrations.components.retrievers.ibm_db import IBMDb2EmbeddingRetriever
            from haystack_integrations.document_stores.ibm_db import IBMDb2DocumentStore

            embed_kwargs = {"model": settings.EMBEDDING_MODEL}
            if settings.EMBEDDING_CACHE_DIR:
                embed_kwargs["cache_dir"] = settings.EMBEDDING_CACHE_DIR

            self.db2_store = IBMDb2DocumentStore(
                database=settings.DB2_DATABASE, hostname=settings.DB2_HOST, port=settings.DB2_PORT,
                username=Secret.from_token(settings.DB2_USER), password=Secret.from_token(settings.DB2_PASSWORD),
                schema=settings.DB2_SCHEMA or None, use_ssl=(settings.DB2_SECURITY or "").upper() == "SSL",
                table_name=PASSAGE_TABLE, embedding_dim=settings.EMBEDDING_DIM, distance_metric="COSINE",
            )
            indexing = Pipeline()
            indexing.add_component("embedder", FastembedDocumentEmbedder(**embed_kwargs, meta_fields_to_embed=["title"], progress_bar=False))
            indexing.add_component("writer", DocumentWriter(document_store=self.db2_store, policy=DuplicatePolicy.OVERWRITE))
            indexing.connect("embedder.documents", "writer.documents")
            indexing.run({"embedder": {"documents": self.passages}})

            hybrid = Pipeline()
            hybrid.add_component("text_embedder", FastembedTextEmbedder(**embed_kwargs, progress_bar=False))
            hybrid.add_component("db2_retriever", IBMDb2EmbeddingRetriever(document_store=self.db2_store, top_k=12))
            hybrid.add_component("bm25_retriever", InMemoryBM25Retriever(document_store=self.memory_store, top_k=12))
            hybrid.connect("text_embedder.embedding", "db2_retriever.query_embedding")
            self.hybrid_pipeline = hybrid
            self.error = None
            logger.info("Hybrid retrieval enabled: %d passages indexed in Db2 table %s.", len(self.passages), PASSAGE_TABLE)
        except Exception as exc:  # pragma: no cover - depends on the environment
            self.hybrid_pipeline = None
            self.error = str(exc)[:300]
            logger.warning("Db2 hybrid retrieval unavailable, using BM25 only: %s", exc)

    # ---- query --------------------------------------------------------------------------------
    def _run(self, query: str, filters: Optional[Dict[str, Any]]):
        if self.hybrid:
            out = self.hybrid_pipeline.run(
                {"text_embedder": {"text": query}, "db2_retriever": {"filters": filters},
                 "bm25_retriever": {"query": query, "filters": filters}},
            )
            return out["bm25_retriever"]["documents"], out["db2_retriever"]["documents"]
        out = self.bm25_pipeline.run({"bm25": {"query": query, "filters": filters}})
        return out["bm25"]["documents"], []

    @staticmethod
    def _best_per_protocol(docs: List[Document]) -> List[Document]:
        seen, best = set(), []
        for d in docs:
            if d.meta["protocol_id"] not in seen:
                seen.add(d.meta["protocol_id"])
                best.append(d)
        return best

    def query(self, query_text: str, category: Optional[str] = None, audience: Optional[str] = None,
              top_k: int = 3, prefer_category: Optional[str] = None) -> Dict[str, Any]:
        mode = "hybrid (Haystack BM25 + IBM Db2 vector)" if self.hybrid else "Haystack BM25"
        q_terms = _keywords(query_text)
        if not q_terms:
            return {"results": [], "found": False, "retrieval_mode": mode,
                    "message": "Query was empty or contained no searchable keywords."}

        filters = build_filters(category, audience)
        bm25_docs, dense_docs = self._run(query_text, filters)

        # Keyword branch: keep passages that share real words with the query.
        bm25_hits = self._best_per_protocol([d for d in bm25_docs if q_terms & _keywords(d.content or "")])
        # Dense branch: Db2 returns cosine distance (lower is closer); gate on distance and margin.
        dense_hits = self._best_per_protocol(sorted(dense_docs, key=lambda d: d.score))
        if dense_hits:
            best = dense_hits[0].score
            margin = dense_hits[1].score - best if len(dense_hits) > 1 else 1.0
            if not (best <= STRONG_MATCH or (best <= MAX_DISTANCE and margin >= MIN_MARGIN)):
                dense_hits = []
            dense_hits = [d for d in dense_hits if d.score <= best + MIN_MARGIN]

        # Collapse each branch to one document per protocol (id = protocol id) and fuse with Haystack's
        # DocumentJoiner (RRF); then add the soft category prior from triage.
        def as_protocol_docs(hits: List[Document]) -> List[Document]:
            return [Document(id=d.meta["protocol_id"], content=d.content, meta=d.meta, score=d.score) for d in hits]

        passage: Dict[str, Document] = {}
        matched: Dict[str, List[str]] = defaultdict(list)
        distances: Dict[str, float] = {}
        for label, hits in (("bm25", bm25_hits), ("vector", dense_hits)):
            for d in hits:
                pid = d.meta["protocol_id"]
                matched[pid].append(label)
                passage.setdefault(pid, d)
                if label == "vector":
                    distances[pid] = float(d.score)
        ranked_lists = [as_protocol_docs(h) for h in (bm25_hits, dense_hits) if h]
        joined = self.joiner.run(documents=ranked_lists)["documents"] if ranked_lists else []
        fused: Dict[str, float] = {d.id: float(d.score or 0.0) for d in joined}
        if prefer_category and ranked_lists:
            # DocumentJoiner normalises RRF so a first-place vote is worth 1/len(lists); the prior is half of that.
            prior = CATEGORY_PRIOR_VOTES / len(ranked_lists)
            for pid in fused:
                if self.protocols[pid]["category"] == prefer_category:
                    fused[pid] += prior

        if not fused:
            return {"results": [], "found": False, "retrieval_mode": mode, "query": query_text,
                    "filters": filters,
                    "message": "No approved safety protocol matched the query. Please consult on-duty responders."}

        results = []
        for pid in sorted(fused, key=fused.get, reverse=True)[:top_k]:
            proto = self.protocols[pid]
            results.append({
                "document_id": pid,
                "title": proto["title"],
                "category": proto["category"],
                "audience": PROTOCOL_AUDIENCE.get(proto["category"], []),
                "excerpt": proto["content"],
                "cited_passage": passage[pid].content,
                "source": proto["source"],
                "updated_at": proto["updated_at"],
                "relevance_score": round(fused[pid], 4),
                "matched_by": "+".join(matched[pid]),
                "vector_distance": round(distances[pid], 4) if pid in distances else None,
            })
        return {"results": results, "found": True, "count": len(results), "retrieval_mode": mode,
                "filters": filters, "top_source": results[0]["source"], "query": query_text}

    def status(self) -> Dict[str, Any]:
        return {"hybrid": self.hybrid, "passages": len(self.passages), "db2_table": PASSAGE_TABLE if self.hybrid else None,
                "reason": None if self.hybrid else (self.error or "requires DATABASE_MODE=db2")}


protocol_retriever = SafetyProtocolRetriever()


def retrieve_safety_guidance(query: str, category: Optional[str] = None, incident_type: Optional[str] = None,
                             audience: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve cited protocols. ``category``/``audience`` are hard metadata filters;
    ``incident_type`` (from triage) is a soft ranking prior."""
    return protocol_retriever.query(query_text=query, category=category, audience=audience,
                                    prefer_category=INCIDENT_TO_PROTOCOL_CATEGORY.get(incident_type or ""))
