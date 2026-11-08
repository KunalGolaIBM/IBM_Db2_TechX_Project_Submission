"""LangChain integration with IBM Db2's DB2VS vector store.

Requires Db2 12.1.2+ with vector-search support. HashEmbeddings is a deterministic
hashed n-gram baseline, not a transformer or semantic embedding model.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

try:
    from langchain_core.embeddings import Embeddings
except ImportError:  # Enables offline adapter tests; full vector mode installs langchain-core.
    class Embeddings:  # type: ignore[no-redef]
        """Minimal protocol fallback used only when the LangChain dependency is absent."""
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            raise NotImplementedError

        def embed_query(self, text: str) -> list[float]:
            raise NotImplementedError

from sklearn.feature_extraction.text import HashingVectorizer

from .config import get_settings


class HashEmbeddings(Embeddings):
    """Small, deterministic 384-dimension hashed n-gram embeddings for reproducible demos."""

    def __init__(self, dimensions: int = 384):
        if dimensions < 32:
            raise ValueError("dimensions must be at least 32")
        self.dimensions = dimensions
        self.vectorizer = HashingVectorizer(
            n_features=dimensions,
            alternate_sign=False,
            norm="l2",
            ngram_range=(1, 2),
            analyzer="word",
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if any(not isinstance(text, str) for text in texts):
            raise TypeError("All embedding inputs must be strings")
        matrix = self.vectorizer.transform(texts)
        return matrix.toarray().astype(float).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def build_embeddings(provider: str | None = None):
    """Build the configured embedding backend for Db2 vector retrieval.

    The hash backend is deterministic and dependency-light for offline tests.
    Hugging Face is the preferred live-demo option because it captures semantic
    similarity rather than relying only on token/ngram overlap.
    """
    settings = get_settings()
    selected = (provider or settings.db2_embedding_provider).strip().lower()
    if selected == "hash":
        return HashEmbeddings()
    if selected == "huggingface":
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
        except ImportError as exc:
            raise RuntimeError(
                "Install langchain-huggingface and sentence-transformers to use semantic embeddings."
            ) from exc
        return HuggingFaceEmbeddings(
            model_name=settings.db2_embedding_model,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    raise ValueError("DB2_EMBEDDING_PROVIDER must be 'hash' or 'huggingface'.")


@contextmanager
def _open_db2_vector_store() -> Iterator[object]:
    settings = get_settings()
    settings.validate()
    if settings.db_backend != "db2":
        raise RuntimeError("Set DB_BACKEND=db2 to enable IBM Db2 vector retrieval.")
    try:
        import ibm_db_dbi
        from langchain_db2 import DB2VS
    except ImportError as exc:
        raise RuntimeError("Install ibm-db and langchain-db2 before using Db2 vector search.") from exc

    connection = ibm_db_dbi.connect(settings.db2_connection_string, "", "")
    try:
        store = DB2VS(
            embedding_function=build_embeddings(),
            table_name="ESAI_KNOWLEDGE",
            client=connection,
        )
        yield store
    finally:
        connection.close()


MAINTENANCE_NOTES = [
    "A sudden increase in motor current can be associated with increased mechanical load, friction, a jam, supply variation or sensor calibration error. Compare with the appliance-specific baseline before diagnosing.",
    "Higher motor temperature can be associated with restricted ventilation, excessive load, bearing friction or ambient temperature. Inspect only under safe isolation and qualified supervision.",
    "Increased vibration can be associated with mounting looseness, misalignment, imbalance or bearing wear. A single reading is not proof of failure; inspect trends and operating context.",
    "Unexpectedly long runtime can indicate a schedule change, control issue or a process that has not completed. Compare runtime with the selected appliance's historical operating cycle.",
    "Voltage measurement anomalies can be caused by supply variation, wiring, module scaling or ADC calibration. Validate the voltage sensor and isolation before interpreting the result.",
    "EnergySense AI keeps deterministic local relay protection independent of network services and AI. AI outputs are advisory and require human verification.",
]


def seed_maintenance_knowledge(vector_store=None) -> int:
    metadata = [{"topic": "maintenance", "source": "EnergySense AI knowledge seed"} for _ in MAINTENANCE_NOTES]
    if vector_store is not None:
        vector_store.add_texts(MAINTENANCE_NOTES, metadatas=metadata)
        return len(MAINTENANCE_NOTES)
    with _open_db2_vector_store() as store:
        store.add_texts(MAINTENANCE_NOTES, metadatas=metadata)
    return len(MAINTENANCE_NOTES)


def search_maintenance_knowledge(query: str, k: int = 3) -> list[str]:
    query = query.strip()
    if not query or len(query) > 1000:
        raise ValueError("query must contain 1 to 1000 characters")
    safe_k = max(1, min(int(k), 5))
    with _open_db2_vector_store() as store:
        documents = store.similarity_search(query, k=safe_k)
    return [document.page_content for document in documents]
