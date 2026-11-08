import sys
from types import ModuleType

from src.config import Settings
from src.store import Db2Store


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.description = None
        self.last_sql = ""

    def execute(self, sql, params=()):
        self.last_sql = sql
        self.connection.calls.append((sql, params))
        if "SELECT TELEMETRY_ID" in sql:
            names = ["TELEMETRY_ID", "EQUIPMENT_ID", "APPLIANCE_ID", "VRMS_V", "IRMS_A", "APPARENT_POWER_VA", "RUNTIME_S", "TEMPERATURE_C", "VIBRATION_RMS", "RELAY_STATE", "SOURCE", "RECORDED_AT"]
            self.description = [(name,) for name in names]
        return self

    def fetchone(self):
        if "COUNT(*)" in self.last_sql:
            return (0,)
        return None

    def fetchall(self):
        return []


class FakeConnection:
    def __init__(self):
        self.calls = []
        self.commits = 0
        self.closed = False

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass

    def close(self):
        self.closed = True


class FakeDriver:
    def __init__(self):
        self.connections = []

    def connect(self, *_args):
        connection = FakeConnection()
        self.connections.append(connection)
        return connection


def test_db2_adapter_uses_bound_values_and_closes_connections(monkeypatch):
    fake_driver = FakeDriver()
    module = ModuleType("ibm_db_dbi")
    module.connect = fake_driver.connect
    monkeypatch.setitem(sys.modules, "ibm_db_dbi", module)
    monkeypatch.setattr("src.store.get_settings", lambda: Settings(db_backend="db2", db2_password="local-test"))

    store = Db2Store()
    row = store.insert_telemetry({
        "equipment_id": "ES-DB2", "appliance_id": "pump-db2", "irms_a": 1.0,
        "source": "synthetic", "recorded_at": "2026-11-08T00:00:00+00:00",
    })
    assert row["telemetry_id"]
    assert len(fake_driver.connections) >= 2
    assert all(connection.closed for connection in fake_driver.connections)
    sql_calls = [call for connection in fake_driver.connections for call in connection.calls]
    insert = next((call for call in sql_calls if "INSERT INTO ESAI_TELEMETRY" in call[0]), None)
    assert insert is not None
    assert "pump-db2" not in insert[0]
    assert "pump-db2" in insert[1]


def test_db2_adapter_refuses_missing_password_before_import(monkeypatch):
    monkeypatch.setattr("src.store.get_settings", lambda: Settings(db_backend="db2", db2_password=""))
    try:
        Db2Store()
    except ValueError as exc:
        assert "DB2_PASSWORD" in str(exc)
    else:
        raise AssertionError("Expected the Db2 configuration check to fail")
