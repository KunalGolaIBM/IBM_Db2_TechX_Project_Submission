"""Which distance metrics a native vector index accepts on Db2 12.1.5, pinned.

IBM documents six metrics for VECTOR_DISTANCE: COSINE, EUCLIDEAN, EUCLIDEAN_SQUARED, DOT, HAMMING and MANHATTAN.
CREATE VECTOR INDEX takes three of them for FLOAT32 vectors; DOT, HAMMING and MANHATTAN fail to parse (SQL0104N,
"Expected tokens may include: <vector_index_metric>"). For INT8 vectors COSINE is refused as well (SQL0628N), and an
index without WITH DISTANCE is refused (SQL0628N). AsOf's index is COSINE on FLOAT32, the one combination its query
needs. If a Db2 upgrade changes any of this, the test fails and docs/db2.md needs the new list.

The metric is a keyword, not a value, so every statement is a literal.
"""

from __future__ import annotations

import pytest

from asof import db, schema

pytestmark = pytest.mark.db2

SCHEMA = "ASOF_VMETRIC"
TABLES = ("CREATE TABLE VF (ID INTEGER NOT NULL PRIMARY KEY, E VECTOR(8, FLOAT32)) IN ASOF_TS32K",
          "CREATE TABLE VI (ID INTEGER NOT NULL PRIMARY KEY, E VECTOR(8, INT8)) IN ASOF_TS32K")
