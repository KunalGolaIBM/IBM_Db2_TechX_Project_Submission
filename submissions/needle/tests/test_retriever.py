"""Unit tests (no DB): candidate ranking per mode, RCAC-router depth wiring, LangChain retriever wiring."""
import pytest

from needle import retriever as R

CANDS = [
    {"ADV_ID": "A", "RRF": 1 / 61 + 1 / 63, "KW_RANK": 1, "VEC_RANK": 3, "VEC_DIST": 0.30},
    {"ADV_ID": "B", "RRF": 1 / 61, "KW_RANK": None, "VEC_RANK": 1, "VEC_DIST": 0.10},
    {"ADV_ID": "C", "RRF": 1 / 62 + 1 / 62, "KW_RANK": 2, "VEC_RANK": 2, "VEC_DIST": 0.20},
    {"ADV_ID": "D", "RRF": 1 / 63, "KW_RANK": 3, "VEC_RANK": None, "VEC_DIST": None},
]


def ids(rows):
    return [r["ADV_ID"] for r in rows]


def test_top_candidates_per_mode():
    assert ids(R.top_candidates(CANDS, "keyword", 10)) == ["A", "C", "D"]
    assert ids(R.top_candidates(CANDS, "vector", 10)) == ["B", "C", "A"]
    assert ids(R.top_candidates(CANDS, "hybrid", 2)) == ["A", "C"]
    with pytest.raises(ValueError):
        R.top_candidates(CANDS, "bogus", 3)


def test_ranked_hides_ids_the_user_cannot_read():
    run = R.TriageRun("q", "NDL_JUNIOR", candidates=CANDS, docs={"B": {}, "C": {}}, k=10)
    assert ids(run.ranked("hybrid")) == ["C", "B"]
    assert ids(run.ranked("keyword")) == ["C"]


def _fake_dbi(monkeypatch):
    import ibm_db_dbi

    monkeypatch.setattr(ibm_db_dbi, "Connection", lambda handle: ("dbi", handle))


def test_router_depth_uses_the_users_k_and_widens_p_k(monkeypatch):
    from needle import triage as T

    _fake_dbi(monkeypatch)
    seen = {}

    def fake_choose(conn, k):
        seen["router_k"] = k
        return T.DepthChoice(50, "approx-index", "NDL_SENIOR", 26210, 26210, "APPROX", 50)

    def fake_call_ex(conn, qvec, terms, k=10, depth=None, mode="HYBRID"):
        seen.update(p_k=k, depth=depth, mode=mode)
        return [T.TriageHit("A", 0.03, 1, 2, 0.1)], depth, None

    monkeypatch.setattr(T, "choose_depth", fake_choose)
    monkeypatch.setattr(T, "call_triage_ex", fake_call_ex)
    rows, path, info = R._call_triage(object(), [0.0] * 768, ["yaml"], 10, None)
    assert seen == {"router_k": 10, "p_k": 100, "depth": 50, "mode": "HYBRID"}  # router sees k=10, not P_K
    assert info["reason"] == "approx-index" and info["depth"] == 50 and info["visible_rows"] == 26210
    assert rows[0]["ADV_ID"] == "A" and "TRIAGE_MODE" in path


def test_missing_triage_is_a_clear_error_not_a_fallback(monkeypatch):
    from needle import triage as T

    _fake_dbi(monkeypatch)

    def boom(*a, **kw):
        raise Exception("[IBM][CLI Driver][DB2/LINUXX8664] SQL0440N No authorized routine named TRIAGE_MODE")

    monkeypatch.setattr(T, "choose_depth", lambda conn, k: T.DepthChoice(50, "approx-index"))
    monkeypatch.setattr(T, "call_triage_ex", boom)
    with pytest.raises(R.Db2Unavailable, match="required object"):
        R._call_triage(object(), [0.0] * 768, ["yaml"], 10, None)
    assert not hasattr(R, "fallback_sql")  # no direct SQL on TERM_DF / CORPUS_STATS any more


def test_retriever_returns_documents_with_metadata(monkeypatch):
    docs = {c["ADV_ID"]: {"SUMMARY": f"sum {c['ADV_ID']}", "DETAILS": "d", "PACKAGES_LIST": ["pyyaml"],
                          "ALIASES": ["CVE-1"], "KIND": "GHSA"} for c in CANDS}
    seen = {}

    def fake_run(conn, query, authid="", k=10, depth=None):
        seen.update(conn=conn, authid=authid, k=k)
        return R.TriageRun(query, authid, path="CALL NEEDLE.TRIAGE", candidates=CANDS, docs=docs, k=k)

    monkeypatch.setattr(R, "run_triage", fake_run)
    sentinel = object()
    r = R.Db2HybridRetriever(conn=sentinel, authid="NDL_JUNIOR", k=2, mode="vector")
    out = r.invoke("yaml loader rce")
    assert seen["conn"] is sentinel and seen["authid"] == "NDL_JUNIOR"  # caller's own connection
    assert [d.metadata["adv_id"] for d in out] == ["B", "C"]
    assert out[0].metadata["vec_rank"] == 1 and out[0].metadata["kw_rank"] is None
    assert out[1].metadata["rrf"] == pytest.approx(2 / 62)
    assert out[0].page_content.startswith("sum B")
    assert r.last_run is not None and r.last_run.path == "CALL NEEDLE.TRIAGE"
