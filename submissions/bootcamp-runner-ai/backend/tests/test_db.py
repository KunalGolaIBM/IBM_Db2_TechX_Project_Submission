import pytest

import backend.db as db_module
from backend.db import DatabaseError, DatabaseUnavailable, Db2Client


class FakeStatement:
    def __init__(self, sql):
        self.sql = sql


class FakeIbmDb:
    SQL_ATTR_AUTOCOMMIT = "autocommit_attribute"
    SQL_AUTOCOMMIT_OFF = "autocommit_off"

    def __init__(self, execute_error=False, error_code="", rollback_error=False):
        self.execute_error = execute_error
        self.error_code = error_code
        self.rollback_error = rollback_error
        self.executed_sql = []
        self.commits = 0
        self.rollbacks = 0
        self.closes = 0
        self.options = None
        self.fetch_calls = 0
        self.fetch_error = False
        self.invalid_field_count = False

    def connect(self, dsn, user, password, options):
        self.options = options
        return object()

    def prepare(self, connection, sql):
        self.executed_sql.append(sql)
        return FakeStatement(sql)

    def bind_param(self, statement, index, value):
        return True

    def execute(self, statement):
        if self.execute_error:
            raise RuntimeError("write failed")
        return True

    def num_fields(self, statement):
        if self.invalid_field_count:
            return None
        return 1 if statement.sql.upper().lstrip().startswith("SELECT") else 0

    def stmt_error(self, statement=None):
        return self.error_code

    def stmt_errormsg(self, statement=None):
        return "SQLSTATE diagnostic"

    def get_sqlcode(self):
        return "-803"

    def fetch_assoc(self, statement):
        self.fetch_calls += 1
        if self.fetch_error:
            raise RuntimeError("fetch failed")
        if statement.sql.upper().startswith("SELECT IDENTITY_VAL_LOCAL"):
            return {"GENERATED_ID": 42}
        if statement.sql.upper().startswith("SELECT"):
            if self.fetch_calls == 1:
                return {"VALUE": 7}
        return None

    def commit(self, connection):
        self.commits += 1
        return True

    def rollback(self, connection):
        self.rollbacks += 1
        if self.rollback_error:
            raise RuntimeError("connection lost during rollback")
        return True

    def close(self, connection):
        self.closes += 1
        return True


def test_connect_disables_autocommit_and_execute_commits(monkeypatch):
    fake = FakeIbmDb()
    monkeypatch.setattr(db_module, "ibm_db", fake)
    client = Db2Client("DATABASE=test")

    client.connect()
    client.execute("INSERT INTO example (value) VALUES (?)", (1,))

    assert fake.options == {fake.SQL_ATTR_AUTOCOMMIT: fake.SQL_AUTOCOMMIT_OFF}
    assert fake.commits == 1
    assert fake.rollbacks == 0


def test_select_fetches_rows(monkeypatch):
    fake = FakeIbmDb()
    monkeypatch.setattr(db_module, "ibm_db", fake)
    client = Db2Client("DATABASE=test")
    client.connect()

    assert client.execute("SELECT value FROM example") == [{"VALUE": 7}]
    assert fake.fetch_calls == 2
    assert fake.commits == 1


def test_merge_with_no_result_columns_commits_without_fetching(monkeypatch):
    fake = FakeIbmDb()
    monkeypatch.setattr(db_module, "ibm_db", fake)
    client = Db2Client("DATABASE=test")
    client.connect()

    assert client.execute("MERGE INTO example USING source ON 1=1") == []
    assert fake.fetch_calls == 0
    assert fake.commits == 1


@pytest.mark.parametrize("sql", [
    "INSERT INTO example (value) VALUES (?)",
    "UPDATE example SET value = ?",
    "DELETE FROM example",
])
def test_write_statements_do_not_fetch_rows(monkeypatch, sql):
    fake = FakeIbmDb()
    monkeypatch.setattr(db_module, "ibm_db", fake)
    client = Db2Client("DATABASE=test")
    client.connect()

    assert client.execute(sql, (1,) if "?" in sql else ()) == []
    assert fake.fetch_calls == 0
    assert fake.commits == 1


def test_fetch_failure_rolls_back_and_raises_database_error(monkeypatch):
    fake = FakeIbmDb()
    fake.fetch_error = True
    monkeypatch.setattr(db_module, "ibm_db", fake)
    client = Db2Client("DATABASE=test")
    client.connect()

    with pytest.raises(DatabaseError, match="Db2 query failed"):
        client.execute("SELECT value FROM example")

    assert fake.rollbacks == 1
    assert fake.commits == 0
    assert client.connection is not None


