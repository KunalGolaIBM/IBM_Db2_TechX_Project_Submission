"""IBM Db2 driver path (ibm_db). Runs against the real driver; no Db2 server is needed
for the failure-handling tests. Set RG_TEST_DB2=1 + DB2_* env vars to also run the live test."""
import os
import time

import pytest

from app.core.config import Settings
from app.database import DatabaseError
from app.database.db2 import Db2Database
from app.database.queries import load_queries


def test_ibm_db_driver_is_installed():
    import ibm_db  # noqa: F401
    import ibm_db_dbi  # noqa: F401


def test_connection_string_built_from_env_settings():
    s = Settings(db_mode="db2", db2_host="db2.example", db2_port=50001, db2_database="RECALLDB", db2_user="u",
                 db2_password="p", db2_security="SSL", db2_schema="rg")
    cs = Db2Database(s)._conn_str()
    assert "HOSTNAME=db2.example;PORT=50001" in cs and "SECURITY=SSL" in cs and "CURRENTSCHEMA=RG" in cs


def test_unreachable_db2_fails_gracefully_with_database_error():
    s = Settings(db_mode="db2", db2_host="127.0.0.1", db2_port=1, db2_database="NODB", db2_user="x", db2_password="y")
    db = Db2Database(s)
    t0 = time.time()
    with pytest.raises(DatabaseError) as exc:
        db.ping()
    assert "Cannot connect to IBM Db2" in str(exc.value)
    assert time.time() - t0 < 60


def test_traceability_sql_is_db2_compatible_by_construction():
    """Static guards for Db2 recursive-CTE rules (no RECURSIVE keyword, no LIMIT, bounded depth, CAST in both legs)."""
    for name, text in load_queries().items():
        up = text.upper()
        assert "WITH RECURSIVE" not in up, name
        assert " LIMIT " not in up, name
        if "UNION ALL" in up and ("FROM GENEALOGY G" in up or "FROM ANCESTRY A" in up or "FROM FLOW F" in up):
            assert "< 12" in up or "< 8" in up, f"{name}: recursion must be depth-bounded"
            assert up.count("CAST(") >= 2, name


@pytest.mark.skipif(os.getenv("RG_TEST_DB2") != "1", reason="live IBM Db2 not configured (set RG_TEST_DB2=1 and DB2_* vars)")
def test_live_db2_round_trip():
    from app.core.config import get_settings

    db = Db2Database(get_settings())
    assert db.ping()["ok"]
    assert db.query_one("SELECT COUNT(*) AS n FROM SYSCAT.TABLES")["n"] > 0
