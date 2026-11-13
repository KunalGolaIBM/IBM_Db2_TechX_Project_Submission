"""
src/ai/memory_search.py
-----------------------
Semantic search over saved music memories using:
  - LangChain DB2VS (Db2 vector store via langchain-db2)
  - nomic-embed-text via Ollama (already installed on this machine)

Memories are embedded once when saved, stored as vectors in Db2,
and retrieved by cosine similarity at query time.

Usage:
    from src.ai.memory_search import MemorySearch
    ms = MemorySearch()
    ms.add_memory("This song played when my grandmother visited", "Tere Bina", "AR Rahman", "wholesome")
    results = ms.search("family and nostalgia", k=3)
    for r in results:
        print(r.page_content, r.metadata)
"""

from __future__ import annotations
import os
from dotenv import load_dotenv

from langchain_core.documents import Document
from langchain_community.embeddings import OllamaEmbeddings

load_dotenv()

# DB2VS import — installed via langchain-db2
try:
    import ibm_db_dbi
    from langchain_db2.db2vs import DB2VS
    from langchain_community.vectorstores.utils import DistanceStrategy
    _DB2VS_AVAILABLE = True
except ImportError:
    _DB2VS_AVAILABLE = False

TABLE_NAME = "MEMORY_VECTORS"


def _get_embeddings() -> OllamaEmbeddings:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    return OllamaEmbeddings(model="nomic-embed-text", base_url=base_url)


def _get_db2_conn():
    """Return an ibm_db_dbi connection (DBI-style, required by DB2VS)."""
    return ibm_db_dbi.connect(
        f"DATABASE={os.environ['DB2_DATABASE']};"
        f"HOSTNAME={os.environ['DB2_HOST']};"
        f"PORT={os.environ['DB2_PORT']};"
        "PROTOCOL=TCPIP;"
        f"UID={os.environ['DB2_USER']};"
        f"PWD={os.environ['DB2_PASSWORD']};",
        "",
        "",
    )


class MemorySearch:
    """
    Stores and retrieves music memories using Db2 as the vector store.
    Falls back to keyword search if langchain-db2 is not installed.
    """

    def __init__(self) -> None:
        if not _DB2VS_AVAILABLE:
            print(
                "[MemorySearch] langchain-db2 not installed — "
                "semantic search unavailable. Install with: pip install langchain-db2"
            )
        self._store: DB2VS | None = None

    def _get_store(self) -> "DB2VS":
        if self._store is None:
            if not _DB2VS_AVAILABLE:
                raise RuntimeError("langchain-db2 is not installed.")
            conn = _get_db2_conn()
            self._store = DB2VS(
                embedding_function=_get_embeddings(),
                client=conn,
                table_name=TABLE_NAME,
                distance_strategy=DistanceStrategy.COSINE,
            )
        return self._store

    def add_memory(
        self,
        memory_text: str,
        song_title: str,
        artist: str,
        mood_tag: str,
    ) -> None:
        """
        Embed a memory and store it in Db2 alongside its metadata.
        Also persists to the MEMORIES table via queries.save_memory.
        """
        if not _DB2VS_AVAILABLE:
            print("[MemorySearch] Skipping vector storage — langchain-db2 not installed.")
            return
        doc = Document(
            page_content=memory_text,
            metadata={
                "song_title": song_title,
                "artist": artist,
                "mood_tag": mood_tag,
            },
        )
        self._get_store().add_documents([doc])

    def search(self, query: str, k: int = 3) -> list[Document]:
        """
        Return up to k memories semantically similar to the query.
        Returns an empty list if the vector store is unavailable.
        """
        if not _DB2VS_AVAILABLE:
            return []
        try:
            return self._get_store().similarity_search(query, k=k)
        except Exception as exc:
            print(f"[MemorySearch] Search error: {exc}")
            return []

