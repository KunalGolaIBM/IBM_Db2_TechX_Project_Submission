"""
Security & Guardrails Test Suite - Kisan Mitra (किसान मित्र)
Verifies that all DDL/DML mutation queries, SQL injection vectors,
and multi-statement execution are strictly rejected with PermissionError.
"""

import pytest
from app.db_client import get_db_client

@pytest.fixture
def db():
    return get_db_client(read_only=True)

def test_drop_table_blocked(db):
    """Ensure DROP TABLE is rejected."""
    with pytest.raises(PermissionError) as exc_info:
        db.execute_query("DROP TABLE MANDI_PRICES;")
    assert "Disallowed" in str(exc_info.value) or "Violation" in str(exc_info.value)

def test_delete_query_blocked(db):
    """Ensure DELETE FROM is rejected."""
    with pytest.raises(PermissionError) as exc_info:
        db.execute_query("DELETE FROM MANDI_PRICES WHERE id = 1;")
    assert "Disallowed" in str(exc_info.value) or "Violation" in str(exc_info.value)

def test_update_query_blocked(db):
    """Ensure UPDATE statement is rejected."""
    with pytest.raises(PermissionError) as exc_info:
        db.execute_query("UPDATE MANDI_PRICES SET modal_price = 9999 WHERE id = 1;")
    assert "Disallowed" in str(exc_info.value) or "Violation" in str(exc_info.value)

def test_insert_into_blocked(db):
    """Ensure INSERT INTO is rejected."""
    with pytest.raises(PermissionError) as exc_info:
        db.execute_query("INSERT INTO MANDI_PRICES (state, commodity, modal_price) VALUES ('UP', 'Wheat', 2500);")
    assert "Disallowed" in str(exc_info.value) or "Violation" in str(exc_info.value)

def test_alter_table_blocked(db):
    """Ensure ALTER TABLE is rejected."""
    with pytest.raises(PermissionError) as exc_info:
        db.execute_query("ALTER TABLE MANDI_PRICES ADD COLUMN hacked VARCHAR(100);")
    assert "Disallowed" in str(exc_info.value) or "Violation" in str(exc_info.value)

def test_grant_revoke_blocked(db):
    """Ensure privilege modifications are rejected."""
    with pytest.raises(PermissionError) as exc_info:
        db.execute_query("GRANT ALL PRIVILEGES ON MANDI_PRICES TO PUBLIC;")
    assert "Disallowed" in str(exc_info.value) or "Violation" in str(exc_info.value)

def test_semicolon_chaining_blocked(db):
    """Ensure stacked SQL injection statements separated by semicolons are rejected."""
    with pytest.raises(PermissionError) as exc_info:
        db.execute_query("SELECT * FROM MANDI_PRICES; DROP TABLE DOC_CHUNKS;")
    assert "chaining" in str(exc_info.value).lower() or "Violation" in str(exc_info.value)

def test_valid_select_allowed(db):
    """Ensure standard read-only SELECT queries succeed seamlessly."""
    res = db.execute_query("SELECT COUNT(*) AS total FROM MANDI_PRICES")
    assert res is not None
    assert "total" in res["columns"]
    assert len(res["rows"]) == 1
    assert res["rows"][0]["total"] > 0
