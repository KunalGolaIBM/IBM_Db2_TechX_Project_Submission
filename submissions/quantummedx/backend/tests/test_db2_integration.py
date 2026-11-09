"""Real Db2 integration test. Skipped (not passed) unless DB2_PASSWORD points at a live Db2."""
import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("DB2_PASSWORD"), reason="No live Db2 configured")


def test_db2_insert_read_delete():
    from app.database.db2 import Db2Pool

    pool = Db2Pool()
    assert pool.health_check()["connected"] is True
    name = f"it_{uuid.uuid4().hex[:8]}"
    pool.execute(
        "INSERT INTO USERS (USERNAME, EMAIL, PASSWORD_HASH) VALUES (?, ?, ?)",
        (name, f"{name}@example.com", "x"),
    )
    row = pool.fetch_one("SELECT username FROM USERS WHERE USERNAME = ?", (name,))
    assert row["username"] == name
    pool.execute("DELETE FROM USERS WHERE USERNAME = ?", (name,))
    assert pool.fetch_one("SELECT username FROM USERS WHERE USERNAME = ?", (name,)) is None
