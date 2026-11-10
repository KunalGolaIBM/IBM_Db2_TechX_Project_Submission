"""Db2 12.1.5 and ibm_db behaviours AsOf's design depends on, pinned on the database the suite runs against.

Each test is one finding from the README's "What building AsOf taught us about Db2". If a Db2 or driver upgrade
changes the behaviour, the test fails and the workaround in the code can go.
"""

from __future__ import annotations

import pytest

from asof import db, schema

pytestmark = pytest.mark.db2

SCHEMA = "ASOF_FINDINGS"


@pytest.fixture(scope="module")
def conn(admin_conn, test_schema):  # test_schema installs AsOf's 32K tablespace
    schema.drop(admin_conn, SCHEMA)
    db.use_schema(admin_conn, SCHEMA)
    yield admin_conn
    schema.drop(admin_conn, SCHEMA)
    db.use_schema(admin_conn, test_schema)


def _refused(conn, sql: str) -> db.DatabaseError:
    with pytest.raises(db.DatabaseError) as err:
        db.query(conn, sql)
    conn.rollback()
    return err.value


def test_json_table_takes_only_strict_dollar_as_its_row_path(conn):
    """So CLAIMS_FROM_JSON reads each array position with a literal index instead of 'lax $.claims[*]'."""
    ok = "SELECT T.X FROM JSON_TABLE('{\"a\":[1,2]}', 'strict $' COLUMNS (X INTEGER PATH '$.a[1]') ERROR ON ERROR) AS T"
    assert db.query(conn, ok) == [(2,)]
    for sql in ("SELECT T.X FROM JSON_TABLE('{\"a\":[1,2]}', 'lax $.a[*]' COLUMNS (X INTEGER PATH '$') "
                "ERROR ON ERROR) AS T",
                "SELECT T.X FROM JSON_TABLE('{\"a\":[1,2]}', 'strict $.a[*]' COLUMNS (X INTEGER PATH '$') "
                "ERROR ON ERROR) AS T"):
        exc = _refused(conn, sql)
        assert (exc.sqlcode, exc.sqlstate) == (-104, "42601")
        assert 'Expected tokens may include:  "strict $"' in str(exc)


def test_json_table_needs_an_explicit_on_error_clause(conn):
    exc = _refused(conn, "SELECT T.X FROM JSON_TABLE('{\"a\":[1,2]}', 'strict $' COLUMNS (X INTEGER PATH '$.a[0]')) AS T")
    assert (exc.sqlcode, exc.sqlstate) == (-104, "42601") and "<json_table_on_error_clause>" in str(exc)


def test_ibm_db_cannot_return_a_null_integer_out_parameter(conn):
    """CLI0110E for a NULL INTEGER OUT value, while a NULL VARCHAR comes back as None. VERIFY_CHAIN therefore reports
    first_bad_id 0 when no row is bad, and ledger.verify_chain maps 0 back to None."""
    db.execute(conn, "CREATE OR REPLACE PROCEDURE P_NULL_INT (OUT P_N INTEGER) LANGUAGE SQL BEGIN SET P_N = NULL; END")
    db.execute(conn, "CREATE OR REPLACE PROCEDURE P_NULL_STR (OUT P_S VARCHAR(20)) LANGUAGE SQL "
                     "BEGIN SET P_S = NULL; END")
    conn.commit()
    cur = conn.cursor()
    try:
        with pytest.raises(Exception, match="CLI0110E"):
            cur.callproc("P_NULL_INT", (0,))
        assert cur.callproc("P_NULL_STR", (" " * 20,)) == (None,)
    finally:
        cur.close()


def test_a_vector_index_on_384_float32_dimensions_needs_more_than_a_4k_page(conn):
    """Why every AsOf table lives in the 32K tablespace ASOF_TS32K."""
    db.execute(conn, "CREATE TABLE V4K (ID INTEGER NOT NULL PRIMARY KEY, E VECTOR(384, FLOAT32)) IN USERSPACE1")
    db.execute(conn, "CREATE TABLE V32K (ID INTEGER NOT NULL PRIMARY KEY, E VECTOR(384, FLOAT32)) IN ASOF_TS32K")
    conn.commit()
    with pytest.raises(db.DatabaseError) as err:
        db.execute(conn, "CREATE VECTOR INDEX IX_V4K ON V4K (E) WITH DISTANCE COSINE")
    conn.rollback()
    assert (err.value.sqlcode, err.value.sqlstate) == (-614, "54008")
    db.execute(conn, "CREATE VECTOR INDEX IX_V32K ON V32K (E) WITH DISTANCE COSINE IN ASOF_TS32K")
    conn.commit()
    assert db.query(conn, "SELECT INDEXTYPE FROM SYSCAT.INDEXES WHERE INDSCHEMA = ? AND INDNAME = 'IX_V32K'",
                    (SCHEMA,)) == [("VANN",)]
