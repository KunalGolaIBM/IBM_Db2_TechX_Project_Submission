"""DB-API contract checks: parameter binding, transaction cleanup, and decoding.

These complement the opt-in live Db2 tests; no SQL semantics are simulated here.
"""
from collections import deque
from datetime import datetime
from decimal import Decimal
import json

import pytest

from adapters.db2 import Db2Repository
from pool import ConnectionPool


class Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.description = None
        self.rows = []

    def execute(self, sql, params=()):
        self.connection.calls.append((sql, params))
        if self.connection.results:
            result = self.connection.results.popleft()
            if isinstance(result, Exception):
                raise result
            columns, self.rows = result
            self.description = [(column,) for column in columns] if columns else None

    def fetchall(self):
        return self.rows

    def fetchmany(self, count):
        return self.rows[:count]

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def close(self):
        self.connection.cursors_closed += 1


class Connection:
    def __init__(self):
        self.results = deque()
        self.calls = []
        self.commits = self.rollbacks = self.cursors_closed = 0

    def cursor(self):
        return Cursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        pass

    def returns(self, columns=(), rows=()):
        self.results.append((columns, rows))


@pytest.fixture
def db():
    connection = Connection()
    repo = Db2Repository(pool=ConnectionPool(lambda: connection, 0, 1))
    yield repo, connection
    repo.close()


def test_transactions_commit_once_close_all_cursors_and_release_on_failure(db):
    repo, conn = db
    with repo.transaction():
        repo.execute("UPDATE PG_META SET META_VALUE = ?", ("one",))
        repo.execute("UPDATE PG_META SET META_VALUE = ?", ("two",))
    assert conn.commits == 1 and conn.cursors_closed == 2
    conn.results.append(RuntimeError("write failed"))
    with pytest.raises(RuntimeError):
        repo.execute("UPDATE PG_META SET META_VALUE = ?", ("three",))
    assert conn.commits == 1 and conn.rollbacks >= 2
    assert repo.pool.stats()["borrowed"] == 0


def test_query_decodes_decimal_datetime_and_lowercase_column_names(db):
    repo, conn = db
    conn.returns(["AMOUNT", "CREATED_AT"], [(Decimal("1.50"), datetime(2026, 1, 1))])
    assert repo.query("SELECT AMOUNT, CREATED_AT FROM PG_REPORTS") == [
        {"amount": 1.5, "created_at": "2026-01-01T00:00:00"}]
    conn.returns()
    assert repo.query("VALUES 1") == []


def test_writes_bind_hostile_values_and_preserve_generated_ids(db):
    repo, conn = db
    attack = "x'); DROP TABLE PG_ENTITIES; --"
    conn.returns(["ID"], [(42,)])
    assert repo.insert_pattern({"title": attack, "category": "other", "channel": "chat", "severity": 1,
                                "description": attack}, [1.0, 0.0]) == 42
    conn.returns(["ID"], [(43,)])
    assert repo.add_report(42, attack, "other", 5, "NGN", attack, [1.0, 0.0]) == 43
    conn.returns(["ID"], [(44,)])
    assert repo.insert_screening({"merchant": attack, "message": attack, "risk_score": 70, "verdict": "BLOCK"}) == 44
    repo.update_screening_ai(44, attack, 80, "BLOCK")
    repo.update_screening_paypal(44, attack, "CREATED")
    for sql, params in conn.calls:
        assert attack not in sql
        assert any(attack in str(value) for value in params)
    assert repo.pool.stats()["borrowed"] == 0


def test_vector_queries_bind_vectors_region_and_velocity(db):
    repo, conn = db
    conn.returns(["ID", "DISTANCE"], [(1, 0.2)])
    assert repo.search_patterns([0.123456, -0.654321], "NG")[0]["similarity"] == 0.8
    conn.returns(["ID", "DISTANCE"], [(2, 0.3)])
    assert repo.search_reports([0.123456, -0.654321])[0]["similarity"] == 0.7
    for sql, params in conn.calls:
        assert "0.123456" not in sql and "0.123456" in params[0]
    conn.returns(["ATTEMPTS", "BLOCKED"], [(2, 1)])
    assert repo.payee_velocity("SELLER@EXAMPLE.COM")["blocked"] == 1
    assert conn.calls[-1][1] == ("seller@example.com", 24)


def test_entity_lookups_and_merge_are_parameterized(db):
    repo, conn = db
    assert repo.lookup_entities([]) == [] and not conn.calls
    conn.returns(["STATUS"], [("BLOCKED",)])
    assert repo.lookup_entities([("account", "0000012345")]) == [{"status": "BLOCKED"}]
    assert conn.calls[-1][1] == ("account", "0000012345")
    conn.returns()
    conn.returns(["ID"], [(7,)])
    assert repo.upsert_entity("email", "SELLER@EXAMPLE.COM", count_report=True) == 7
    sql, params = conn.calls[-2]
    assert "MERGE INTO" in sql and params[-3:] == (1, 1, 1)
    assert "seller@example.com" not in sql


