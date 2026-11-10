"""LangChain Db2 vector search for PII taxonomy classification."""

from __future__ import annotations

import hashlib
import threading
from typing import TYPE_CHECKING, Any

from app.config import settings
from app.db import MOCK_MODE, conn, query
from app.sql import quote_identifier

if TYPE_CHECKING:
    from langchain_core.embeddings import Embeddings
    from langchain_db2.db2vs import DB2VS

VECTOR_TABLE = "PII_TAXONOMY_VECTORS"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

_TAXONOMY = {
    "EMAIL": "Email address, e-mail, electronic mail, customer or user email contact.",
    "PHONE": "Phone number, telephone, mobile, cell number, contact number.",
    "NAME": "Person name, first name, last name, full name, customer or patient name.",
    "ADDRESS": "Postal address, street, city, state, ZIP or PIN code, residence.",
    "DOB": "Date of birth, birth date, birthday, age-related date.",
    "GOVT_ID": "Government identity number, Aadhaar, PAN, national ID, passport number.",
    "HEALTH": "Medical or health information, diagnosis, medication, prescription, lab result.",
}

_vector_store: DB2VS | None = None
_vector_store_lock = threading.Lock()


def _record_id(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()[:16].upper()


def _qualified_table_name(table_name: str) -> str:
    return (
        f"{quote_identifier(settings.db2_schema)}."
        f"{quote_identifier(table_name)}"
    )


def _seed_taxonomy(vector_store: DB2VS, table_name: str) -> None:
    from langchain_core.documents import Document

    sql = f"SELECT ID FROM {table_name}"  # nosec B608
    existing_rows = query(sql) or []
    existing_ids = {str(row[0]).strip().upper() for row in existing_rows}

    documents = [
        Document(page_content=text, metadata={"label": label})
        for label, text in _TAXONOMY.items()
        if _record_id(label) not in existing_ids
    ]
    if documents:
        vector_store.add_documents(
            documents,
            ids=[document.metadata["label"] for document in documents],
        )


def create_vector_store(
    *,
    client: Any | None = None,
    embeddings: Embeddings | None = None,
    table_name: str = VECTOR_TABLE,
) -> DB2VS:
    """Create the Db2 vector store and insert any missing taxonomy entries."""
    if MOCK_MODE and client is None:
        raise RuntimeError("Db2 vector search is unavailable in mock mode")

    qualified_table = _qualified_table_name(table_name)
    if client is None:
        client = conn()

    if embeddings is None:
        from langchain_community.embeddings import HuggingFaceEmbeddings

        embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

    from langchain_community.vectorstores.utils import DistanceStrategy
    from langchain_db2.db2vs import DB2VS

    vector_store = DB2VS(
        embedding_function=embeddings,
        table_name=qualified_table,
        client=client,
        distance_strategy=DistanceStrategy.COSINE,
        query="email address and personal contact information",
    )
    _seed_taxonomy(vector_store, qualified_table)
    return vector_store


def get_vector_store() -> DB2VS:
    """Return the process-wide Db2 vector store, initializing it on first use."""
    global _vector_store

    if MOCK_MODE:
        raise RuntimeError("Db2 vector search is unavailable in mock mode")

    if _vector_store is None:
        with _vector_store_lock:
            if _vector_store is None:
                _vector_store = create_vector_store()
    return _vector_store


def classify_column_name(
    column_name: str,
    vector_store: DB2VS | None = None,
) -> tuple[str, float] | None:
    """Return the closest PII taxonomy label and its Db2 cosine distance."""
    store = vector_store or get_vector_store()
    query_text = column_name.replace("_", " ")
    matches = store.similarity_search_with_score(query_text, k=1)
    if not matches:
        return None

    document, distance = matches[0]
    label = document.metadata.get("label")
    if label not in _TAXONOMY:
        raise ValueError(f"Unknown PII taxonomy label returned by Db2VS: {label!r}")
    return label, float(distance)
