"""Tests for embeddings and the in memory knowledge base."""

import pytest

from parity.kb.embeddings import HashingEmbedder, cosine_distance
from parity.kb.store import InMemoryKb, KnownDifference


def test_embedder_shape_and_stability():
    embedder = HashingEmbedder()
    first = embedder.embed("trailing space text comparison")
    second = embedder.embed("trailing space text comparison")
    assert len(first) == 384
    assert first == second


def test_embedder_empty_text():
    assert HashingEmbedder().embed("") == (0.0,) * 384


def test_embedder_rejects_bad_dim():
    with pytest.raises(ValueError):
        HashingEmbedder(dim=0)


def test_cosine_identical_is_zero():
    vector = HashingEmbedder().embed("null versus empty string")
    assert cosine_distance(vector, vector) == pytest.approx(0.0)


def test_cosine_different_is_larger():
    embedder = HashingEmbedder()
    same = embedder.embed("trailing space in varchar")
    close = embedder.embed("trailing space in text")
    far = embedder.embed("integer division rounding")
    assert cosine_distance(same, close) < cosine_distance(same, far)


def test_cosine_length_mismatch_rejected():
    with pytest.raises(ValueError):
        cosine_distance((1.0,), (1.0, 2.0))


def test_kb_search_only_verified():
    kb = InMemoryKb()
    kb.add(KnownDifference(title="t1", source_pattern="ILIKE", db2_pattern="UPPER LIKE"))
    kb.add(KnownDifference(title="t2", source_pattern="LIMIT", db2_pattern="FETCH", verified=True))
    results = kb.search("LIMIT fetch first rows")
    assert [r.entry.title for r in results] == ["t2"]


def test_kb_approve_then_search():
    kb = InMemoryKb()
    kb.add(KnownDifference(title="t1", source_pattern="ILIKE", db2_pattern="UPPER LIKE"))
    assert kb.search("ILIKE") == ()
    kb.approve("t1")
    assert len(kb.search("ILIKE")) == 1


def test_kb_reject_rules():
    kb = InMemoryKb()
    kb.add(KnownDifference(title="t1", source_pattern="x", db2_pattern="y"))
    kb.reject("t1")
    assert kb.search("x") == ()
    kb.add(KnownDifference(title="t2", source_pattern="x", db2_pattern="y", verified=True))
    with pytest.raises(ValueError, match="verified entries cannot be rejected"):
        kb.reject("t2")


def test_kb_unknown_title_rejected():
    kb = InMemoryKb()
    with pytest.raises(KeyError):
        kb.approve("missing")
    with pytest.raises(KeyError):
        kb.reject("missing")


def test_kb_search_limit():
    kb = InMemoryKb()
    for index in range(4):
        kb.add(
            KnownDifference(
                title=f"t{index}",
                source_pattern=f"pattern {index}",
                db2_pattern="fix",
                verified=True,
            )
        )
    assert len(kb.search("pattern", limit=2)) == 2
