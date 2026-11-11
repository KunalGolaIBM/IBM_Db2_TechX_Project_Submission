"""
Advanced 3-Way Hybrid RRF & Corrective RAG (CRAG) Retriever for IBM Db2.

Fuses three retrieval channels with Reciprocal Rank Fusion (RRF: k=60):
1. Native IBM Db2 Vector Search (`DB2LlamaVS` COSINE distance + BSON metadata pushdown)
2. Sparse Lexical Ranking A: Okapi BM25 (`k1=1.5, b=0.75`)
3. Sparse Lexical Ranking B: Scikit-Learn TF-IDF Cosine Matrix

Includes Hinglish -> English Corrective RAG (CRAG) query expansion and a
singleton cached 384-d embedding factory for fast, network-resilient execution.
"""
import hashlib
import math
import os
import re
import threading
from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
except ImportError:
    TfidfVectorizer = None

try:
    from fastembed import TextEmbedding
    HAS_FASTEMBED = True
except ImportError:
    TextEmbedding = None
    HAS_FASTEMBED = False

try:
    from llama_index.core.retrievers import BaseRetriever
    from llama_index.core.schema import NodeWithScore, TextNode
except ImportError:
    class BaseRetriever:
        def retrieve(self, str_or_bundle):
            return self._retrieve(str_or_bundle)

    class TextNode:
        def __init__(self, text: str = "", id_: Optional[str] = None, metadata: Optional[dict] = None, embedding: Optional[List[float]] = None):
            self.text = text
            self.id_ = id_ or str(hash(text))
            self.metadata = metadata or {}
            self.embedding = embedding

    class NodeWithScore:
        def __init__(self, node: Any = None, score: float = 0.0):
            self.node = node
            self.score = score

from src.vector_store import BakeboxDb2VectorStore, _matches_metadata_filters

_EMBED_CACHE: Dict[str, Callable[[str], List[float]]] = {}
_EMBED_CACHE_LOCK = threading.Lock()


def _semantic_hash_embed(text: str, dim: int = 384) -> List[float]:
    """
    Deterministic L2-normalized 384-dim n-gram feature-hash vector fallback.
    Produces meaningful token & char-trigram overlap cosines with zero network I/O.
    """
    vec = np.zeros(dim, dtype=np.float32)
    clean = (text or "").lower()
    tokens = re.findall(r"[a-z0-9]+", clean)
    features = list(tokens) + [f"{tokens[i]}_{tokens[i+1]}" for i in range(len(tokens) - 1)]
    for tok in tokens:
        if len(tok) >= 3:
            features.extend(tok[i:i+3] for i in range(len(tok) - 2))

    counts = Counter(features)
    for feat, tf in counts.items():
        digest = int(hashlib.blake2b(feat.encode("utf-8"), digest_size=8).hexdigest(), 16)
        bucket = digest % dim
        sign = 1.0 if ((digest >> 16) & 1) == 0 else -1.0
        vec[bucket] += sign * (1.0 + math.log(tf))

    norm = float(np.linalg.norm(vec))
    if norm > 0.0:
        vec /= norm
    else:
        vec[0] = 1.0
    return vec.tolist()


def get_shared_embedding_fn(model_name: str = "BAAI/bge-small-en-v1.5") -> Callable[[str], List[float]]:
    """
    Return a thread-safe cached 384-d embedding callable.
    Avoids repeated ONNX reloads across tests/requests and degrades cleanly if offline.
    """
    force_offline = os.getenv("BAKEBOX_OFFLINE_EMBED", "false").lower() in ("true", "1", "yes")
    cache_key = f"{model_name}::{'offline' if force_offline else 'auto'}"

    with _EMBED_CACHE_LOCK:
        if cache_key in _EMBED_CACHE:
            return _EMBED_CACHE[cache_key]

        embed_fn: Optional[Callable[[str], List[float]]] = None
        if not force_offline and HAS_FASTEMBED and TextEmbedding is not None:
            try:
                fast_model = TextEmbedding(model_name=model_name)
                embed_fn = lambda q, _m=fast_model: list(_m.embed([q]))[0].tolist()
            except Exception:
                embed_fn = None

        if embed_fn is None and not force_offline:
            try:
                from sentence_transformers import SentenceTransformer
                st_model = SentenceTransformer(model_name)
                embed_fn = lambda q, _m=st_model: _m.encode(q).tolist()
            except Exception:
                embed_fn = None

        if embed_fn is None:
            embed_fn = lambda q: _semantic_hash_embed(q, dim=384)

        _EMBED_CACHE[cache_key] = embed_fn
        return embed_fn


