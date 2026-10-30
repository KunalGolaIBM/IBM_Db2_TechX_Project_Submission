"""
Custom Hybrid RRF (Reciprocal Rank Fusion) Retriever for LlamaIndex.
Combines:
1. Native IBM Db2 Vector Store Search (via DB2LlamaVS)
2. Lexical Sparse Search (TF-IDF / Exact Keyword Match)
Using Reciprocal Rank Fusion (RRF) with standard constant k=60.
"""
from typing import List, Dict, Any
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

try:
    from fastembed import TextEmbedding
    HAS_FASTEMBED = True
except ImportError:
    HAS_FASTEMBED = False
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        pass

from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore, TextNode
from llama_index.core.vector_stores.types import VectorStoreQuery

from src.vector_store import BakeboxDb2VectorStore

class Db2HybridRRFRetriever(BaseRetriever):
    """
    LlamaIndex BaseRetriever implementation that fuses native IBM Db2 vector search
    with lexical keyword matching for high-precision bakery & catalog retrieval.
    """
    def __init__(
        self,
        vector_store: BakeboxDb2VectorStore,
        corpus_nodes: List[TextNode],
        model_name: str = "BAAI/bge-small-en-v1.5",
        rrf_k: int = 60
    ):
        super().__init__()
        self.vector_store = vector_store
        self.rrf_k = rrf_k
        self.nodes_dict = {n.id_: n for n in corpus_nodes}
        
        # Load embedding model for query embedding
        print(f"Loading embedding model '{model_name}' for query vectorization...")
        if HAS_FASTEMBED:
            self.fast_model = TextEmbedding(model_name=model_name)
            self.embed_func = lambda q: list(self.fast_model.embed([q]))[0].tolist()
        else:
            from sentence_transformers import SentenceTransformer
            self.st_model = SentenceTransformer(model_name)
            self.embed_func = lambda q: self.st_model.encode(q).tolist()

        # Build Lexical TF-IDF index across corpus
        self.corpus_ids = [n.id_ for n in corpus_nodes]
        self.corpus_texts = [n.text for n in corpus_nodes]
        self.tfidf = TfidfVectorizer(stop_words='english', max_features=5000)
        if self.corpus_texts:
            self.tfidf_matrix = self.tfidf.fit_transform(self.corpus_texts)
        else:
            self.tfidf_matrix = None

    def _retrieve(self, query_bundle) -> List[NodeWithScore]:
        query_str = query_bundle.query_str
        return self.hybrid_retrieve(query_str, top_k=5)

    def hybrid_retrieve(self, query: str, top_k: int = 5) -> List[NodeWithScore]:
        """
        Executes dense search in IBM Db2 + sparse lexical search,
        then fuses results using RRF: score = sum(1 / (k + rank)).
        """
        # 1. Dense Semantic Search via IBM Db2 DB2LlamaVS
        q_emb = self.embed_func(query)
        dense_res = self.vector_store.query(query_embedding=q_emb, top_k=top_k * 3)
        dense_ranked_ids = dense_res.ids or []

        # 2. Sparse Lexical Search
        sparse_ranked_ids = []
        if self.tfidf_matrix is not None:
            q_vec = self.tfidf.transform([query])
            sims = (self.tfidf_matrix * q_vec.T).toarray().flatten()
            top_sparse_idx = np.argsort(sims)[::-1][:top_k * 3]
            sparse_ranked_ids = [self.corpus_ids[i] for i in top_sparse_idx if sims[i] > 0.0]

        # 3. Reciprocal Rank Fusion (RRF)
        rrf_scores: Dict[str, float] = {}

        # Dense ranking contribution
        for rank, doc_id in enumerate(dense_ranked_ids):
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + (1.0 / (self.rrf_k + rank + 1))

        # Sparse ranking contribution
        for rank, doc_id in enumerate(sparse_ranked_ids):
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + (1.0 / (self.rrf_k + rank + 1))

        # Sort documents by fused RRF score
        sorted_candidates = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        # Construct NodeWithScore objects
        results: List[NodeWithScore] = []
        for doc_id, score in sorted_candidates:
            node = self.nodes_dict.get(doc_id)
            if node:
                results.append(NodeWithScore(node=node, score=score))

        return results
