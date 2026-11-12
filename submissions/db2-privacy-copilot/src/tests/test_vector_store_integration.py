"""Integration test for the live IBM Db2 vector store."""

import uuid

import pytest

from app.db import conn
from app.vector_store import classify_column_name, create_vector_store

pytestmark = pytest.mark.integration


def test_db2vs_stores_and_searches_pii_taxonomy():
    from langchain_core.embeddings import Embeddings
    from langchain_db2.db2vs import drop_table

    class FixedEmbeddings(Embeddings):
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [self.embed_query(text) for text in texts]

        def embed_query(self, text: str) -> list[float]:
            if "email" in text.lower():
                return [1.0, 0.0, 0.0]
            if "phone" in text.lower():
                return [0.0, 1.0, 0.0]
            return [0.0, 0.0, 1.0]

    client = conn()
    table_name = f"DB2VS_TEST_{uuid.uuid4().hex[:8].upper()}"
    vector_store = None

    try:
        vector_store = create_vector_store(
            client=client,
            embeddings=FixedEmbeddings(),
            table_name=table_name,
        )
        result = classify_column_name("customer email", vector_store=vector_store)

        assert result is not None
        assert result[0] == "EMAIL"
        assert result[1] == pytest.approx(0.0, abs=1e-5)
    finally:
        if vector_store is not None:
            drop_table(client, vector_store.table_name)
        client.close()
