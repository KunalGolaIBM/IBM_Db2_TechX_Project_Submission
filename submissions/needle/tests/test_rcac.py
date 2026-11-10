"""RCAC tests.

Unit tests (router decisions, SQL builder safety) run without a database.
DB tests (pytest -m db) use REAL, separate Db2 identities (NDL_SENIOR, NDL_JUNIOR, NDL_P10; passwords from needle/.env)
after sql/04_rcac.sql has been applied. No test filters rows in Python: every check asks Db2 as that identity.
Positive controls (NDL_SENIOR sees the embargoed advisory) prove each leak check could fail.
"""
from __future__ import annotations

import json

import pytest

from needle.rcac import RouterConfig, choose_strategy, knn_sql

N = 26210


# ----------------------------------------------------------------------------------------------- unit (no DB)
def test_small_visible_set_goes_exact():
    s = choose_strategy(1500, N, 10, RouterConfig(exact_max_rows=2000))
    assert (s.mode, s.depth, s.search_list_size) == ("EXACT", 10, None)


def test_depth_rounds_up_to_a_fixed_statement_and_sets_search_list():
    s = choose_strategy(6552, N, 10, RouterConfig(exact_max_rows=2000, overfetch=1.0))  # 25 % visible -> need 40
    assert (s.mode, s.depth, s.search_list_size) == ("APPROX", 50, 150)


def test_full_visibility_uses_plain_k():
    s = choose_strategy(N, N, 10, RouterConfig(exact_max_rows=2000, overfetch=1.0))
    assert (s.mode, s.depth, s.search_list_size) == ("APPROX", 10, 50)


def test_need_beyond_largest_statement_goes_exact():
    s = choose_strategy(2700, N, 10, RouterConfig(exact_max_rows=2000, overfetch=3.0))  # need 292 > 200
    assert s.mode == "EXACT"


def test_missing_statistics_or_nothing_visible_goes_exact():
    assert choose_strategy(5000, -1, 10).mode == "EXACT"
    assert choose_strategy(0, N, 10).mode == "EXACT"


def test_knn_sql_literal_depth_guideline_and_bound_vector():
    sql = knn_sql("NEEDLE.ADV_DOC", 50, True, id_col="ADV_ID", search_list_size=150)
    assert "FETCH APPROX FIRST 50 ROWS ONLY" in sql
    assert "<IXSCAN TABLE='T' SEARCH_LIST_SIZE='150'/>" in sql
    assert sql.count("?") == 2  # the query vector is always bound, never inlined


def test_knn_sql_exact_has_no_guideline():
    sql = knn_sql("NEEDLE.ADV_DOC", 10, False, id_col="ADV_ID", search_list_size=150)
    assert "FETCH EXACT FIRST 10 ROWS ONLY" in sql and "OPTGUIDELINES" not in sql


@pytest.mark.parametrize("table,col", [("NEEDLE.ADV_DOC; DROP TABLE X", "ADV_ID"),
                                       ("NEEDLE.ADV_DOC", "ADV_ID FROM SYSCAT.TABLES --")])
def test_knn_sql_rejects_unsafe_identifiers(table, col):
    with pytest.raises(ValueError):
        knn_sql(table, 10, True, id_col=col)


def test_knn_sql_filter_is_a_validated_integer_only():
    assert "WHERE ROW_BUCKET < 10 ORDER BY" in knn_sql("NEEDLE.ADV_DOC", 10, True, id_col="ADV_ID", max_bucket=10)
    for bad in ("10 OR 1=1", 101, -1, 9.5):
        with pytest.raises((ValueError, TypeError)):
            knn_sql("NEEDLE.ADV_DOC", 10, True, id_col="ADV_ID", max_bucket=bad)


def test_knn_sql_rejects_non_integer_depth():
    with pytest.raises(ValueError):
        knn_sql("NEEDLE.ADV_DOC", "10 ROWS ONLY --", True)


# ----------------------------------------------------------------------------------------------- DB (real identities)
def _rows(conn, sql, params=None):
    import ibm_db

    if params:
        st = ibm_db.prepare(conn, sql)
        ibm_db.execute(st, tuple(params))
    else:
        st = ibm_db.exec_immediate(conn, sql)
    out, r = [], ibm_db.fetch_tuple(st)
    while r:
        out.append(r)
        r = ibm_db.fetch_tuple(st)
    ibm_db.free_stmt(st)
    return out


@pytest.fixture(scope="module")
def conns():
    import ibm_db

    from needle.sbom import connect_as

    opened = {}
    try:
        for a in ("NDL_SENIOR", "NDL_JUNIOR", "NDL_P10"):
            opened[a] = connect_as(a, timeout_s=30)
        yield opened
    finally:
        for c in opened.values():
            ibm_db.close(c)


