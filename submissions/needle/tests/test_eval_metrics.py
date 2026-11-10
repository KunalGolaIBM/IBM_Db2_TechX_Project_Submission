"""Unit tests for eval/run_eval.py metric and SQL-builder functions (no DB, no Ollama)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))
import run_eval as ev  # noqa: E402

GT = ["GHSA-aaaa-bbbb-cccc", "PYSEC-2021-1"]


def test_first_hit_rank():
    assert ev.first_hit_rank(["x", "y", "PYSEC-2021-1"], GT) == 3
    assert ev.first_hit_rank(["x", "y"], GT) is None
    assert ev.first_hit_rank([], GT) is None


def test_recall_at_k_counts_any_duplicate_as_correct():
    ranked = ["x", "PYSEC-2021-1", "y", "z"]
    assert ev.recall_at(ranked, GT, 1) == 0.0
    assert ev.recall_at(ranked, GT, 3) == 1.0
    assert ev.recall_at(["GHSA-aaaa-bbbb-cccc"], GT, 1) == 1.0


def test_reciprocal_rank_and_cutoff():
    assert ev.reciprocal_rank(["x", "PYSEC-2021-1"], GT) == pytest.approx(0.5)
    ranked = [f"d{i}" for i in range(10)] + ["PYSEC-2021-1"]  # rank 11 is outside the top 10
    assert ev.reciprocal_rank(ranked, GT) == 0.0


def test_set_recall():
    assert ev.set_recall_at(["PYSEC-2021-1", "GHSA-aaaa-bbbb-cccc"], GT, 10) == 1.0
    assert ev.set_recall_at(["PYSEC-2021-1"], GT, 10) == 0.5
    assert ev.set_recall_at(["x"], [], 10) == 0.0


def test_overlap_at():
    exact = [f"d{i}" for i in range(10)]
    assert ev.overlap_at(exact, exact) == 1.0
    assert ev.overlap_at(exact[:5] + ["n1", "n2", "n3", "n4", "n5"], exact) == 0.5
    assert ev.overlap_at(["a"], []) is None
    # filtered search may return fewer than k rows: denominator is the exact list
    assert ev.overlap_at(["d0", "d1"], ["d0", "d1", "d2", "d3"]) == 0.5


def test_percentile_matches_numpy_linear():
    vals = [5.0, 1.0, 3.0, 2.0, 4.0]
    assert ev.percentile(vals, 50) == 3.0
    assert ev.percentile(vals, 95) == pytest.approx(4.8)
    assert ev.percentile([], 50) is None
    assert ev.percentile([7.0], 95) == 7.0


def test_rrf_fuse_order_and_ties():
    a = ["d1", "d2", "d3"]
    b = ["d2", "d4", "d1"]
    fused = ev.rrf_fuse([a, b], k_rrf=60, top=10)
    assert fused[0] == "d2"  # 1/62 + 1/61 beats 1/61 + 1/63
    assert fused[1] == "d1"
    assert set(fused) == {"d1", "d2", "d3", "d4"}
    assert ev.rrf_fuse([["b"], ["a"]], top=2) == ["a", "b"]  # equal score -> adv_id order


def test_summarize_relevance():
    rows = [
        {"ranked": ["PYSEC-2021-1"], "gt": GT, "latency_ms": 10.0, "error": None},
        {"ranked": ["x", "y", "GHSA-aaaa-bbbb-cccc"], "gt": GT, "latency_ms": 20.0, "error": None},
        {"ranked": [], "gt": GT, "latency_ms": 30.0, "error": "boom"},
        {"ranked": ["x"], "gt": [], "latency_ms": 40.0, "error": None},  # gt not visible: not scored
    ]
    s = ev.summarize_relevance(rows)
    assert s["n"] == 3
    assert s["errors"] == 1
    assert s["recall@1"] == pytest.approx(1 / 3, abs=1e-4)
    assert s["recall@3"] == pytest.approx(2 / 3, abs=1e-4)
    assert s["mrr@10"] == pytest.approx((1 + 1 / 3) / 3, abs=1e-4)
    assert s["latency_p50_ms"] == 20.0  # error row excluded from latency


def test_vector_sql_uses_literal_k_and_bound_vector():
    sql = ev.vector_sql("APPROX", 10)
    assert "FETCH APPROX FIRST 10 ROWS ONLY" in sql
    assert "VECTOR(CAST(? AS CLOB(100K)), 768, FLOAT32)" in sql
    assert sql.count("?") == 1
    assert "WHERE ROW_BUCKET < 50" in ev.vector_sql("EXACT", 10, 50)
    with pytest.raises(ValueError):
        ev.vector_sql("APPROX", "10; DROP TABLE X")
    with pytest.raises(ValueError):
        ev.vector_sql("FAST", 10)


def test_query_terms_use_the_shared_bm25_analyzer():
    terms = ev.query_terms("The PyYAML loader lets an attacker run code via yaml.load")
    assert "pyyaml" in terms and "yaml.load" in terms and "yaml" in terms
    assert "the" not in terms and "an" not in terms  # stop words dropped by needle.bm25
    assert len(terms) == len(set(terms))


def test_saved_query_vectors_roundtrip(tmp_path):
    qs = [{"qid": "named:A", "query": "x one"}, {"qid": "named:B", "query": "y two"}]
    vecs = {"named:A": [0.1] * 3, "named:B": [0.2] * 3}
    p = tmp_path / "v.json.gz"
    ev.save_qvecs(p, qs, vecs, [5.0, 6.0], {"model": "m"}, {"named": {"sha256": "abc"}})
    got, lat, info = ev.load_qvecs(p, qs)
    assert got == vecs and lat == [5.0, 6.0] and info["model"] == "m"
    with pytest.raises(SystemExit):  # a changed query text is refused
        ev.load_qvecs(p, [{"qid": "named:A", "query": "x CHANGED"}])