def compute_rrf_score(ranks: List[Optional[int]], k: int = 60) -> float:
    """
    Compute Reciprocal Rank Fusion (RRF) score over arbitrary 0-based channel ranks:
      RRF(d) = sum(1 / (k + rank + 1)) for each channel where d appears.
    """
    score = 0.0
    for r in ranks:
        if r is not None and r >= 0:
            score += 1.0 / (k + r + 1)
    return score


class SimpleBM25:
    """Okapi BM25 lexical ranker with precomputed term frequencies and RSJ IDF."""
    def __init__(self, corpus_texts: List[str], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus_texts)
        self.tokenized_corpus = [self._tokenize(doc) for doc in corpus_texts]
        self.doc_counts = [Counter(doc) for doc in self.tokenized_corpus]
        self.doc_lengths = [len(doc) for doc in self.tokenized_corpus]
        self.avg_doc_len = sum(self.doc_lengths) / (self.corpus_size or 1)

        self.df: Dict[str, int] = {}
        for counts in self.doc_counts:
            for term in counts.keys():
                self.df[term] = self.df.get(term, 0) + 1

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"\b[a-z0-9]+(?:[._-][a-z0-9]+)*\b", text.lower())

    def score(self, query: str) -> List[float]:
        q_tokens = self._tokenize(query)
        scores = [0.0] * self.corpus_size
        for term in q_tokens:
            if term not in self.df:
                continue
            df_term = self.df[term]
            idf = math.log(1.0 + (self.corpus_size - df_term + 0.5) / (df_term + 0.5))
            for i, counts in enumerate(self.doc_counts):
                tf = counts.get(term, 0)
                if tf > 0:
                    denom = tf + self.k1 * (1.0 - self.b + self.b * (self.doc_lengths[i] / (self.avg_doc_len or 1)))
                    scores[i] += idf * (tf * (self.k1 + 1.0) / denom)
        return scores


class CorrectiveRAGEvaluator:
    """
    Corrective RAG (CRAG) Hinglish Query Expander & Retrieval Quality Grader.
    Translates vernacular Hinglish phrases into canonical Db2 catalog vocabulary
    only when ambiguity or cross-lingual phrasing is detected.
    """
    EXPANSION_RULES: List[Tuple[str, str]] = [
        (r"\bbina\s+ande\b|\bande\s+bina\b", "Pure Veg Khoaa Eggless"),
        (r"\baadha\s+kilo\b|\baadha\s+kg\b|\bhalf\s*kg\b", "0.5kg"),
        (r"\bek\s+kilo\b|\bek\s+kg\b|\bone\s*kg\b", "1.0kg"),
        (r"\bjanamdin\b|\bbday\b", "birthday celebration"),
        (r"\bsaal\s*girah\b|\bshadi\b", "anniversary heart red velvet"),
        (r"\bpetis\b", "patty puff pastry"),
        (r"\bgaram\b", "reheat dry tawa skillet never microwave"),
        (r"\bkitne\s+baje\b|\bkhulta\b", "store hours 8:00 AM 11:00 PM"),
        (r"\bkahan\b", "Khatoti Kua Holigate Gosna Mathura"),
        (r"\btoota\b", "Celebration Happiness Guarantee replacement"),
    ]

    def transform_query(self, query: str) -> str:
        """Expand vernacular Hinglish terms into catalog-aligned tokens cleanly."""
        q_lower = (query or "").lower()
        extras = []
        for pattern, expansion in self.EXPANSION_RULES:
            if re.search(pattern, q_lower):
                extras.append(expansion)
        return f"{query} {' '.join(extras)}".strip() if extras else query

    def evaluate_retrieval(self, query: str, nodes: List[NodeWithScore]) -> str:
        """Grade top fused RRF retrieval confidence (`CORRECT` / `AMBIGUOUS` / `INCORRECT`)."""
        if not nodes:
            return "INCORRECT"
        top_score = max((n.score or 0.0) for n in nodes)
        q_terms = set(re.findall(r"\b[a-z0-9]{3,}\b", query.lower()))
        has_overlap = any(
            any(term in (n.node.text or "").lower() for term in q_terms)
            for n in nodes[:3]
        )
        if top_score >= 0.035 and has_overlap:
            return "CORRECT"
        if top_score >= 0.015 or has_overlap:
            return "AMBIGUOUS"
        return "INCORRECT"


