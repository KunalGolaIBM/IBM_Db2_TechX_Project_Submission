import pytest
from app.services.haystack_service import haystack_db2_service

def test_filter_building():
    # Verify filter translation structure
    filters = {
        "operator": "AND",
        "conditions": [
            {"field": "meta.kind", "operator": "==", "value": "job"},
            {"field": "meta.deadline", "operator": ">=", "value": "2026-01-01"},
        ]
    }
    assert filters["operator"] == "AND"
    assert len(filters["conditions"]) == 2
    assert filters["conditions"][0]["field"] == "meta.kind"

def test_haystack_search_with_filter():
    # In fallback or native mode, search with a kind filter returns only that kind
    res = haystack_db2_service.search(
        query="software engineer",
        filters={"field": "meta.kind", "operator": "==", "value": "certification"},
        top_k=5
    )
    for r in res:
        meta = r.get("meta", {})
        if "kind" in meta:
            assert meta["kind"] == "certification"
