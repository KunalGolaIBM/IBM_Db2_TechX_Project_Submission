import sys
from types import ModuleType, SimpleNamespace

import pytest

from src.config import Settings
from src.langchain_db2 import HashEmbeddings, seed_maintenance_knowledge, search_maintenance_knowledge


def test_hash_embeddings_are_deterministic_and_fixed_width():
    embeddings = HashEmbeddings(dimensions=128)
    first = embeddings.embed_query("motor current anomaly")
    second = embeddings.embed_query("motor current anomaly")
    assert first == second
    assert len(first) == 128
    assert any(value != 0 for value in first)


def test_hash_embeddings_reject_non_string_and_invalid_dimensions():
    with pytest.raises(ValueError):
        HashEmbeddings(dimensions=8)
    with pytest.raises(TypeError):
        HashEmbeddings().embed_documents(["good", 123])


def test_seed_knowledge_supports_an_injected_vector_store():
    calls = {}
    class FakeVectorStore:
        def add_texts(self, texts, metadatas=None):
            calls["texts"] = texts
            calls["metadatas"] = metadatas
    count = seed_maintenance_knowledge(FakeVectorStore())
    assert count == len(calls["texts"]) == 6
    assert all(meta["topic"] == "maintenance" for meta in calls["metadatas"])


def test_db2_vector_search_closes_connection(monkeypatch):
    connections = []
    class Connection:
        closed = False
        def close(self): self.closed = True
    def connect(*_args):
        connection = Connection()
        connections.append(connection)
        return connection
    driver = ModuleType("ibm_db_dbi")
    driver.connect = connect
    class FakeDB2VS:
        def __init__(self, **kwargs): self.kwargs = kwargs
        def similarity_search(self, query, k=3):
            return [SimpleNamespace(page_content=f"matched {query}")]
    vector_module = ModuleType("langchain_db2")
    vector_module.DB2VS = FakeDB2VS
    monkeypatch.setitem(sys.modules, "ibm_db_dbi", driver)
    monkeypatch.setitem(sys.modules, "langchain_db2", vector_module)
    monkeypatch.setattr("src.langchain_db2.get_settings", lambda: Settings(db_backend="db2", db2_password="test"))
    assert search_maintenance_knowledge("bearing temperature", k=9) == ["matched bearing temperature"]
    assert connections and all(connection.closed for connection in connections)


def test_build_embeddings_supports_configured_huggingface_provider(monkeypatch):
    import sys
    from types import SimpleNamespace
    from src import langchain_db2

    captured = {}

    class FakeHuggingFaceEmbeddings:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        langchain_db2, "get_settings",
        lambda: SimpleNamespace(
            db2_embedding_provider="huggingface",
            db2_embedding_model="sentence-transformers/all-MiniLM-L6-v2",
        ),
    )
    monkeypatch.setitem(
        sys.modules, "langchain_huggingface",
        SimpleNamespace(HuggingFaceEmbeddings=FakeHuggingFaceEmbeddings),
    )
    langchain_db2.build_embeddings()
    assert captured["model_name"] == "sentence-transformers/all-MiniLM-L6-v2"
    assert captured["model_kwargs"] == {"device": "cpu"}
    assert captured["encode_kwargs"] == {"normalize_embeddings": True}


def test_build_embeddings_rejects_unknown_provider(monkeypatch):
    from types import SimpleNamespace
    from src import langchain_db2

    monkeypatch.setattr(
        langchain_db2, "get_settings",
        lambda: SimpleNamespace(db2_embedding_provider="other"),
    )
    with pytest.raises(ValueError, match="DB2_EMBEDDING_PROVIDER"):
        langchain_db2.build_embeddings()
