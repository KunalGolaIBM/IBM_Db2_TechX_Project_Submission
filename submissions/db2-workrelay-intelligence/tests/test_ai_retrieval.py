from langchain_core.documents import Document as LCDocument
from langchain_core.retrievers import BaseRetriever

from app.agent.coordinator import IncidentCoordinator
from app.ai.knowledge_retriever import (
    IncidentKnowledgeRetriever,
    KnowledgeDocument,
    LangChainRunbookRetriever,
)
from app.db.connection import Db2ConnectionManager
from app.db.repository import Db2IncidentRepository
from app.models.incident import Incident, IncidentSeverity


def test_knowledge_retriever_seeded_runbooks():
    retriever = IncidentKnowledgeRetriever()
    status = retriever.get_status()
    assert status["total_documents"] >= 4
    assert status["total_langchain_documents"] >= 4
    assert status["framework"] == "LangChain"
    assert status["retriever_class"] == "LangChainRunbookRetriever"
    assert status["engine_ready"] is True


def test_runbooks_converted_to_langchain_documents():
    retriever = IncidentKnowledgeRetriever()
    assert len(retriever.langchain_docs) >= 4
    for doc in retriever.langchain_docs:
        assert isinstance(doc, LCDocument)
        assert len(doc.page_content) > 0
        assert "doc_id" in doc.metadata
        assert "service" in doc.metadata
        assert "resolution_steps" in doc.metadata

    # Verify single document conversion
    sample = KnowledgeDocument(
        doc_id="TEST-001",
        title="Test Title",
        category="test",
        service="test-svc",
        content="Test issue occurred",
        resolution_steps="Restart test service",
    )
    lc_doc = sample.to_langchain_document()
    assert isinstance(lc_doc, LCDocument)
    assert lc_doc.metadata["doc_id"] == "TEST-001"
    assert "Restart test service" in lc_doc.page_content


def test_langchain_retriever_direct_invocation():
    retriever = IncidentKnowledgeRetriever()
    lc_retriever = retriever.retriever
    assert isinstance(lc_retriever, BaseRetriever)
    assert isinstance(lc_retriever, LangChainRunbookRetriever)

    # Invoke via LangChain's Runnable interface
    docs = lc_retriever.invoke("SQL0964C transaction log full service:database")
    assert len(docs) >= 1
    assert isinstance(docs[0], LCDocument)
    assert docs[0].metadata["doc_id"] == "RUNBOOK-DB2-002"
    assert "LOGFILSIZ" in docs[0].metadata["resolution_steps"]


def test_knowledge_retriever_query_matching():
    retriever = IncidentKnowledgeRetriever()
    res = retriever.query("SQL0964C transaction log full error", service="database")
    assert res["matches_count"] >= 1
    top_doc = res["matches"][0]
    assert "Transaction Log Full" in top_doc["title"]
    assert "LOGFILSIZ" in top_doc["resolution_steps"]
    assert "Matched" in res["recommendation"]


def test_knowledge_retriever_irrelevant_query_handling():
    retriever = IncidentKnowledgeRetriever()
    res = retriever.query("unrelated extraterrestrial quantum anomaly", service="unknown-svc")
    assert res["matches_count"] == 0
    assert res["matches"] == []
    assert "No high-confidence runbook match found" in res["recommendation"]


def test_knowledge_retriever_custom_ingest():
    retriever = IncidentKnowledgeRetriever()
    custom_doc = KnowledgeDocument(
        doc_id="RUNBOOK-CUSTOM-099",
        title="Custom Kafka Consumer Lag Spikes",
        category="messaging",
        service="kafka",
        content="Kafka consumer group partitions unbalanced and lag exceeding 10k messages",
        resolution_steps="Scale up consumer pod replicas to match partition count",
    )
    retriever.ingest_document(custom_doc)
    res = retriever.query("kafka consumer lag high", service="kafka")
    assert res["matches_count"] >= 1
    assert res["matches"][0]["doc_id"] == "RUNBOOK-CUSTOM-099"

    # Confirm it was also converted to a LangChain Document in the active retriever
    lc_matching = [d for d in retriever.retriever.documents if d.metadata.get("doc_id") == "RUNBOOK-CUSTOM-099"]
    assert len(lc_matching) == 1
    assert isinstance(lc_matching[0], LCDocument)


def test_coordinator_workflow_uses_langchain_retriever():
    mgr = Db2ConnectionManager(use_mock=True)
    repo = Db2IncidentRepository(mgr)
    repo.init_schema_sqlite()
    coord = IncidentCoordinator(repo)

    incident = Incident(
        title="Db2 SQL0964C critical transaction log exhaustion",
        description="Write transactions failing across order persistence pipeline with full log",
        service="database",
        severity=IncidentSeverity.CRITICAL,
    )
    result = coord.handle(incident)

    # Verify that the coordinator invoked the LangChain retriever and embedded the context
    assert "ai_runbook_context" in result.metadata
    ai_ctx = result.metadata["ai_runbook_context"]
    assert ai_ctx["matches_count"] >= 1
    assert ai_ctx["matches"][0]["doc_id"] == "RUNBOOK-DB2-002"
    assert "LOGFILSIZ" in ai_ctx["recommendation"]
