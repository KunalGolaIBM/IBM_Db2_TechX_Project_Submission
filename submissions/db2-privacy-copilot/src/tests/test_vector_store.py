"""Unit tests for LangChain Db2 vector-store classification."""

import pytest

from app import vector_store


class FakeDocument:
    def __init__(self, page_content, metadata):
        self.page_content = page_content
        self.metadata = metadata


class FakeVectorStore:
    def __init__(self, matches):
        self.matches = matches
        self.query = None
        self.k = None

    def similarity_search_with_score(self, query, k):
        self.query = query
        self.k = k
        return self.matches


def test_classify_column_name_uses_db2vs_distance():
    store = FakeVectorStore(
        [(FakeDocument(page_content="email address", metadata={"label": "EMAIL"}), 0.12)]
    )

    result = vector_store.classify_column_name("CUST_MAIL_ID", vector_store=store)

    assert result == ("EMAIL", 0.12)
    assert store.query == "CUST MAIL ID"
    assert store.k == 1


def test_classify_column_name_returns_none_without_matches():
    store = FakeVectorStore([])

    assert vector_store.classify_column_name("UNKNOWN", vector_store=store) is None


def test_classify_column_name_rejects_unknown_taxonomy_label():
    store = FakeVectorStore(
        [(FakeDocument(page_content="unexpected", metadata={"label": "NOT_PII"}), 0.1)]
    )

    with pytest.raises(ValueError, match="Unknown PII taxonomy label"):
        vector_store.classify_column_name("SOMETHING", vector_store=store)


def test_seed_taxonomy_only_adds_missing_documents(monkeypatch):
    existing_label = next(iter(vector_store._TAXONOMY))
    existing_id = vector_store._record_id(existing_label)
    monkeypatch.setattr(vector_store, "query", lambda sql: [(existing_id,)])
    store = FakeVectorStore([])
    store.add_documents = lambda documents, ids: setattr(
        store, "added", (documents, ids)
    )

    vector_store._seed_taxonomy(store, '"DB2INST1"."PII_TAXONOMY_VECTORS"')

    documents, ids = store.added
    labels = [document.metadata["label"] for document in documents]
    assert existing_label not in labels
    assert len(labels) == len(vector_store._TAXONOMY) - 1
    assert ids == labels