@pytest.fixture(scope="module")
def embargoed(conns):
    """Embargoed advisories as NDL_SENIOR sees them: (ADV_ID, SUMMARY, vector list)."""
    rs = _rows(conns["NDL_SENIOR"],
               "SELECT ADV_ID, COALESCE(SUMMARY, ''), VECTOR_SERIALIZE(EMB RETURNING CLOB(100K)) FROM NEEDLE.ADV_DOC "
               "WHERE EMBARGO_UNTIL > CURRENT TIMESTAMP ORDER BY ADV_ID")
    assert len(rs) >= 25, "sql/04_rcac.sql step 2 should embargo at least 25 advisories"
    return [(str(a).strip(), s, json.loads(v)) for a, s, v in rs]


def _ids_in(conn, sql, ids):
    marks = ",".join("?" * len(ids))
    return {str(r[0]).strip() for r in _rows(conn, sql.format(marks=marks), ids)}


@pytest.mark.db
def test_each_connection_is_a_distinct_db2_identity(conns):
    for authid, c in conns.items():
        su = str(_rows(c, "SELECT SESSION_USER FROM SYSIBM.SYSDUMMY1")[0][0]).strip()
        assert su == authid


@pytest.mark.db
def test_junior_never_sees_embargoed_rows(conns, embargoed):
    ids = [e[0] for e in embargoed]
    assert _ids_in(conns["NDL_SENIOR"], "SELECT ADV_ID FROM NEEDLE.ADV_DOC WHERE ADV_ID IN ({marks})", ids) == set(ids)
    assert _ids_in(conns["NDL_JUNIOR"], "SELECT ADV_ID FROM NEEDLE.ADV_DOC WHERE ADV_ID IN ({marks})", ids) == set()
    n_sen = _rows(conns["NDL_SENIOR"], "SELECT COUNT(*) FROM NEEDLE.ADV_DOC")[0][0]
    n_jun = _rows(conns["NDL_JUNIOR"], "SELECT COUNT(*) FROM NEEDLE.ADV_DOC")[0][0]
    assert n_sen - n_jun == len(ids)


CRAFTED = [
    "SELECT ADV_ID FROM NEEDLE.ADV_DOC WHERE ADV_ID IN ({marks}) OR 1 = 1",
    "SELECT ADV_ID FROM NEEDLE.ADV_DOC WHERE EMBARGO_UNTIL IS NOT NULL AND ADV_ID IN ({marks})",
    "WITH X AS (SELECT * FROM NEEDLE.ADV_DOC) SELECT ADV_ID FROM X WHERE ADV_ID IN ({marks})",
    "SELECT ADV_ID FROM NEEDLE.ADV_DOC WHERE ADV_ID IN ({marks}) UNION ALL "
    "SELECT ADV_ID FROM NEEDLE.ADV_DOC WHERE ROW_BUCKET >= 0",
    "SELECT D.ADV_ID FROM NEEDLE.ADV_DOC D JOIN NEEDLE.ADV_DOC E ON D.CANON_ID = E.CANON_ID WHERE D.ADV_ID IN ({marks})",
    "SELECT DISTINCT ADV_ID FROM NEEDLE.POSTING WHERE ADV_ID IN ({marks})",
    "SELECT ADV_ID FROM NEEDLE.ADV_ALIAS WHERE ADV_ID IN ({marks})",
    "SELECT ADV_ID FROM NEEDLE.ADV_AFFECTED WHERE ADV_ID IN ({marks})",
]


@pytest.mark.db
@pytest.mark.parametrize("sql", CRAFTED)
def test_crafted_queries_do_not_bypass_the_permission(conns, embargoed, sql):
    ids = [e[0] for e in embargoed]
    got = _ids_in(conns["NDL_JUNIOR"], sql, ids)
    assert not (got & set(ids)), f"junior saw embargoed IDs via: {sql}"


POLICY_ATTACKS = [
    "SELECT * FROM NEEDLE.USER_ACCESS",
    "UPDATE NEEDLE.USER_ACCESS SET SEES_EMBARGO = 1 WHERE AUTHID = SESSION_USER",
    "INSERT INTO NEEDLE.USER_ACCESS VALUES ('NDL_JUNIOR2', 100, 1)",
    "ALTER TABLE NEEDLE.ADV_DOC DEACTIVATE ROW ACCESS CONTROL",
    "ALTER PERMISSION NEEDLE.ADV_DOC_ROWS DISABLE",
    "DROP MASK NEEDLE.ADV_DOC_SUMMARY_MASK",
    "SET SESSION AUTHORIZATION = 'NDL_SENIOR'",
    "UPDATE NEEDLE.ADV_DOC SET EMBARGO_UNTIL = NULL",
    "SELECT COUNT(*) FROM NEEDLE.ADV_RAW",
]


