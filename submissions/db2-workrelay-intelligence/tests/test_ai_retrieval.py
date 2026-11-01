from app.ai.knowledge_retriever import (
    IncidentKnowledgeRetriever,
    KnowledgeDocument,
)


def test_knowledge_retriever_seeded_runbooks():
    retriever = IncidentKnowledgeRetriever()
    status = retriever.get_status()
    assert status["total_documents"] >= 4
    assert status["engine_ready"] is True


def test_knowledge_retriever_query_matching():
    retriever = IncidentKnowledgeRetriever()
    # Query for Db2 transaction log
    res = retriever.query("SQL0964C transaction log full error", service="database")
    assert res["matches_count"] >= 1
    top_doc = res["matches"][0]
    assert "Transaction Log Full" in top_doc["title"]
    assert "LOGFILSIZ" in top_doc["resolution_steps"]


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
