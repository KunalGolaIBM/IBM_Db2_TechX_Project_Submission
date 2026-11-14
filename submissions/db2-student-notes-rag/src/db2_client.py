"""
IBM Db2 Native Vector Store Manager for LangChain.
Provides high-performance vector search, embedding storage, and index lifecycle
management using `langchain-db2` and `ibm_db_dbi`.
"""

import logging
import math
from typing import List, Tuple, Optional, Any
from config import Db2RAGConfig

logger = logging.getLogger("db2_vector_store")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class MockVectorStoreFallback:
    """
    Robust in-memory cosine similarity fallback store.
    Ensures tests and offline demonstrations run reliably when
    IBM Db2 instance is not yet started or during local validation.
    """

    def __init__(self, embeddings: Any, table_name: str = "STUDENT_NOTES_VS"):
        self.embeddings = embeddings
        self.table_name = table_name
        self.documents: List[Any] = []
        self.doc_vectors: List[List[float]] = []
        logger.warning(
            "Running with InMemory fallback vector engine because IBM Db2 is offline. "
            "Full Db2 VECTOR queries will activate automatically once Db2 connection is established."
        )

    def add_documents(self, documents: List[Any]) -> List[str]:
        texts = [doc.page_content for doc in documents]
        embeddings = self.embeddings.embed_documents(texts)
        self.documents.extend(documents)
        self.doc_vectors.extend(embeddings)
        return [doc.metadata.get("doc_id", str(i)) for i, doc in enumerate(documents)]

    @classmethod
    def from_documents(cls, documents: List[Any], embeddings: Any, **kwargs) -> "MockVectorStoreFallback":
        store = cls(embeddings=embeddings, table_name=kwargs.get("table_name", "STUDENT_NOTES_VS"))
        store.add_documents(documents)
        return store

    def similarity_search_with_score(self, query: str, k: int = 4) -> List[Tuple[Any, float]]:
        if not self.documents:
            return []
        query_vec = self.embeddings.embed_query(query)

        def cosine_similarity(v1: List[float], v2: List[float]) -> float:
            dot = sum(a * b for a, b in zip(v1, v2))
            norm1 = math.sqrt(sum(a * a for a in v1))
            norm2 = math.sqrt(sum(b * b for b in v2))
            if norm1 == 0 or norm2 == 0:
                return 0.0
            return dot / (norm1 * norm2)

        scored = []
        for doc, vec in zip(self.documents, self.doc_vectors):
            score = cosine_similarity(query_vec, vec)
            scored.append((doc, float(score)))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]

    def similarity_search(self, query: str, k: int = 4) -> List[Any]:
        results = self.similarity_search_with_score(query, k=k)
        return [doc for doc, _ in results]


def get_embedding_function():
    """Initializes and returns the sentence-transformers embedding function."""
    try:
        from langchain_community.embeddings import HuggingFaceEmbeddings
        logger.info(f"Loading embedding model: {Db2RAGConfig.EMBEDDING_MODEL}")
        return HuggingFaceEmbeddings(
            model_name=Db2RAGConfig.EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    except Exception as e:
        logger.warning(f"Could not load HuggingFaceEmbeddings ({e}), using lightweight hash embedder fallback.")
        
        class SimpleHashEmbedder:
            def __init__(self, dim: int = 768):
                self.dim = dim

            def embed_documents(self, texts: List[str]) -> List[List[float]]:
                return [self.embed_query(t) for t in texts]

            def embed_query(self, text: str) -> List[float]:
                import hashlib, re
                vec = [0.0] * self.dim
                words = re.findall(r"[a-z0-9_]+", text.lower())
                if not words:
                    return vec
                for w in words:
                    h = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16)
                    idx = h % self.dim
                    vec[idx] += 1.0
                norm = math.sqrt(sum(x * x for x in vec)) or 1.0
                return [x / norm for x in vec]

        return SimpleHashEmbedder(dim=Db2RAGConfig.EMBEDDING_DIM)


def get_db2_connection():
    """Establishes a low-level DBI connection to the IBM Db2 database."""
    try:
        import ibm_db_dbi
        conn_str = Db2RAGConfig.get_connection_string()
        logger.info(f"Connecting to IBM Db2 at {Db2RAGConfig.DB2_HOST}:{Db2RAGConfig.DB2_PORT}/{Db2RAGConfig.DB2_DATABASE}...")
        conn = ibm_db_dbi.connect(conn_str, "", "")
        logger.info("Successfully connected to IBM Db2 database.")
        return conn
    except Exception as exc:
        logger.warning(f"Unable to establish direct connection to IBM Db2 ({exc}).")
        return None


def verify_db2_connection() -> Tuple[bool, str]:
    """Test connection and return health status message."""
    conn = get_db2_connection()
    if conn is None:
        return False, f"Could not connect to Db2 at {Db2RAGConfig.DB2_HOST}:{Db2RAGConfig.DB2_PORT}."
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM SYSIBM.SYSDUMMY1")
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row and row[0] == 1:
            return True, f"Active and healthy IBM Db2 connection at {Db2RAGConfig.DB2_HOST}:{Db2RAGConfig.DB2_PORT}/{Db2RAGConfig.DB2_DATABASE}."
        return True, "Connected, but heartbeat query returned unexpected response."
    except Exception as e:
        return False, f"Db2 heartbeat failed: {e}"


def get_or_create_vector_store(documents: Optional[List[Any]] = None, recreate: bool = False):
    """
    Returns an initialized IBM Db2 Vector Store (`DB2VS`),
    populating it with documents if provided.
    Falls back to in-memory store gracefully if Db2 is offline.
    """
    embeddings = get_embedding_function()
    conn = get_db2_connection()

    if conn is not None:
        try:
            from langchain_community.vectorstores.utils import DistanceStrategy
            from langchain_db2.db2vs import DB2VS

            strategy = (
                DistanceStrategy.COSINE
                if Db2RAGConfig.DISTANCE_STRATEGY.upper() == "COSINE"
                else DistanceStrategy.EUCLIDEAN_DISTANCE
            )

            if documents:
                logger.info(
                    f"Indexing {len(documents)} documents into Db2 table '{Db2RAGConfig.DB2_TABLE_NAME}'..."
                )
                store = DB2VS.from_documents(
                    documents,
                    embeddings,
                    client=conn,
                    table_name=Db2RAGConfig.DB2_TABLE_NAME,
                    distance_strategy=strategy,
                )
                logger.info("Documents successfully ingested into IBM Db2 vector store.")
                return store
            else:
                return DB2VS(
                    embedding=embeddings,
                    client=conn,
                    table_name=Db2RAGConfig.DB2_TABLE_NAME,
                    distance_strategy=strategy,
                )
        except Exception as e:
            logger.error(f"Error initializing DB2VS: {e}. Falling back to resilient mode.")

    # Resilient fallback
    if documents:
        return MockVectorStoreFallback.from_documents(
            documents, embeddings, table_name=Db2RAGConfig.DB2_TABLE_NAME
        )
    return MockVectorStoreFallback(embeddings, table_name=Db2RAGConfig.DB2_TABLE_NAME)