INDEX = {
    ("FLOAT32", "COSINE"): "CREATE VECTOR INDEX IX_F_COSINE ON VF (E) WITH DISTANCE COSINE IN ASOF_TS32K",
    ("FLOAT32", "EUCLIDEAN"): "CREATE VECTOR INDEX IX_F_EUCLIDEAN ON VF (E) WITH DISTANCE EUCLIDEAN IN ASOF_TS32K",
    ("FLOAT32", "EUCLIDEAN_SQUARED"):
        "CREATE VECTOR INDEX IX_F_EUCLIDEAN_SQ ON VF (E) WITH DISTANCE EUCLIDEAN_SQUARED IN ASOF_TS32K",
    ("FLOAT32", "DOT"): "CREATE VECTOR INDEX IX_F_DOT ON VF (E) WITH DISTANCE DOT IN ASOF_TS32K",
    ("FLOAT32", "HAMMING"): "CREATE VECTOR INDEX IX_F_HAMMING ON VF (E) WITH DISTANCE HAMMING IN ASOF_TS32K",
    ("FLOAT32", "MANHATTAN"): "CREATE VECTOR INDEX IX_F_MANHATTAN ON VF (E) WITH DISTANCE MANHATTAN IN ASOF_TS32K",
    ("FLOAT32", None): "CREATE VECTOR INDEX IX_F_NONE ON VF (E) IN ASOF_TS32K",
    ("INT8", "COSINE"): "CREATE VECTOR INDEX IX_I_COSINE ON VI (E) WITH DISTANCE COSINE IN ASOF_TS32K",
    ("INT8", "EUCLIDEAN"): "CREATE VECTOR INDEX IX_I_EUCLIDEAN ON VI (E) WITH DISTANCE EUCLIDEAN IN ASOF_TS32K",
    ("INT8", "EUCLIDEAN_SQUARED"):
        "CREATE VECTOR INDEX IX_I_EUCLIDEAN_SQ ON VI (E) WITH DISTANCE EUCLIDEAN_SQUARED IN ASOF_TS32K",
    ("INT8", "DOT"): "CREATE VECTOR INDEX IX_I_DOT ON VI (E) WITH DISTANCE DOT IN ASOF_TS32K",
    ("INT8", "HAMMING"): "CREATE VECTOR INDEX IX_I_HAMMING ON VI (E) WITH DISTANCE HAMMING IN ASOF_TS32K",
    ("INT8", "MANHATTAN"): "CREATE VECTOR INDEX IX_I_MANHATTAN ON VI (E) WITH DISTANCE MANHATTAN IN ASOF_TS32K",
}
# What Db2 12.1.5.0 does with each statement: None when it builds a VANN index, else (SQLCODE, SQLSTATE).
PARSE = (-104, "42601")       # SQL0104N An unexpected token "DOT" ... Expected tokens may include: "<vector_index_metric>"
CONFLICT = (-628, "42613")    # SQL0628N Multiple or conflicting keywords involving the "WITH DISTANCE COSINE" clause
EXPECTED: dict[tuple[str, str | None], tuple[int, str] | None] = {
    ("FLOAT32", "COSINE"): None, ("FLOAT32", "EUCLIDEAN"): None, ("FLOAT32", "EUCLIDEAN_SQUARED"): None,
    ("FLOAT32", "DOT"): PARSE, ("FLOAT32", "HAMMING"): PARSE, ("FLOAT32", "MANHATTAN"): PARSE,
    ("FLOAT32", None): CONFLICT,
    ("INT8", "COSINE"): CONFLICT, ("INT8", "EUCLIDEAN"): None, ("INT8", "EUCLIDEAN_SQUARED"): None,
    ("INT8", "DOT"): PARSE, ("INT8", "HAMMING"): PARSE, ("INT8", "MANHATTAN"): PARSE,
}
# VECTOR_DISTANCE itself takes all six documented metrics, for both coordinate types.
DISTANCE_SQL = {
    ("FLOAT32", "COSINE"): "VALUES VECTOR_DISTANCE(VECTOR('[1,0,0,0,0,0,0,1]', 8, FLOAT32), "
                           "VECTOR('[1,0,0,0,0,0,0,0]', 8, FLOAT32), COSINE)",
    ("FLOAT32", "EUCLIDEAN"): "VALUES VECTOR_DISTANCE(VECTOR('[1,0,0,0,0,0,0,1]', 8, FLOAT32), "
                              "VECTOR('[1,0,0,0,0,0,0,0]', 8, FLOAT32), EUCLIDEAN)",
    ("FLOAT32", "EUCLIDEAN_SQUARED"): "VALUES VECTOR_DISTANCE(VECTOR('[1,0,0,0,0,0,0,1]', 8, FLOAT32), "
                                      "VECTOR('[1,0,0,0,0,0,0,0]', 8, FLOAT32), EUCLIDEAN_SQUARED)",
    ("FLOAT32", "DOT"): "VALUES VECTOR_DISTANCE(VECTOR('[1,0,0,0,0,0,0,1]', 8, FLOAT32), "
                        "VECTOR('[1,0,0,0,0,0,0,0]', 8, FLOAT32), DOT)",
    ("FLOAT32", "HAMMING"): "VALUES VECTOR_DISTANCE(VECTOR('[1,0,0,0,0,0,0,1]', 8, FLOAT32), "
                            "VECTOR('[1,0,0,0,0,0,0,0]', 8, FLOAT32), HAMMING)",
    ("FLOAT32", "MANHATTAN"): "VALUES VECTOR_DISTANCE(VECTOR('[1,0,0,0,0,0,0,1]', 8, FLOAT32), "
                              "VECTOR('[1,0,0,0,0,0,0,0]', 8, FLOAT32), MANHATTAN)",
    ("INT8", "COSINE"): "VALUES VECTOR_DISTANCE(VECTOR('[1,0,0,0,0,0,0,1]', 8, INT8), "
                        "VECTOR('[1,0,0,0,0,0,0,0]', 8, INT8), COSINE)",
    ("INT8", "EUCLIDEAN"): "VALUES VECTOR_DISTANCE(VECTOR('[1,0,0,0,0,0,0,1]', 8, INT8), "
                           "VECTOR('[1,0,0,0,0,0,0,0]', 8, INT8), EUCLIDEAN)",
    ("INT8", "EUCLIDEAN_SQUARED"): "VALUES VECTOR_DISTANCE(VECTOR('[1,0,0,0,0,0,0,1]', 8, INT8), "
                                   "VECTOR('[1,0,0,0,0,0,0,0]', 8, INT8), EUCLIDEAN_SQUARED)",
    ("INT8", "DOT"): "VALUES VECTOR_DISTANCE(VECTOR('[1,0,0,0,0,0,0,1]', 8, INT8), "
                     "VECTOR('[1,0,0,0,0,0,0,0]', 8, INT8), DOT)",
    ("INT8", "HAMMING"): "VALUES VECTOR_DISTANCE(VECTOR('[1,0,0,0,0,0,0,1]', 8, INT8), "
                         "VECTOR('[1,0,0,0,0,0,0,0]', 8, INT8), HAMMING)",
    ("INT8", "MANHATTAN"): "VALUES VECTOR_DISTANCE(VECTOR('[1,0,0,0,0,0,0,1]', 8, INT8), "
                           "VECTOR('[1,0,0,0,0,0,0,0]', 8, INT8), MANHATTAN)",
}
METRICS = {"COSINE", "EUCLIDEAN", "EUCLIDEAN_SQUARED", "DOT", "HAMMING", "MANHATTAN"}