def test_example_storage_binds_text_and_uses_bson(db):
    repo, conn = db
    repo.init_examples(2)
    repo.insert_example("id", {"text": "Abeg send OTP", "label": "phishing", "source": "test"}, [1.0, 0.0])
    sql, params = conn.calls[-1]
    assert "Abeg send OTP" not in sql and "SYSTOOLS.JSON2BSON(?)" in sql
    assert params[2] == "Abeg send OTP"
    conn.returns(["ID"], [("id   ",)])
    assert repo.example_ids() == {"id"}
    repo.delete_examples(["id"])
    assert conn.calls[-1][1] == ("id",)


def test_get_screening_decodes_reasons_and_missing_rows(db):
    repo, conn = db
    conn.returns(["ID", "REASONS_JSON"], [(7, json.dumps([{"code": "CREDENTIALS"}]))])
    assert repo.get_screening(7) == {"id": 7, "reasons": [{"code": "CREDENTIALS"}]}
    conn.returns(["ID"], [])
    assert repo.get_screening(8) is None
    conn.returns(["ID"], [(7,)])
    assert repo.recent_screenings(1) == [{"id": 7}]


def test_meta_and_schema_description_do_not_expose_embeddings(db):
    repo, conn = db
    conn.returns(["META_VALUE"], [("local-hash-v1",)])
    assert repo.get_meta("embedder") == "local-hash-v1"
    conn.returns(["META_VALUE"], [])
    assert repo.get_meta("missing") is None
    repo.set_meta("embedder", "local-hash-v1")
    assert conn.calls[-1][1] == ("embedder", "local-hash-v1")
    conn.returns(["TABNAME", "COLNAME", "TYPENAME"], [("PG_ENTITIES", "ID", "INTEGER")])
    assert repo.schema_description() == "PG_ENTITIES(ID INTEGER)"
    assert "COLNAME <> 'EMBEDDING'" in conn.calls[-1][0]


def test_readonly_revalidates_limits_and_rolls_back(db):
    from analyst import UnsafeSQL
    repo, conn = db
    conn.returns(["ID"], [(1,), (2,)])
    assert repo.run_readonly("SELECT ID FROM PG_ENTITIES") == {"columns": ["id"], "rows": [[1], [2]]}
    assert not conn.commits and conn.rollbacks >= 1
    assert conn.calls[-1][0].endswith("FETCH FIRST 100 ROWS ONLY")
    with pytest.raises(UnsafeSQL):
        repo.run_readonly("DELETE FROM PG_ENTITIES")
    assert len(conn.calls) == 1


def test_only_known_ddl_conflicts_are_ignored(db):
    repo, conn = db
    conn.results.append(RuntimeError("SQLSTATE=42710"))
    repo._try("CREATE TABLE PG_META (X INT)", ignore=("42710",))
    conn.results.append(RuntimeError("permission denied"))
    with pytest.raises(RuntimeError, match="permission denied"):
        repo._try("CREATE TABLE PG_META (X INT)")


def test_stats_and_liveness_map_database_values(db):
    repo, conn = db
    conn.returns(["OK"], [(1,)])
    assert repo.ping()
    conn.returns(["N"], [(25,)])
    assert repo.count_patterns() == 25
    for columns, rows in [(["SCREENINGS"], [(3,)]), (["CATEGORY", "N"], [("phishing", 2)]),
                          (["ENTITY_VALUE"], [("1234567890",)]), (["VERDICT"], [("BLOCK",)]),
                          (["PATTERNS", "ENTITIES", "REPORTS"], [(25, 3, 5)])]:
        conn.returns(columns, rows)
    stats = repo.stats()
    assert stats["totals"]["screenings"] == 3 and stats["knowledge_base"]["patterns"] == 25


def test_atomic_report_retries_only_rolled_back_conflicts(db, monkeypatch):
    repo, conn = db
    calls = []
    def merge(*args):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("SQLSTATE=23505 concurrent insert")
        return 7
    monkeypatch.setattr(repo, "_merge_entity", merge)
    monkeypatch.setattr(repo, "add_report", lambda *args: 8)
    monkeypatch.setattr(repo, "lookup_entities", lambda *args: [{"status": "BLOCKED", "report_count": 3}])
    result = repo.file_report("account", "1234567890", "test", "other", 0, "NGN", "Report narrative", [1.0])
    assert result["report_id"] == 8 and len(calls) == 2
    assert conn.commits == 1 and conn.rollbacks >= 1
    def disconnected(*args):
        raise RuntimeError("08006 ambiguous outcome")
    monkeypatch.setattr(repo, "_merge_entity", disconnected)
    with pytest.raises(RuntimeError, match="08006"):
        repo.file_report("account", "1234567890", "test", "other", 0, "NGN", "Report narrative", [1.0])
