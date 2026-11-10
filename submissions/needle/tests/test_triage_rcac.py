"""RCAC through NEEDLE.TRIAGE: NDL_JUNIOR must never receive an ADV_ID its row permission forbids. DB only.

Attack: for each forbidden advisory (embargoed, or ROW_BUCKET >= MAX_BUCKET) the junior user sends that advisory's
OWN stored embedding and its own summary terms, in HYBRID, KW and VEC mode. If any leg leaked, the forbidden id
would rank first. A positive control (a visible advisory found by its own vector) shows the test is not vacuous.

Prerequisites (owned by the rcac agent): NEEDLE.USER_ACCESS, the row permissions on ADV_DOC and POSTING,
EXECUTE on NEEDLE.TRIAGE_MODE for NDL_JUNIOR, and NDL_JUNIOR_PASSWORD in needle/.env or the environment.
The test skips (it does not pass) when a prerequisite is missing.
"""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from needle.bm25 import query_terms  # noqa: E402

pytestmark = pytest.mark.db
JUNIOR = "NDL_JUNIOR"
N_ATTACK = 5


def _junior_password():
    pw = os.environ.get("NDL_JUNIOR_PASSWORD")
    if not pw:
        try:
            from dotenv import dotenv_values
            pw = dotenv_values(ROOT / ".env").get("NDL_JUNIOR_PASSWORD")
        except ImportError:
            pw = None
    return pw


def _rows(cur, sql, params=()):
    cur.execute(sql, params)
    return cur.fetchall()


def _junior():
    from needle.triage import connect

    pw = _junior_password()
    if not pw:
        pytest.skip("NDL_JUNIOR_PASSWORD not set")
    return connect(user=JUNIOR, password=pw)


def _query_as(conn, sql, params=()):
    cur = conn.cursor()
    try:
        return _rows(cur, sql, params)
    finally:
        cur.close()


PUBLIC = "(EMBARGO_UNTIL IS NULL OR EMBARGO_UNTIL <= CURRENT TIMESTAMP)"
REVIEW_C1_ATTACK = ("WITH V (TERM, C) AS (SELECT TERM, COUNT(*) FROM NEEDLE.POSTING GROUP BY TERM) "
                    "SELECT T.TERM, T.DF, COALESCE(V.C, 0) FROM NEEDLE.TERM_DF T LEFT JOIN V ON V.TERM = T.TERM "
                    "WHERE T.DF > COALESCE(V.C, 0)")


@pytest.mark.parametrize("table", ["NEEDLE.TERM_DF", "NEEDLE.CORPUS_STATS"])
def test_junior_cannot_select_bm25_statistics(table):
    """(a) C1 fix: analysts have no SELECT on the BM25 statistics tables."""
    junior = _junior()
    try:
        with pytest.raises(Exception, match="SQL0551N"):
            _query_as(junior, f"SELECT COUNT(*) FROM {table}")
    finally:
        junior.close()


def test_junior_triage_still_returns_results_with_execute_only():
    """(b) BM25_SEARCH / TRIAGE_MODE run with EXECUTE only (the routines read TERM_DF / CORPUS_STATS)."""
    from needle.triage import connect

    admin = connect()
    try:
        c = _query_as(admin, "SELECT ADV_ID, VECTOR_SERIALIZE(EMB RETURNING CLOB(100K)), SUMMARY FROM NEEDLE.ADV_DOC "
                             f"WHERE {PUBLIC} AND ADV_ID LIKE 'PYSEC-%' ORDER BY ADV_ID FETCH FIRST 1 ROWS ONLY")
    finally:
        admin.close()
    junior = _junior()
    try:
        kw = _query_as(junior, "SELECT ADV_ID FROM TABLE(NEEDLE.BM25_SEARCH(CAST(? AS CLOB(32K)), 10)) AS B",
                       (json.dumps(query_terms("pyyaml arbitrary code execution")),))
        assert len(kw) == 10
        assert len(_triage_ids(junior, None, query_terms("pyyaml arbitrary code execution"), "KW")) == 50
        c_id = str(c[0][0]).strip()
        hyb = _triage_ids(junior, str(c[0][1]), query_terms(f"{c_id} {c[0][2] or ''}"), "HYBRID")
        assert c_id in hyb and len(hyb) == 50
    finally:
        junior.close()


