"""Haystack retrieval: metadata filtering, passage citations and the guidance API.
Runs in BM25-only mode on SQLite and in hybrid mode (BM25 + IBM Db2 vector) on Db2."""
import pytest

from backend.app.ai.haystack.rag_pipeline import build_filters, protocol_retriever, retrieve_safety_guidance

API = "/api/v1"


def test_build_filters_combines_conditions():
    assert build_filters() is None
    assert build_filters(category="elder_care") == {"field": "meta.category", "operator": "==", "value": "elder_care"}
    combined = build_filters(category="elder_care", audience="seniors")
    assert combined["operator"] == "AND" and len(combined["conditions"]) == 2


def test_category_filter_restricts_results():
    res = retrieve_safety_guidance("emergency help procedure for residents", category="elder_care")
    assert all(r["category"] == "elder_care" for r in res["results"])


def test_audience_filter_restricts_results():
    res = retrieve_safety_guidance("safety at night when walking alone", audience="responders")
    assert all("responders" in r["audience"] for r in res["results"])
    women = retrieve_safety_guidance("safe transit corridor for women at night", audience="women")
    assert women["found"] and women["results"][0]["document_id"] == "DOC-WOMEN-005"


def test_results_cite_the_matching_passage():
    res = retrieve_safety_guidance("child journey delay escalation for guardians")
    top = res["results"][0]
    assert top["document_id"] == "DOC-CHILD-002"
    assert top["cited_passage"] and top["cited_passage"] in protocol_retriever.protocols["DOC-CHILD-002"]["title"] + ". " \
        + protocol_retriever.protocols["DOC-CHILD-002"]["content"]


def test_empty_or_stopword_queries_return_nothing():
    assert not retrieve_safety_guidance("the and of")["found"]


def test_guidance_api_validates_filters(client, resident):
    ok = client.get(f"{API}/ai/guidance", params={"query": "elderly wellness check", "audience": "seniors"}, headers=resident)
    assert ok.status_code == 200 and ok.json()["results"][0]["category"] == "elder_care"
    bad = client.get(f"{API}/ai/guidance", params={"query": "anything here", "audience": "aliens"}, headers=resident)
    assert bad.status_code == 422


def test_hybrid_status_reports_db2_table():
    if not protocol_retriever.hybrid:  # decided at startup, after test collection
        pytest.skip("hybrid retrieval needs IBM Db2")
    status = protocol_retriever.status()
    assert status["hybrid"] and status["db2_table"] == "NSIN_PROTOCOL_PASSAGES" and status["passages"] > 6
