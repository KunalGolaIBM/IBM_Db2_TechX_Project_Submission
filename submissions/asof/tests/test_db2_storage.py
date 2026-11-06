"""Storage design in the catalog: dedicated 32K tablespace, the native vector index, compression."""

from __future__ import annotations

from datetime import date

import pytest

from asof import db
from asof.retriever import SQL_AS_OF, clauses_as_of

pytestmark = pytest.mark.db2

ALL_TABLES = ("POLICY_DOC", "POLICY_CLAUSE", "POLICY_CLAUSE_HIST", "ANSWER_LEDGER", "CLAIM_CITATION",
              "CHAIN_HEAD", "PUBLISHED_ANSWER")


def test_every_asof_table_lives_in_the_32k_tablespace(admin_conn, test_schema):
    rows = dict(db.query(admin_conn, "SELECT TABNAME, TBSPACE FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TYPE = 'T'",
                         (test_schema,)))
    assert {t: rows.get(t, "").strip() for t in ALL_TABLES} == {t: "ASOF_TS32K" for t in ALL_TABLES}
    page = db.query(admin_conn, "SELECT PAGESIZE FROM SYSCAT.TABLESPACES WHERE TBSPACE = 'ASOF_TS32K'")[0][0]
    assert page == 32768


def test_policy_embeddings_have_a_native_vector_index(admin_conn, test_schema):
    rows = db.query(admin_conn, "SELECT INDNAME, INDEXTYPE, COLNAMES FROM SYSCAT.INDEXES WHERE INDSCHEMA = ? "
                                "AND TABNAME = 'POLICY_CLAUSE' AND INDEXTYPE = 'VANN'", (test_schema,))
    assert [(r[0].strip(), r[2].strip()) for r in rows] == [("IX_CLAUSE_EMBEDDING", "+EMBEDDING")]
    ts = db.query(admin_conn, "SELECT T.TBSPACE FROM SYSCAT.INDEXES I JOIN SYSCAT.TABLESPACES T ON T.TBSPACEID = I.TBSPACEID "
                              "WHERE I.INDSCHEMA = ? AND I.INDNAME = 'IX_CLAUSE_EMBEDDING'", (test_schema,))
    assert ts[0][0].strip() == "ASOF_TS32K"


def test_ledger_tables_use_adaptive_row_compression(admin_conn, test_schema):
    rows = dict((r[0].strip(), (r[1], r[2])) for r in db.query(
        admin_conn, "SELECT TABNAME, COMPRESSION, ROWCOMPMODE FROM SYSCAT.TABLES WHERE TABSCHEMA = ? "
                    "AND TABNAME IN ('ANSWER_LEDGER', 'CLAIM_CITATION')", (test_schema,)))
    assert rows == {"ANSWER_LEDGER": ("R", "A"), "CLAIM_CITATION": ("R", "A")}


def test_the_temporal_query_asks_for_exact_ranking():
    # With a vector index, Db2's default is approximate; the in-force version must never be missed.
    assert "FETCH EXACT FIRST ? ROWS ONLY" in SQL_AS_OF


def test_retrieval_with_the_index_present_still_ranks_every_clause_in_force(app_conn, embeddings, test_schema):
    vec = embeddings.embed_query("You can get the bereavement fare after you travel.")
    for day, want in ((date(2026, 3, 10), "v1"), (date(2026, 6, 2), "v2")):
        found = clauses_as_of(app_conn, vec, day, "AURELIA-CSP", k=10, schema=test_schema)
        assert len(found) == 10
        assert {c.clause_id: c.version_label for c in found}.get("BRV-002") == want
        assert [c.distance for c in found] == sorted(c.distance for c in found)
