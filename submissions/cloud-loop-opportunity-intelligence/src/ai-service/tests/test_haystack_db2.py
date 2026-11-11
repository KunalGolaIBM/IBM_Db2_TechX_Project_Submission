import pytest
from app.services.haystack_service import haystack_db2_service
from app.core.config import settings


def test_haystack_store_initialization():
    store = haystack_db2_service.get_document_store()
    assert store is not None


def test_haystack_document_indexing_and_search():
    sample_docs = [
        {
            "id": "test-ibm-intern",
            "content": "IBM Cloud and Db2 Student Developer Internship in Bangalore focusing on SQL, Python, and Vector Embeddings.",
            "meta": {
                "slug": "test-ibm-intern",
                "title": "Db2 Developer Intern",
                "organization": "IBM",
                "opportunity_type": "internship",
                "category": "Cloud & AI",
                "location": "Bangalore",
                "deadline": "2026-12-31"
            }
        },
        {
            "id": "test-frontend-role",
            "content": "Frontend Engineer internship working with React, Next.js, Tailwind CSS, and UX design.",
            "meta": {
                "slug": "test-frontend-role",
                "title": "Frontend Engineer",
                "organization": "Adobe",
                "opportunity_type": "job",
                "category": "Frontend",
                "location": "Noida",
                "deadline": "2026-11-30"
            }
        }
    ]

    indexed = haystack_db2_service.write_documents(sample_docs)
    assert indexed >= 2

    # Query matching IBM Db2
    results = haystack_db2_service.search("IBM Db2 SQL developer", top_k=2)
    assert len(results) > 0
    top_match = results[0]
    assert "test-ibm-intern" in top_match["id"] or top_match["score"] > 0.5


def test_haystack_filtered_search():
    # Search with filter for internship
    filters = {"field": "meta.opportunity_type", "operator": "==", "value": "internship"}
    results = haystack_db2_service.search("developer", filters=filters, top_k=5)
    for r in results:
        assert r["meta"].get("opportunity_type") == "internship"
