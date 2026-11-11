"""Mock-mode coverage for minimal knowledge-document ingestion."""


def test_mock_knowledge_ingestion_is_available_offline(client):
    response = client.post(
        "/api/v1/knowledge/documents",
        json={
            "documents": [
                {
                    "text": "Test guide: RUNSTATS refreshes Db2 optimizer statistics.",
                    "metadata": {
                        "id": "test-runstats-guide",
                        "source": "test",
                        "title": "RUNSTATS guide",
                    },
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.json() == {"documents_added": 1, "mock": True}
    hits = client.app.state.registry.vector_store.similarity_search("RUNSTATS optimizer", k=10)
    assert any(hit.metadata.get("id") == "test-runstats-guide" for hit in hits)


def test_knowledge_ingestion_rejects_empty_or_oversized_batches(client):
    assert client.post("/api/v1/knowledge/documents", json={"documents": []}).status_code == 422
    too_many = [{"text": f"document {index}"} for index in range(21)]
    assert client.post(
        "/api/v1/knowledge/documents", json={"documents": too_many}
    ).status_code == 422