@pytest.mark.db
@pytest.mark.parametrize("sql", POLICY_ATTACKS)
def test_junior_cannot_change_or_read_the_policy(conns, sql):
    import ibm_db

    with pytest.raises(Exception):
        st = ibm_db.exec_immediate(conns["NDL_JUNIOR"], sql)
        if st:
            ibm_db.fetch_tuple(st)


@pytest.mark.db
def test_vector_leg_never_returns_embargoed(conns, embargoed):
    """Most adversarial vector query: the embargoed advisory's own embedding (distance 0 for that row)."""
    ids = {e[0] for e in embargoed}
    for adv_id, _, vec in embargoed[:10]:
        qv = json.dumps(vec)
        for approx in (True, False):
            sql = knn_sql("NEEDLE.ADV_DOC", 10, approx, id_col="ADV_ID")
            jun = {str(r[0]).strip() for r in _rows(conns["NDL_JUNIOR"], sql, (qv, qv))}
            assert not (jun & ids)
            assert len(jun) > 0
        top = _rows(conns["NDL_SENIOR"], knn_sql("NEEDLE.ADV_DOC", 1, False, id_col="ADV_ID"), (qv, qv))
        assert str(top[0][0]).strip() in ids  # positive control: senior's exact top-1 is an embargoed row


@pytest.mark.db
def test_triage_never_returns_embargoed(conns, embargoed):
    import ibm_db_dbi

    from needle.bm25 import query_terms
    from needle.triage import call_triage

    ids = {e[0] for e in embargoed}
    jun = ibm_db_dbi.Connection(conns["NDL_JUNIOR"])
    sen = ibm_db_dbi.Connection(conns["NDL_SENIOR"])
    senior_hits = 0
    for adv_id, summary, vec in embargoed[:5]:
        terms = query_terms(summary) or ["vulnerability"]
        for mode in ("HYBRID", "KW", "VEC"):
            hits = call_triage(jun, vec, terms, k=10, depth=100, mode=mode)
            assert not ({h.adv_id for h in hits} & ids), f"TRIAGE {mode} leaked an embargoed ID to NDL_JUNIOR"
        senior_hits += len({h.adv_id for h in call_triage(sen, vec, terms, k=10, depth=100)} & ids)
    assert senior_hits > 0  # positive control


@pytest.mark.db
def test_details_mask_is_defined_enabled_and_active(conns, embargoed):
    c = conns["NDL_JUNIOR"]
    ctl = {str(r[0]).strip(): (str(r[1]).strip(), str(r[2]).strip(), str(r[3]).strip()) for r in _rows(
        c, "SELECT CONTROLNAME, CONTROLTYPE, ENABLE, VALID FROM SYSCAT.CONTROLS WHERE TABSCHEMA = 'NEEDLE'")}
    # Db2 12.1.5 rejects a mask on the CLOB column DETAILS (SQL0350N); SUMMARY carries the mask instead.
    assert ctl.get("ADV_DOC_SUMMARY_MASK") == ("C", "Y", "Y")
    for p in ("ADV_DOC_ROWS", "POSTING_ROWS", "ADV_ALIAS_ROWS", "ADV_AFFECTED_ROWS"):
        assert ctl.get(p) == ("R", "Y", "Y")
    control = str(_rows(c, "SELECT CONTROL FROM SYSCAT.TABLES WHERE TABSCHEMA = 'NEEDLE' AND TABNAME = 'ADV_DOC'")[0][0])
    assert control.strip() == "B"  # row and column access control both active
    ids = [e[0] for e in embargoed]
    assert _ids_in(c, "SELECT ADV_ID FROM NEEDLE.ADV_DOC WHERE ADV_ID IN ({marks}) AND (DETAILS IS NOT NULL "
                      "OR DETAILS IS NULL)", ids) == set()


@pytest.mark.db
def test_p10_sees_only_its_buckets(conns):
    from conftest import corpus_rows

    mx, n = _rows(conns["NDL_P10"], "SELECT MAX(ROW_BUCKET), COUNT(*) FROM NEEDLE.ADV_DOC")[0]
    assert mx is not None and int(mx) < 10
    total = corpus_rows() or N  # real corpus size (full or 2,000-row sample), not a hard-coded constant
    assert 0.05 < int(n) / total < 0.15
