"""Ticket retrieval with Db2 VECTOR through the official langchain-db2 DB2VS store.
The store runs on the END USER's connection, so retrieval is subject to their Db2 grants."""
import os
from functools import lru_cache

from langchain_community.vectorstores.utils import DistanceStrategy
from langchain_core.embeddings import Embeddings
from langchain_db2 import DB2VS

TABLE = "BANK.TICKET_EMBEDDINGS"  # CHAR(16) id, CLOB text, BLOB metadata, VECTOR(384, FLOAT32)


class GraniteEmbeddings(Embeddings):
    """Local ibm-granite/granite-embedding-30m-english (384 dims) via sentence-transformers."""

    def __init__(self):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(os.getenv("EMBED_MODEL", "ibm-granite/granite-embedding-30m-english"),
                                         model_kwargs={"dtype": "float32"})

    def embed_documents(self, texts):
        return self.model.encode(texts, normalize_embeddings=True).tolist()

    def embed_query(self, text):
        return self.embed_documents([text])[0]


@lru_cache(maxsize=1)
def embeddings() -> GraniteEmbeddings:
    return GraniteEmbeddings()


def ticket_store(conn) -> DB2VS:
    return DB2VS(client=conn, embedding_function=embeddings(), table_name=TABLE,
                 distance_strategy=DistanceStrategy.COSINE)


def search_tickets(conn, text: str, k: int = 3) -> list[dict]:
    hits = ticket_store(conn).similarity_search_with_score(text, k=k)
    return [{"ticket_id": d.metadata.get("ticket_id"), "customer_id": d.metadata.get("customer_id"),
             "text": d.page_content, "distance": round(float(score), 4)} for d, score in hits]