def test_difference_attack_yields_empty_set():
    """(c) Regression for review C1: TERM_DF minus the postings NDL_JUNIOR can see must reveal nothing."""
    from needle.triage import connect

    junior = _junior()
    admin = connect()
    try:
        # 1. the review's exact one-statement attack is no longer possible for the analyst
        with pytest.raises(Exception, match="SQL0551N"):
            _query_as(junior, REVIEW_C1_ATTACK)
        # 2. even with TERM_DF in hand (read here by DB2INST1), global-minus-visible is empty
        term_df = dict(_query_as(admin, "SELECT TERM, DF FROM NEEDLE.TERM_DF"))
        visible = dict(_query_as(junior, "SELECT TERM, COUNT(*) FROM NEEDLE.POSTING GROUP BY TERM"))
        leaked = {t for t, df in term_df.items() if int(df) > int(visible.get(t, 0))}
        assert leaked == set(), f"{len(leaked)} terms leak through TERM_DF"
        # 3. no term that occurs only in embargoed advisories is in TERM_DF; the embargoed IDs themselves included
        emb_only = {r[0] for r in _query_as(admin, f"SELECT DISTINCT TERM FROM NEEDLE.POSTING WHERE NOT {PUBLIC} "
                                                   f"EXCEPT SELECT TERM FROM NEEDLE.POSTING WHERE {PUBLIC}")}
        emb_ids = {str(r[0]).strip().lower() for r in _query_as(admin, f"SELECT ADV_ID FROM NEEDLE.ADV_DOC "
                                                                         f"WHERE NOT {PUBLIC}")}
        if not emb_ids:
            pytest.skip("no active embargo; nothing to attack")
        assert not (emb_only & set(term_df)), "TERM_DF contains embargoed-only terms"
        # 4. score oracle: BM25_SEARCH on embargoed-only advisory IDs returns nothing for the analyst
        probe = sorted(emb_ids & emb_only)[:30]
        assert probe, "no embargoed advisory ID is embargoed-only; the probe would be vacuous"
        for t in probe:
            got = _query_as(junior, "SELECT ADV_ID FROM TABLE(NEEDLE.BM25_SEARCH(CAST(? AS CLOB(32K)), 10)) AS B",
                            (json.dumps([t]),))
            assert got == [], (t, got)
    finally:
        admin.close()
        junior.close()


def _triage_ids(conn, qvec_json, terms, mode):
    cur = conn.cursor()
    try:
        cur.callproc("NEEDLE.TRIAGE_MODE", (qvec_json, json.dumps(terms), 50, 200, mode))
        return {str(r[0]).strip() for r in (cur.fetchall() or [])}
    finally:
        cur.close()


def test_junior_never_sees_forbidden_ids_through_triage():
    from needle.triage import connect

    pw = _junior_password()
    if not pw:
        pytest.skip("NDL_JUNIOR_PASSWORD not set")
    admin = connect()
    try:
        cur = admin.cursor()
        try:
            if not _rows(cur, "SELECT 1 FROM SYSCAT.TABLES WHERE TABSCHEMA = 'NEEDLE' AND TABNAME = 'USER_ACCESS'"):
                pytest.skip("NEEDLE.USER_ACCESS does not exist yet (rcac agent)")
            ua = _rows(cur, "SELECT MAX_BUCKET, SEES_EMBARGO FROM NEEDLE.USER_ACCESS WHERE AUTHID = ?", (JUNIOR,))
            if not ua:
                pytest.skip("NDL_JUNIOR has no NEEDLE.USER_ACCESS row")
            max_bucket, sees_embargo = int(ua[0][0]), int(ua[0][1])
            forbidden_sql = ("SELECT ADV_ID, SUMMARY, VECTOR_SERIALIZE(EMB RETURNING CLOB(100K)) FROM NEEDLE.ADV_DOC "
                             "WHERE {} ORDER BY ADV_ID FETCH FIRST " + str(N_ATTACK) + " ROWS ONLY")
            attacks = _rows(cur, forbidden_sql.format("ROW_BUCKET >= ?"), (max_bucket,))
            if not sees_embargo:
                attacks += _rows(cur, forbidden_sql.format("EMBARGO_UNTIL > CURRENT TIMESTAMP"))
            if not attacks:
                pytest.skip("the admin connection sees no forbidden rows; cannot build attack queries")
            control = _rows(cur, "SELECT ADV_ID, VECTOR_SERIALIZE(EMB RETURNING CLOB(100K)) FROM NEEDLE.ADV_DOC "
                                 "WHERE ROW_BUCKET < ? AND (EMBARGO_UNTIL IS NULL OR EMBARGO_UNTIL <= CURRENT TIMESTAMP) "
                                 "ORDER BY ADV_ID FETCH FIRST 1 ROWS ONLY", (max_bucket,))
        finally:
            cur.close()
    finally:
        admin.close()

    junior = connect(user=JUNIOR, password=pw)
    try:
        forbidden = {str(a).strip() for a, _, _ in attacks}
        for adv_id, summary, emb in attacks:
            terms = query_terms(f"{adv_id} {summary or ''}")
            for mode in ("HYBRID", "KW", "VEC"):
                got = _triage_ids(junior, str(emb), terms, mode)
                assert not (got & forbidden), (mode, adv_id, sorted(got & forbidden))
        assert control, "no visible advisory for the positive control"
        c_id, c_emb = str(control[0][0]).strip(), str(control[0][1])
        assert c_id in _triage_ids(junior, c_emb, [], "VEC"), "positive control: visible advisory not returned"
    finally:
        junior.close()
