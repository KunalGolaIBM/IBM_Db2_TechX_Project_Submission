"""Test doubles. NOTHING here talks to a real Db2: these are mocks used by the unit tests."""

from __future__ import annotations

from typing import Any, Sequence

from locklens.errors import Db2PermissionError, Db2QueryError
from locklens.models import (LockRecord, LockWaitRecord, ResourceInfo, SessionInfo, Snapshot)

LOCKS_COLS = ["MEMBER", "LOCK_NAME", "LOCK_OBJECT_TYPE_ID", "LOCK_OBJECT_TYPE", "LOCK_MODE",
              "LOCK_CURRENT_MODE", "LOCK_STATUS", "LOCK_COUNT", "APPLICATION_HANDLE"]
WAIT_COLS = ["LOCK_WAIT_START_TIME", "LOCK_NAME", "LOCK_OBJECT_TYPE", "LOCK_MODE",
             "LOCK_CURRENT_MODE", "LOCK_MODE_REQUESTED", "LOCK_STATUS", "REQ_APPLICATION_HANDLE",
             "REQ_MEMBER", "HLD_APPLICATION_HANDLE", "HLD_MEMBER", "ADDITIONAL_DETAILS"]
CONN_COLS = ["APPLICATION_HANDLE", "APPLICATION_NAME", "APPLICATION_ID", "SYSTEM_AUTH_ID",
             "CLIENT_HOSTNAME", "WORKLOAD_OCCURRENCE_STATE", "SOMETHING_NEW_IN_FUTURE"]


class ScriptedExecutor:
    """Answers queries by matching a substring of the SQL; records every call."""

    def __init__(self, columns: dict[str, list[str]] | None = None):
        self.columns = columns or {"MON_GET_LOCKS": LOCKS_COLS, "MON_GET_APPL_LOCKWAIT": WAIT_COLS,
                                   "MON_GET_CONNECTION": CONN_COLS}
        self.rules: list[tuple[str, Any]] = []
        self.calls: list[tuple[str, tuple]] = []

    def on(self, fragment: str, result: Any) -> "ScriptedExecutor":
        self.rules.append((fragment, result))
        return self

    def query_with_columns(self, sql: str, params: Sequence[Any] = ()):
        self.calls.append((sql, tuple(params)))
        if "WHERE 1=0" in sql:
            for name, cols in self.columns.items():
                if name in sql:
                    if cols is None:
                        raise Db2QueryError("SQL0204N undefined", 204)
                    return list(cols), []
        return [], self.query(sql, params, _record=False)

    def query(self, sql: str, params: Sequence[Any] = (), _record: bool = True):
        if _record:
            self.calls.append((sql, tuple(params)))
        for fragment, result in self.rules:
            if fragment in sql:
                if isinstance(result, Exception):
                    raise result
                return result(params) if callable(result) else result
        return []

    def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        self.calls.append((sql, tuple(params)))
        return 0


def permission_error() -> Db2PermissionError:
    return Db2PermissionError("SQL0551N not authorized", 551, "42501")


def wait(req: int, hld: int | None, lock: str = "AA11", seconds: int | None = 5,
         requested: str = "X", held: str = "X", start: str = "2026-11-10-10.00.00.000000") -> LockWaitRecord:
    return LockWaitRecord(req_application_handle=req, hld_application_handle=hld, lock_name_hex=lock,
                          lock_object_type="ROW", lock_mode=held, lock_mode_requested=requested,
                          lock_status="W", lock_wait_start_time=start, wait_seconds=seconds)


def lock(app: int, name: str = "AA11", status: str = "G", mode: str = "X") -> LockRecord:
    return LockRecord(application_handle=app, lock_name_hex=name, lock_status=status,
                      lock_object_type="ROW", lock_mode=mode, lock_count=1)


def snapshot(waits=(), locks=(), sessions=(), resources=()) -> Snapshot:
    return Snapshot(captured_at="2026-11-10T10:00:10+00:00", waits=list(waits), locks=list(locks),
                    sessions={s.application_handle: s for s in sessions},
                    resources={r.lock_name_hex: r for r in resources})


def session(handle: int, name: str = "app", user: str = "DB2INST1", state: str | None = None) -> SessionInfo:
    return SessionInfo(application_handle=handle, application_name=name, system_auth_id=user,
                       workload_state=state)


def resource(lock_name: str = "AA11") -> ResourceInfo:
    return ResourceInfo(lock_name_hex=lock_name, table_schema="LOCKLENS_DEMO",
                        table_name="ACCOUNTS", object_type="ROW")


class FakeIncidentDb:
    """In-memory emulation of exactly the statements IncidentStore issues (mock, not Db2)."""

    def __init__(self, fail_first_insert_with_duplicate: bool = False):
        self.rows: list[dict[str, Any]] = []
        self._next = 1
        self.duplicate_once = fail_first_insert_with_duplicate
        self.sql_log: list[str] = []

    def _open(self, key):
        return [r for r in self.rows if r["OPEN_KEY"] == key]

    def query(self, sql, params=()):
        self.sql_log.append(sql)
        if "WHERE OPEN_KEY = ?" in sql:
            return [dict(r) for r in self._open(params[0])]
        if "WHERE STATUS = 'OPEN'" in sql and "COUNT" in sql:
            return [{"N": len([r for r in self.rows if r["STATUS"] == "OPEN"])}]
        if "WHERE STATUS = 'OPEN'" in sql:
            return [dict(r) for r in self.rows if r["STATUS"] == "OPEN"]
        if "FROM SYSCAT.TABLES" in sql:
            return [{"N": 1}]
        if "FROM LOCKLENS.LOCK_INCIDENTS" in sql:           # list_incidents
            return [dict(r) for r in self.rows]
        return []

    def query_with_columns(self, sql, params=()):
        return [], self.query(sql, params)

    def execute(self, sql, params=()):
        self.sql_log.append(sql)
        if sql.startswith("INSERT INTO"):
            if self.duplicate_once:
                self.duplicate_once = False
                self.rows.append({"INCIDENT_ID": self._next, "OPEN_KEY": params[1], "STATUS": "OPEN",
                                  "SEVERITY": "INFO", "MAX_WAIT_SECONDS": None, "OBSERVATIONS": 1})
                self._next += 1
                raise Db2QueryError("SQL0803N duplicate", 803)
            if self._open(params[1]):
                raise Db2QueryError("SQL0803N duplicate", 803)
            self.rows.append({"INCIDENT_ID": self._next, "INCIDENT_KEY": params[0], "OPEN_KEY": params[1],
                              "STATUS": "OPEN", "SEVERITY": params[2], "CATEGORY": params[3],
                              "FINDING_TYPE": params[4], "TITLE": params[5], "OBSERVATIONS": 1,
                              "MAX_WAIT_SECONDS": params[11]})
            self._next += 1
        elif sql.startswith("UPDATE") and "OBSERVATIONS = OBSERVATIONS + 1" in sql:
            row = next(r for r in self.rows if r["INCIDENT_ID"] == params[-1])
            row.update(SEVERITY=params[0], MAX_WAIT_SECONDS=params[1], OBSERVATIONS=row["OBSERVATIONS"] + 1)
        elif sql.startswith("UPDATE") and "STATUS = 'RESOLVED'" in sql:
            row = next(r for r in self.rows if r["INCIDENT_ID"] == params[-1])
            row.update(STATUS="RESOLVED", OPEN_KEY=None)
        return 1
