"""REAL IBM Db2 integration test. Skipped unless LOCKLENS_RUN_INTEGRATION=1.

This is NOT a mock. It needs a running Db2, the demo table from scripts/demo_setup.sql, the
ibm_db driver, and the DB2_* variables in the environment (or .env). It opens two separate
sessions, makes one block the other, and asserts that LockLens sees the wait.

    LOCKLENS_RUN_INTEGRATION=1 pytest tests/integration -v -s
"""

import os
import threading
import time

import pytest

pytestmark = pytest.mark.integration

if os.environ.get("LOCKLENS_RUN_INTEGRATION") != "1":
    pytest.skip("set LOCKLENS_RUN_INTEGRATION=1 to run against a real Db2", allow_module_level=True)

ibm_db = pytest.importorskip("ibm_db")

from locklens.config import Settings, load_env_file                    # noqa: E402
from locklens.db.connection import build_connection_string             # noqa: E402
from locklens.services.runtime import LockLensRuntime                  # noqa: E402

TABLE = "LOCKLENS_DEMO.ACCOUNTS"


def _open(settings):
    conn = ibm_db.connect(build_connection_string(settings), "", "")
    ibm_db.autocommit(conn, ibm_db.SQL_AUTOCOMMIT_OFF)
    return conn


def test_locklens_sees_a_real_two_session_lock_wait():
    load_env_file(".env")
    settings = Settings.from_env()
    rt = LockLensRuntime(settings)
    assert rt.test_connection().ok

    holder, waiter = _open(settings), _open(settings)
    outcome = {}

    def blocked_update():
        try:
            ibm_db.exec_immediate(waiter, "SET CURRENT LOCK TIMEOUT 120")
            ibm_db.exec_immediate(waiter, f"UPDATE {TABLE} SET BALANCE = BALANCE + 1 WHERE ID = 1")
            outcome["finished"] = True
        except Exception as exc:                     # noqa: BLE001
            outcome["error"] = str(exc)

    try:
        ibm_db.exec_immediate(holder, f"UPDATE {TABLE} SET BALANCE = BALANCE - 1 WHERE ID = 1")   # no COMMIT
        thread = threading.Thread(target=blocked_update, daemon=True)
        thread.start()

        seen = None
        deadline = time.time() + 30
        while time.time() < deadline and seen is None:
            time.sleep(1)
            result = rt.refresh(record=False)
            assert result.error is None, result.error
            seen = next((e for e in result.diagnosis.analysis.edges if e.holder is not None), None)
        assert seen is not None, "LockLens did not observe a lock wait with a known holder"
        assert seen.waiter != seen.holder
        assert any(f.finding_type == "BLOCKING_SESSION" for f in result.diagnosis.findings)
        assert not any(f.finding_type == "DEADLOCK" for f in result.diagnosis.findings)
    finally:
        ibm_db.rollback(holder)                      # release the lock; the waiter then completes
        if "thread" in locals():
            thread.join(timeout=30)
        ibm_db.rollback(waiter)
        ibm_db.close(holder); ibm_db.close(waiter)

    assert outcome.get("finished"), outcome
    after = rt.refresh(record=False)
    assert not after.diagnosis.analysis.edges, "wait should be gone after the holder rolled back"
    rt.close()