class Db2HybridRRFRetriever(BaseRetriever):
    """
    3-Way Hybrid RAG Retriever combining IBM Db2 Dense Cosine Vectors (with metadata
    pushdown), Okapi BM25, TF-IDF, Reciprocal Rank Fusion (k=60), and CRAG expansion.
    """
    def __init__(
        self,
        vector_store: Optional[BakeboxDb2VectorStore],
        corpus_nodes: Optional[List[TextNode]] = None,
        model_name: str = "BAAI/bge-small-en-v1.5",
        rrf_k: int = 60,
    ):
        super().__init__()
        self.vector_store = vector_store
        self.rrf_k = rrf_k
        self.crag = CorrectiveRAGEvaluator()
        self.embed_func = get_shared_embedding_fn(model_name)

        self.corpus_nodes: List[TextNode] = []
        self.nodes_dict: Dict[str, TextNode] = {}
        self.corpus_ids: List[str] = []
        self.corpus_texts: List[str] = []
        self.bm25: Optional[SimpleBM25] = None
        self.tfidf = None
        self.tfidf_matrix = None

        if corpus_nodes:
            self.refresh_index(corpus_nodes, sync_offline_store=True)

    def retrieve(self, query_bundle, filters: Optional[Any] = None) -> List[NodeWithScore]:
        """Public retrieve method compatible with LlamaIndex BaseRetriever contract."""
        query_str = getattr(query_bundle, "query_str", str(query_bundle))
        return self.hybrid_retrieve(query_str, top_k=5, filters=filters)

    def _retrieve(self, query_bundle) -> List[NodeWithScore]:
        return self.retrieve(query_bundle)

    def _run_rrf_pass(self, query: str, top_k: int, filters: Optional[Any]) -> List[NodeWithScore]:
        """Execute 3-channel ranking + RRF fusion for a single query string."""
        dense_ranked_ids: List[str] = []
        live_nodes_map: Dict[str, TextNode] = {}

        # Channel 1: Native Db2 Vector Store (or offline cosine mirror) with metadata pushdown
        if self.vector_store is not None:
            try:
                q_emb = self.embed_func(query)
                dense_res = self.vector_store.query(query_embedding=q_emb, top_k=top_k * 3, filters=filters)
                dense_ranked_ids = list(dense_res.ids or [])
                if dense_res.nodes:
                    for idx, n in enumerate(dense_res.nodes):
                        nid = dense_ranked_ids[idx] if idx < len(dense_ranked_ids) else n.id_
                        live_nodes_map[nid] = n
            except Exception as exc:
                print(f"[WARN] Db2 vector query failed ({exc}); continuing with lexical channels.")

        eligible_indices = [
            i for i, node in enumerate(self.corpus_nodes)
            if _matches_metadata_filters(getattr(node, "metadata", {}) or {}, filters)
        ]

        # Channel 2: Sparse Okapi BM25 restricted to filter-eligible corpus
        bm25_ranked_ids: List[str] = []
        if self.bm25 and self.corpus_texts and eligible_indices:
            bm25_scores = self.bm25.score(query)
            scored_bm25 = [(bm25_scores[i], self.corpus_ids[i]) for i in eligible_indices if bm25_scores[i] > 0.0]
            scored_bm25.sort(key=lambda x: x[0], reverse=True)
            bm25_ranked_ids = [doc_id for _, doc_id in scored_bm25[:top_k * 3]]

        # Channel 3: Sparse Scikit-Learn TF-IDF restricted to filter-eligible corpus
        tfidf_ranked_ids: List[str] = []
        if self.tfidf_matrix is not None and self.tfidf is not None and eligible_indices:
            try:
                q_vec = self.tfidf.transform([query])
                sims = (self.tfidf_matrix * q_vec.T).toarray().flatten()
                scored_tfidf = [(float(sims[i]), self.corpus_ids[i]) for i in eligible_indices if sims[i] > 0.0]
                scored_tfidf.sort(key=lambda x: x[0], reverse=True)
                tfidf_ranked_ids = [doc_id for _, doc_id in scored_tfidf[:top_k * 3]]
            except Exception:
                tfidf_ranked_ids = []

        all_candidates = set(dense_ranked_ids) | set(bm25_ranked_ids) | set(tfidf_ranked_ids)
        dense_rank = {doc_id: r for r, doc_id in enumerate(dense_ranked_ids)}
        bm25_rank = {doc_id: r for r, doc_id in enumerate(bm25_ranked_ids)}
        tfidf_rank = {doc_id: r for r, doc_id in enumerate(tfidf_ranked_ids)}

        rrf_scores = {
            doc_id: compute_rrf_score(
                [dense_rank.get(doc_id), bm25_rank.get(doc_id), tfidf_rank.get(doc_id)],
                k=self.rrf_k,
            )
            for doc_id in all_candidates
        }
        sorted_candidates = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        results: List[NodeWithScore] = []
        for doc_id, score in sorted_candidates:
            node = live_nodes_map.get(doc_id) or self.nodes_dict.get(doc_id)
            if node is not None:
                results.append(NodeWithScore(node=node, score=score))
        return results

    def hybrid_retrieve(self, query: str, top_k: int = 5, filters: Optional[Any] = None) -> List[NodeWithScore]:
        """
        Execute 3-Way Hybrid RRF retrieval on original query first, then apply
        Corrective RAG (CRAG) Hinglish expansion only if retrieval is ambiguous or
        vernacular expansion enriches missing domain tokens.
        """
        primary_results = self._run_rrf_pass(query, top_k=top_k, filters=filters)
        expanded_query = self.crag.transform_query(query)

        if expanded_query != query or self.crag.evaluate_retrieval(query, primary_results) != "CORRECT":
            if expanded_query != query:
                secondary = self._run_rrf_pass(expanded_query, top_k=top_k, filters=filters)
                merged = {n.node.id_: n for n in primary_results}
                for n in secondary:
                    nid = n.node.id_
                    boosted_score = (n.score or 0.0) * 0.9
                    if nid not in merged:
                        merged[nid] = NodeWithScore(node=n.node, score=boosted_score)
                    else:
                        merged[nid] = NodeWithScore(
                            node=merged[nid].node,
                            score=max(merged[nid].score or 0.0, boosted_score),
                        )
                primary_results = sorted(merged.values(), key=lambda x: x.score or 0.0, reverse=True)[:top_k]

        return primary_results

    def refresh_index(self, updated_nodes: List[TextNode], sync_offline_store: bool = True) -> None:
        """Synchronize lexical BM25/TF-IDF indexes and offline vector store cleanly."""
        self.corpus_nodes = list(updated_nodes)
        self.nodes_dict = {n.id_: n for n in updated_nodes}
        self.corpus_ids = [n.id_ for n in updated_nodes]
        self.corpus_texts = [n.text for n in updated_nodes]

        self.bm25 = SimpleBM25(self.corpus_texts) if self.corpus_texts else None
        if TfidfVectorizer is not None and self.corpus_texts:
            self.tfidf = TfidfVectorizer(stop_words="english", max_features=5000)
            self.tfidf_matrix = self.tfidf.fit_transform(self.corpus_texts)
        else:
            self.tfidf = None
            self.tfidf_matrix = None

        # Populate offline vector simulator so Dense Channel participates authentically
        if sync_offline_store and self.vector_store is not None and not self.vector_store.is_live_db2 and updated_nodes:
            for node in updated_nodes:
                if getattr(node, "embedding", None) is None:
                    node.embedding = self.embed_func(node.text)
            self.vector_store.add_nodes(updated_nodes)
