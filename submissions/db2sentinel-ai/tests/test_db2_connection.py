import pytest
from src.backend.app.database import db_manager

def test_database_manager_integrity():
    """Validates that the database manager connects or runs compliant fallback."""
    status = db_manager.get_status()
    assert status["connected"] is True
    assert status["active_mode"] in ("db2_connected", "demo_fallback")

def test_event_crud_operations():
    """Validates event insertion and retrieval."""
    test_event = {
        "event_type": "AUTHENTICATION",
        "username": "TEST_AUDIT_USER",
        "source_ip": "10.0.99.1",
        "sql_operation": "CONNECT",
        "object_name": "SENTINELDB",
        "status": "SUCCESS",
        "severity": "LOW",
        "event_source": "TEST_HARNESS"
    }
    new_id = db_manager.insert_event(test_event)
    assert new_id > 0

    fetched = db_manager.get_event(new_id)
    assert fetched is not None
    assert fetched["username"] == "TEST_AUDIT_USER"
