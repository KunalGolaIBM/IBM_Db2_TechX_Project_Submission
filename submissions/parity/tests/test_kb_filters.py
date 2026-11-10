"""Tests for category filtering in knowledge base search."""

from parity.kb.store import InMemoryKb, KnownDifference, function_of


def kb_with_categories() -> InMemoryKb:
    kb = InMemoryKb()
    kb.add(
        KnownDifference(
            title="count alias",
            source_pattern="COUNT(*)",
            db2_pattern="COUNT(*) AS COUNT",
            category="aggregate",
            verified=True,
        )
    )
    kb.add(
        KnownDifference(
            title="ilike fix",
            source_pattern="ILIKE",
            db2_pattern="UPPER LIKE",
            category="string",
            verified=True,
        )
    )
    return kb


def test_function_of():
    assert function_of(KnownDifference(title="t", source_pattern="COUNT(*)", db2_pattern="x")) == "COUNT"
    assert function_of(KnownDifference(title="t", source_pattern="", db2_pattern="x")) == ""


def test_matches_category():
    entry = KnownDifference(
        title="count alias", source_pattern="COUNT(*)", db2_pattern="x", category="aggregate"
    )
    assert entry.matches_category("") is True
    assert entry.matches_category("aggregate") is True
    assert entry.matches_category("string") is False


def test_search_without_category_returns_all():
    kb = kb_with_categories()
    titles = {hit.entry.title for hit in kb.search("aggregate string", limit=5)}
    assert titles == {"count alias", "ilike fix"}


def test_search_with_category_filters():
    kb = kb_with_categories()
    titles = [hit.entry.title for hit in kb.search("count", limit=5, category="aggregate")]
    assert titles == ["count alias"]
    titles = [hit.entry.title for hit in kb.search("count", limit=5, category="string")]
    assert titles == ["ilike fix"] or titles == []
