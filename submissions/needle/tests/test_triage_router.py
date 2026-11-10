"""TRIAGE search depth per caller visibility (needle.triage.depth_for_visibility / choose_depth, RCAC router).

Unit part: no DB. DB part (@pytest.mark.db): runs as NDL_SENIOR, NDL_JUNIOR and NDL_P10 (passwords from needle/.env
or the environment as NDL_<ROLE>_PASSWORD; skipped when missing).
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from needle.bm25 import query_terms  # noqa: E402
from needle.triage import (SQL0901N_DEPTHS, TRIAGE_APPROX_DEPTH, TRIAGE_DEEP_DEPTH,  # noqa: E402
                           depth_for_visibility)

TOTAL = 26210


@pytest.mark.parametrize("visible, expected_depth, expected_reason", [
    (26210, TRIAGE_APPROX_DEPTH, "approx-index"),   # NDL_SENIOR
    (26183, TRIAGE_APPROX_DEPTH, "approx-index"),   # NDL_JUNIOR (all buckets, no embargo)
    (19632, TRIAGE_APPROX_DEPTH, "approx-index"),   # ~75 % visible: router APPROX 50
    (13001, TRIAGE_DEEP_DEPTH, "deep-exact"),       # ~50 %: router APPROX 100 -> deep (exact plan, not 100)
    (6570, TRIAGE_DEEP_DEPTH, "deep-exact"),        # ~25 %: router EXACT (visible <= 7000)
    (2616, TRIAGE_DEEP_DEPTH, "deep-exact"),        # ~10 %: router EXACT
    (0, TRIAGE_DEEP_DEPTH, "deep-exact"),           # nothing visible: exact
])
def test_depth_rule(visible, expected_depth, expected_reason):
    c = depth_for_visibility(visible, TOTAL, 10)
    assert (c.depth, c.reason) == (expected_depth, expected_reason)
    assert c.depth not in SQL0901N_DEPTHS


def test_depth_rule_large_k_and_never_sql0901n_depths():
    assert depth_for_visibility(TOTAL, TOTAL, 50).depth == 128   # k >= 50: deep
    assert depth_for_visibility(TOTAL, TOTAL, 80).depth == 160   # 2k
    for k in range(1, 200):
        for v in (TOTAL, 20000, 13000, 5000, 100):
            d = depth_for_visibility(v, TOTAL, k).depth
            assert d not in SQL0901N_DEPTHS and d >= k and d <= 1000


def _password(role):
    pw = os.environ.get(f"NDL_{role}_PASSWORD")
    if not pw:
        from dotenv import dotenv_values
        pw = dotenv_values(ROOT / ".env").get(f"NDL_{role}_PASSWORD")
    if not pw:
        pytest.skip(f"NDL_{role}_PASSWORD not set")
    return pw


@pytest.mark.db
@pytest.mark.parametrize("role, expected_depth, expected_reason", [
    ("SENIOR", TRIAGE_APPROX_DEPTH, "approx-index"),
    ("JUNIOR", TRIAGE_APPROX_DEPTH, "approx-index"),
    ("P10", TRIAGE_DEEP_DEPTH, "deep-exact"),
])
def test_router_depth_per_user(role, expected_depth, expected_reason):
    from needle.triage import call_triage_ex, choose_depth, connect

    if expected_reason == "approx-index":
        from conftest import skip_unless_full_corpus
        skip_unless_full_corpus()
    conn = connect(user=f"NDL_{role}", password=_password(role))
    try:
        c = choose_depth(conn, 10)
        assert c.session_user == f"NDL_{role}"
        assert (c.depth, c.reason) == (expected_depth, expected_reason), c
        # the visibility lookup is cached on the connection
        assert getattr(conn, "_needle_visibility")[0] == f"NDL_{role}"
        # a zero vector is not allowed by COSINE; use a stored embedding visible to this user as the query vector
        cur = conn.cursor()
        try:
            cur.execute("SELECT ADV_ID, VECTOR_SERIALIZE(EMB RETURNING CLOB(100K)) FROM NEEDLE.ADV_DOC "
                        "ORDER BY ADV_ID FETCH FIRST 1 ROWS ONLY")
            adv_id, emb = cur.fetchone()
        finally:
            cur.close()
        import json
        vec = json.loads(str(emb))
        hits, answered, choice = call_triage_ex(conn, vec, query_terms("remote code execution"), k=10, mode="HYBRID")
        assert choice.depth == expected_depth and answered in (expected_depth, 64, 128) and len(hits) == 10
        vhits, _, _ = call_triage_ex(conn, vec, [], k=10, mode="VEC")
        assert len(vhits) == 10 and vhits[0].adv_id == str(adv_id).strip()  # k rows, own vector first
        # explicit depth still overrides the router
        _, answered2, choice2 = call_triage_ex(conn, vec, [], k=10, depth=25, mode="VEC")
        assert choice2.reason == "explicit" and answered2 == 25
    finally:
        conn.close()