def test_invalid_num_fields_result_is_an_error(monkeypatch):
    fake = FakeIbmDb()
    fake.invalid_field_count = True
    monkeypatch.setattr(db_module, "ibm_db", fake)
    client = Db2Client("DATABASE=test")
    client.connect()

    with pytest.raises(DatabaseError, match="Db2 query failed"):
        client.execute("INSERT INTO example (value) VALUES (?)", (1,))

    assert fake.rollbacks == 1
    assert fake.commits == 0


def test_execute_rolls_back_persistence_failure(monkeypatch):
    fake = FakeIbmDb(execute_error=True, error_code="23505")
    monkeypatch.setattr(db_module, "ibm_db", fake)
    client = Db2Client("DATABASE=test")
    client.connect()

    with pytest.raises(DatabaseError, match="Db2 query failed") as error:
        client.execute("INSERT INTO example (value) VALUES (?)", (1,))

    assert error.value.sqlstate == "23505"
    assert error.value.sqlcode == "-803"
    assert fake.commits == 0
    assert fake.rollbacks == 1
    assert fake.closes == 0
    assert client.connection is not None


def test_execute_invalidates_connection_for_transport_failure(monkeypatch):
    fake = FakeIbmDb(execute_error=True, error_code="08006")
    monkeypatch.setattr(db_module, "ibm_db", fake)
    client = Db2Client("DATABASE=test")
    client.connect()

    with pytest.raises(DatabaseUnavailable, match="Db2 query failed"):
        client.execute("INSERT INTO example (value) VALUES (?)", (1,))

    assert fake.rollbacks == 1
    assert fake.closes == 1
    assert client.connection is None


def test_non_connection_sql_error_is_not_reported_as_offline(monkeypatch):
    fake = FakeIbmDb(execute_error=True, error_code="42601")
    monkeypatch.setattr(db_module, "ibm_db", fake)
    client = Db2Client("DATABASE=test")
    client.connect()

    with pytest.raises(DatabaseError) as error:
        client.execute("INVALID SQL", ())

    assert not isinstance(error.value, DatabaseUnavailable)
    assert error.value.sqlstate == "42601"
    assert client.connection is not None


def test_missing_sqlstate_preserves_connection_after_successful_rollback(monkeypatch):
    fake = FakeIbmDb(execute_error=True)
    fake.stmt_error = None
    monkeypatch.setattr(db_module, "ibm_db", fake)
    client = Db2Client("DATABASE=test")
    client.connect()

    with pytest.raises(DatabaseError, match="Db2 query failed"):
        client.execute("INVALID SQL", ())

    assert fake.rollbacks == 1
    assert fake.closes == 0
    assert client.connection is not None


def test_rollback_failure_invalidates_and_closes_connection(monkeypatch):
    fake = FakeIbmDb(execute_error=True, error_code="23505", rollback_error=True)
    monkeypatch.setattr(db_module, "ibm_db", fake)
    client = Db2Client("DATABASE=test")
    client.connect()

    with pytest.raises(DatabaseUnavailable, match="rollback failed"):
        client.execute("INSERT INTO example (value) VALUES (?)", (1,))

    assert fake.rollbacks == 1
    assert fake.closes == 1
    assert client.connection is None


def test_session_insert_and_identity_lookup_commit_atomically(monkeypatch):
    fake = FakeIbmDb()
    monkeypatch.setattr(db_module, "ibm_db", fake)
    client = Db2Client("DATABASE=test")
    client.connect()

    identity = client.execute_insert_and_get_identity(
        "INSERT INTO game_sessions (player_id) VALUES (?)", ("player-1",)
    )

    assert identity == 42
    assert fake.commits == 1
    assert fake.rollbacks == 0
    assert client.connection is not None


def test_session_identity_failure_rolls_back_and_invalidates_connection(monkeypatch):
    fake = FakeIbmDb()
    monkeypatch.setattr(db_module, "ibm_db", fake)
    client = Db2Client("DATABASE=test")
    client.connect()
    fake.executed_sql.clear()

    def no_identity(statement):
        return None

    monkeypatch.setattr(fake, "fetch_assoc", no_identity)
    with pytest.raises(DatabaseError, match="Db2 transaction failed"):
        client.execute_insert_and_get_identity(
            "INSERT INTO game_sessions (player_id) VALUES (?)", ("player-1",)
        )

    assert fake.commits == 0
    assert fake.rollbacks == 1
    assert fake.closes == 0
    assert client.connection is not None


def test_close_rolls_back_before_closing(monkeypatch):
    fake = FakeIbmDb()
    monkeypatch.setattr(db_module, "ibm_db", fake)
    client = Db2Client("DATABASE=test")
    client.connect()

    client.close()

    assert client.connection is None
    assert fake.rollbacks == 1
