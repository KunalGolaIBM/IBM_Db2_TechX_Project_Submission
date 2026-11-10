"""The vector benchmark's clause corpus end to end at a small size: the shipped DDL, synthetic versions, the vector
index after the load, the four forms plus the forced ones, and the scratch schema dropped."""

from __future__ import annotations

import pytest

from asof import db, schema, vectorbench

pytestmark = pytest.mark.db2

TARGET = "ASOF_VBTEST"


@pytest.fixture(scope="module")
def corpus(admin_conn, settings, test_schema):  # test_schema installs AsOf's 32K tablespace
    container = vectorbench.find_db2_container(settings.db2_container)
    built = vectorbench.build_clause_corpus(admin_conn, settings, container, 1_500, target=TARGET)
    yield admin_conn, container, built
    schema.drop(admin_conn, TARGET)
    db.use_schema(admin_conn, test_schema)


def test_the_corpus_is_the_shipped_table_with_several_versions_per_clause(corpus):
    conn, _, built = corpus
    assert built["rows"] == 1_500 and built["clause_ids"] < 600
    assert vectorbench.clause_corpus_ready(conn, 1_500, TARGET)
    assert not vectorbench.clause_corpus_ready(conn, 1_501, TARGET)
    kinds = dict(db.query(conn, "SELECT INDNAME, INDEXTYPE FROM SYSCAT.INDEXES WHERE INDSCHEMA = ?", (TARGET,)))
    assert kinds["IX_CLAUSE_EMBEDDING"] == "VANN" and "IX_CLAUSE_DOC_ASOF" in kinds
    assert db.query(conn, "SELECT TEMPORALTYPE FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TABNAME = 'POLICY_CLAUSE'",
                    (TARGET,)) == [("B",)]
    many = db.query(conn, "SELECT COUNT(*) FROM (SELECT CLAUSE_ID FROM POLICY_CLAUSE GROUP BY CLAUSE_ID "
                          "HAVING COUNT(*) > 1) AS X")[0][0]
    assert many > 100


def test_every_form_answers_and_exact_returns_only_versions_in_force(corpus, settings):
    conn, container, _ = corpus
    owner = db.ident(settings.db2_admin_user)
    queries = vectorbench.clause_queries(vectorbench.clause_plan(1_500), 3)
    r = vectorbench.measure_clauses(conn, settings, container, TARGET, queries, owner)
    assert r["versions"] == 1_500 and r["queries"] == 3
    assert set(r["p50"]) == {name for name, *_ in vectorbench.CLAUSE_FORMS}
    assert all(0.0 <= v <= 1.0 for v in r["recall"].values())
    assert r["timing"] == ("db2batch" if container else "client")
    assert not r["index_used"]["exact_on"] and not r["index_used"]["exact_all"]
    assert r["index_used"]["forced_on_100"] and r["index_used"]["forced_on_200"]  # the guideline is honoured
    db.use_schema(conn, TARGET)
    for vec, on, doc in queries:
        rows = db.query(conn, vectorbench.SQL_CLAUSE_EXACT_ON, (vec, on, doc, 10))
        assert rows and all(row[6] <= on < row[7] for row in rows)


def test_db2batch_failures_are_loud(corpus, settings):
    _, container, _ = corpus
    if container is None:
        pytest.skip("db2batch runs inside the Db2 container")
    with pytest.raises(RuntimeError, match="db2batch failed"):
        vectorbench.server_ms(settings, container, TARGET, [("x", "SELECT NO_SUCH_COLUMN FROM POLICY_CLAUSE", ())])


# The forced form with a search list just past the largest that runs under a date predicate.
SQL_FORCED_ON_210 = vectorbench.SQL_CLAUSE_FORCED_ON_200.replace("SEARCH_LIST_SIZE='200'", "SEARCH_LIST_SIZE='210'")
SQL_FORCED_ALL_1000 = (vectorbench.SQL_CLAUSE_APPROX_ALL + " /* <OPTGUIDELINES><IXSCAN TABID='Q1' "
                       "INDEX='IX_CLAUSE_EMBEDDING' SEARCH_LIST_SIZE='1000'/></OPTGUIDELINES> */")


def test_a_search_list_over_200_under_a_date_predicate_is_a_db2_internal_error(corpus):
    """Db2 12.1.5.0: forcing the vector index under FOR BUSINESS_TIME AS OF with SEARCH_LIST_SIZE 210 fails with
    SQL0901N ("Fetched nodes unexpectedly unsorted."); 200 runs, and so does 1,000 without a date predicate. If an
    upgrade fixes it, this test fails and docs/db2.md can drop the limit."""
    conn, _, _ = corpus
    db.use_schema(conn, TARGET)
    vec, on, doc = vectorbench.clause_queries(vectorbench.clause_plan(1_500), 1)[0]
    assert len(db.query(conn, vectorbench.SQL_CLAUSE_FORCED_ON_200, (vec, on, doc))) == 10
    assert len(db.query(conn, SQL_FORCED_ALL_1000, (vec, doc))) == 10
    with pytest.raises(db.DatabaseError) as err:
        db.query(conn, SQL_FORCED_ON_210, (vec, on, doc))
    conn.rollback()
    assert err.value.sqlcode == -901 and "Fetched nodes unexpectedly unsorted" in str(err.value)