@pytest.fixture(scope="module")
def conn(admin_conn, test_schema):  # test_schema installs AsOf's 32K tablespace
    schema.drop(admin_conn, SCHEMA)
    db.use_schema(admin_conn, SCHEMA)
    for sql in TABLES:
        db.execute(admin_conn, sql)
    admin_conn.commit()
    yield admin_conn
    schema.drop(admin_conn, SCHEMA)
    db.use_schema(admin_conn, test_schema)


def test_the_statements_cover_every_documented_metric_for_both_coordinate_types():
    for kind in ("FLOAT32", "INT8"):
        assert {m for k, m in INDEX if k == kind and m} == METRICS
        assert {m for k, m in DISTANCE_SQL if k == kind} == METRICS
    assert set(INDEX) == set(EXPECTED)


def test_create_vector_index_accepts_exactly_cosine_and_the_euclidean_pair(conn):
    seen: dict[tuple[str, str | None], tuple[int, str] | None] = {}
    for key, sql in INDEX.items():
        try:
            db.execute(conn, sql)
            conn.commit()
        except db.DatabaseError as exc:
            conn.rollback()
            seen[key] = (exc.sqlcode or 0, exc.sqlstate or "")
            continue
        name = sql.split()[3]
        kind = db.query(conn, "SELECT INDEXTYPE FROM SYSCAT.INDEXES WHERE INDSCHEMA = ? AND INDNAME = ?",
                        (SCHEMA, name))
        seen[key] = None if [r[0].strip() for r in kind] == ["VANN"] else (0, "not a VANN index")
    assert seen == EXPECTED
    accepted = {k for k, v in seen.items() if v is None}
    assert {m for k, m in accepted if k == "FLOAT32"} == {"COSINE", "EUCLIDEAN", "EUCLIDEAN_SQUARED"}
    assert {m for k, m in accepted if k == "INT8"} == {"EUCLIDEAN", "EUCLIDEAN_SQUARED"}


def test_vector_distance_takes_all_six_metrics(conn):
    got = {key: float(db.query(conn, sql)[0][0]) for key, sql in DISTANCE_SQL.items()}
    for kind in ("FLOAT32", "INT8"):
        assert got[(kind, "EUCLIDEAN")] == pytest.approx(1.0)
        assert got[(kind, "EUCLIDEAN_SQUARED")] == pytest.approx(1.0)
        assert got[(kind, "MANHATTAN")] == pytest.approx(1.0)
        assert got[(kind, "DOT")] == pytest.approx(-1.0)  # Db2 returns the negated dot product, so smaller is nearer
        assert got[(kind, "COSINE")] == pytest.approx(1 - 1 / 2 ** 0.5)
        assert got[(kind, "HAMMING")] == pytest.approx(1.0)
