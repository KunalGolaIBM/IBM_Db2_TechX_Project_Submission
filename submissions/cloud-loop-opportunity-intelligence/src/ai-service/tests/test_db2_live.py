import os
import pytest
from app.core.config import settings

@pytest.mark.db2
def test_live_db2_connection():
    """
    Live integration test against real IBM Db2 database.
    Skipped unless DB2_HOST environment variable is configured and reachable.
    """
    if not settings.host:
        pytest.skip("DB2_HOST environment variable not configured; skipping live Db2 integration test.")

    import ibm_db
    dsn = settings.db2_dsn
    try:
        conn = ibm_db.connect(dsn, "", "")
        assert conn is not None
        stmt = ibm_db.exec_immediate(conn, "SELECT 1 FROM SYSIBM.SYSDUMMY1")
        assert stmt is not None
        ibm_db.close(conn)
    except Exception as e:
        pytest.fail(f"Live IBM Db2 connection failed: {e}")
