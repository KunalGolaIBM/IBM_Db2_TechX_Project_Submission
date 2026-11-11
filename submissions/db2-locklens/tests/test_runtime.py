"""Runtime orchestration with a mocked executor (no real Db2)."""

from helpers import ScriptedExecutor

from locklens.config import Settings
from locklens.errors import Db2ConnectionError
from locklens.services.runtime import LockLensRuntime

S = Settings.from_env({"DB2_PASSWORD": "pw"})


def executor(wait_seconds=30):
    return (ScriptedExecutor().on("MON_GET_LOCKS", [])
            .on("MON_GET_APPL_LOCKWAIT", [{"REQ_APPLICATION_HANDLE": 9, "HLD_APPLICATION_HANDLE": 7,
                                           "LOCK_NAME_HEX": "AA11", "WAIT_SECONDS": wait_seconds}])
            .on("MON_GET_CONNECTION", []).on("MON_FORMAT_LOCK_NAME", [])
            .on("SYSCAT.TABLES", [{"N": 0}]))


def test_refresh_returns_snapshot_and_diagnosis_without_recording_when_schema_missing():
    rt = LockLensRuntime(S, executor=executor())
    r = rt.refresh()
    assert r.error is None and r.snapshot.waits and r.diagnosis.findings
    assert r.recorded is None and any("not initialised" in n.message for n in r.notes)


def test_recent_result_is_reused_within_min_age():
    ex = executor(); rt = LockLensRuntime(S, executor=ex)
    first = rt.refresh(min_age=60)
    n = len(ex.calls)
    second = rt.refresh(min_age=60)
    assert second is first and len(ex.calls) == n


def test_connection_failure_is_returned_not_raised():
    class Dead:
        def connect(self): raise Db2ConnectionError("SQL30081N down", "unreachable")
        def close(self): pass
        def is_alive(self): return False
        def ping(self): return False
        def query(self, *a, **k): raise AssertionError("should not query")
        def query_with_columns(self, *a, **k): raise AssertionError("should not query")
        def execute(self, *a, **k): raise AssertionError("should not execute")

    rt = LockLensRuntime(S, connection_factory=lambda s: Dead())
    r = rt.refresh()
    assert r.error and r.connection_kind == "unreachable" and r.snapshot is None
    status = rt.test_connection()
    assert not status.ok and status.kind == "unreachable"
