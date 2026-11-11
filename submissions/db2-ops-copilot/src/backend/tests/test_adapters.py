"""Mock adapters, adapter registry and dependency-injection selection."""

from __future__ import annotations

import pytest

from app.adapters.audit.mock_audit import MockAuditAdapter
from app.adapters.base import AuditRecord, DocumentInput
from app.adapters.db.mock_db import MockDatabaseAdapter
from app.adapters.embeddings.mock_embeddings import MockEmbeddingModelAdapter
from app.adapters.llm.mock_llm import MockChatModelAdapter
from app.adapters.orchestration.mock_orchestrator import MockOrchestrator
from app.adapters.registry import AdapterRegistry
from app.adapters.sql_validator.sqlglot_validator import SqlGlotValidator
from app.adapters.vector.mock_vector import MockVectorStoreAdapter
from app.core.config import Settings


# -- mock database -------------------------------------------------------------
def test_mock_db_executes_select():
    db = MockDatabaseAdapter(Settings(_env_file=None))
    result = db.execute_readonly("SELECT * FROM DEMO_SERVERS")
    assert result.columns == [
        "SERVER_ID",
        "HOSTNAME",
        "ENVIRONMENT",
        "OWNER_TEAM",
        "UPTIME_PCT",
    ]
    assert result.row_count == 4


def test_mock_db_respects_fetch_first():
    db = MockDatabaseAdapter(Settings(_env_file=None))
    result = db.execute_readonly(
        "SELECT * FROM DEMO_SERVERS FETCH FIRST 2 ROWS ONLY"
    )
    assert result.row_count == 2
    assert result.truncated is True


def test_mock_db_refuses_non_select():
    db = MockDatabaseAdapter(Settings(_env_file=None))
    with pytest.raises(ValueError):
        db.execute_readonly("DROP TABLE DEMO_SERVERS")


def test_mock_db_schema_snapshot():
    db = MockDatabaseAdapter(Settings(_env_file=None))
    snapshot = db.fetch_schema()
    assert snapshot.source == "mock"
    names = {t.name for t in snapshot.tables}
    # Mirrors database/migrations 001 + 004 (M2 schema).
    assert {
        "DEMO_SERVERS",
        "DEMO_INCIDENTS",
        "COPILOT_KB",
        "APP_AUDIT",
        "DOCUMENT_METADATA",
        "QUERY_EXECUTIONS",
    } <= names


# -- mock vector store -----------------------------------------------------------
def test_mock_vector_search_ranks_by_overlap():
    store = MockVectorStoreAdapter(Settings(_env_file=None))
    hits = store.similarity_search("vector embeddings in Db2", k=2)
    assert hits
    # Score is a DISTANCE (lower = closer), matching DB2VS/VECTOR_DISTANCE.
    assert hits[0].score <= hits[-1].score
    assert "vector" in hits[0].content.lower()


def test_mock_vector_metadata_filters():
    store = MockVectorStoreAdapter(Settings(_env_file=None))
    hits = store.similarity_search("anything", k=10, filters={"source": "db2-docs"})
    assert hits
    assert all(h.metadata["source"] == "db2-docs" for h in hits)


def test_mock_vector_upsert_and_count():
    store = MockVectorStoreAdapter(Settings(_env_file=None))
    before = store.count()
    added = store.upsert_documents([DocumentInput(text="new doc", metadata={"source": "test"})])
    assert added == 1
    assert store.count() == before + 1


# -- mock llm / embeddings --------------------------------------------------------
def test_mock_llm_deterministic():
    llm = MockChatModelAdapter(Settings(_env_file=None))
    first = llm.generate("hello")
    second = llm.generate("hello")
    assert first.text == second.text
    assert first.text.startswith("[mock:")


def test_mock_embeddings_deterministic_and_sized():
    emb = MockEmbeddingModelAdapter(Settings(_env_file=None, embedding_dimensions=16))
    first = emb.embed(["alpha"])
    second = emb.embed(["alpha"])
    assert first.vectors == second.vectors
    assert len(first.vectors[0]) == 16
    assert first.dimensions == 16


# -- mock audit -------------------------------------------------------------------
def test_mock_audit_records_and_lists_newest_first():
    audit = MockAuditAdapter(Settings(_env_file=None))
    audit.record(
        AuditRecord(intent="docs", question="q", status="OK", latency_ms=5, timestamp="t")
    )
    entries = audit.list_recent(limit=10)
    assert entries[0].question == "q"
    assert entries[0].status == "OK"


# -- mock orchestrator --------------------------------------------------------------
def test_mock_orchestrator_intents():
    orch = MockOrchestrator(Settings(_env_file=None))
    assert orch.respond("What is DB2VS?").intent == "docs"
    assert orch.respond("List servers by uptime").intent == "data"
    assert orch.respond("hello there").intent == "general"


def test_mock_orchestrator_sql_passes_gate():
    orch = MockOrchestrator(Settings(_env_file=None))
    result = orch.respond("List the top servers")
    assert result.sql is not None
    assert orch._validator.validate(result.sql).valid is True


# -- registry / DI -----------------------------------------------------------------
def test_registry_mock_mode_builds_mock_adapters():
    registry = AdapterRegistry.from_settings(Settings(_env_file=None))
    try:
        assert registry.mode == "mock"
        for adapter in registry._adapters:
            assert adapter.mode == "mock"
            assert adapter.provider_id == "mock"
        assert isinstance(registry.database, MockDatabaseAdapter)
        assert isinstance(registry.orchestrator, MockOrchestrator)
        assert isinstance(registry.validator, SqlGlotValidator)
    finally:
        registry.close_all()


def test_registry_real_mode_never_uses_mock_adapters():
    settings = Settings(_env_file=None, adapter_mode="real", db2_connect_timeout_ms=200)
    registry = AdapterRegistry.from_settings(settings)
    try:
        assert registry.mode == "real"
        for adapter in registry._adapters:
            assert adapter.mode == "real"
            assert adapter.provider_id != "mock"
        assert not isinstance(registry.database, MockDatabaseAdapter)
        assert not isinstance(registry.orchestrator, MockOrchestrator)
    finally:
        registry.close_all()


def test_closed_mock_adapters_report_unavailable():
    settings = Settings(_env_file=None)
    db = MockDatabaseAdapter(settings)
    db.close()
    assert db.ping().status == "unavailable"


def test_registry_probes_never_raise():
    registry = AdapterRegistry.from_settings(Settings(_env_file=None))
    try:
        probes = registry.probes()
        assert len(probes) == 6
        assert all(p.status in {"ok", "degraded", "unavailable"} for p in probes)
    finally:
        registry.close_all()


def test_registry_close_all_is_idempotent():
    registry = AdapterRegistry.from_settings(Settings(_env_file=None))
    registry.close_all()
    registry.close_all()  # must not raise
