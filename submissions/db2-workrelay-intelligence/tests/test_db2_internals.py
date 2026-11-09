import pytest
from unittest.mock import MagicMock
from app.db.connection import Db2ConnectionManager
from app.db.repository import Db2IncidentRepository
from app.models.incident import (
    Incident,
    IncidentAction,
    IncidentEvent,
    IncidentSeverity,
    IncidentStatus,
    ActionStatus,
)


def test_db2_row_mapping_from_tuples():
    """Verify that tuple rows from ibm_db_dbi are mapped safely to lowercase dict keys."""
    mock_cursor = MagicMock()
    mock_cursor.description = [
        ("ID", 1, 32, 32, 0, 0, False),
        ("TITLE", 1, 255, 255, 0, 0, False),
        ("DESCRIPTION", 1, 1000, 1000, 0, 0, False),
        ("SERVICE", 1, 100, 100, 0, 0, False),
        ("SEVERITY", 1, 20, 20, 0, 0, False),
        ("STATUS", 1, 30, 30, 0, 0, False),
        ("TOTAL", 3, 10, 10, 0, 0, False),
    ]
    raw_tuple = ("INC-TEST-01", "Outage Alert", "Database connection lost", "db2", "CRITICAL", "OPEN", 1)

    mapped = Db2ConnectionManager.map_row(mock_cursor, raw_tuple)
    assert mapped is not None
    assert mapped["id"] == "INC-TEST-01"
    assert mapped["title"] == "Outage Alert"
    assert mapped["service"] == "db2"
    assert mapped["severity"] == "CRITICAL"
    assert mapped["status"] == "OPEN"
    assert mapped["total"] == 1


def test_db2_row_mapping_none_and_dict():
    """Verify handling of None and existing dicts in map_row."""
    assert Db2ConnectionManager.map_row(None, None) is None
    d = {"ID": "123", "NAME": "test"}
    mapped = Db2ConnectionManager.map_row(None, d)
    assert mapped["id"] == "123"
    assert mapped["name"] == "test"


def test_db2_connection_failure_handling(monkeypatch):
    """Verify Db2ConnectionManager records error and health check reports disconnected on connection failure."""
    # Force use_mock=False and invalid host
    monkeypatch.setenv("DB2_HOST", "invalid.db2.host.nonexistent")
    monkeypatch.setenv("DB2_PORT", "50000")
    monkeypatch.setenv("DB2_USE_MOCK", "false")

    mgr = Db2ConnectionManager(use_mock=False)
    health = mgr.check_health()
    # In absence of native ibm_db or unreachable host, health probe reports degraded/mock or not connected
    if mgr.is_db2_active:
        assert health["connected"] is False
    else:
        assert mgr.active_mode == "sqlite_mock"
        assert mgr.last_error is not None


def test_native_schema_db2_file_exists_and_parses():
    """Verify schema_db2.sql exists, is readable, and contains genuine Db2 DDL statements."""
    from pathlib import Path
    schema_file = Path(__file__).parent.parent / "src" / "app" / "db" / "schema_db2.sql"
    assert schema_file.is_file()
    content = schema_file.read_text(encoding="utf-8")
    assert "CREATE TABLE incidents" in content
    assert "CLOB(1M)" in content
    assert "GENERATED ALWAYS AS IDENTITY" in content
    assert "CONSTRAINT fk_event_incident FOREIGN KEY" in content


def test_audit_log_persistence_on_status_change():
    """Verify that multiple status updates produce sequential, immutable audit events."""
    mgr = Db2ConnectionManager(use_mock=True)
    repo = Db2IncidentRepository(mgr)
    repo.init_schema_sqlite()

    incident = Incident(
        title="Audit Trail Verification",
        description="Testing chronological lifecycle audit events",
        service="audit-service",
        severity=IncidentSeverity.MEDIUM,
    )
    repo.create(incident)

    # First update
    repo.patch(incident.id, status=IncidentStatus.INVESTIGATING)
    # Second update
    repo.patch(incident.id, status=IncidentStatus.REMEDIATING)
    # Third update
    repo.patch(incident.id, status=IncidentStatus.RESOLVED, resolution="Resolved successfully")

    fetched = repo.get(incident.id)
    assert fetched is not None
    events = [e.event for e in fetched.history]
    assert "INCIDENT_REGISTERED" in events
    assert events.count("INCIDENT_PATCHED") == 3
    assert fetched.status == IncidentStatus.RESOLVED
    assert fetched.resolution == "Resolved successfully"



def test_db2_timestamp_formatting_utc():
    """Verify that timezone-aware UTC datetimes format to standard Db2 TIMESTAMP syntax."""
    from datetime import datetime, timezone
    from app.db.repository import format_db2_timestamp, parse_db_timestamp

    dt = datetime(2026, 11, 8, 14, 25, 30, 123456, tzinfo=timezone.utc)
    formatted = format_db2_timestamp(dt)
    assert formatted == "2026-11-08 14:25:30.123456"
    assert "T" not in formatted
    assert "+" not in formatted

    parsed = parse_db_timestamp(formatted)
    assert parsed == dt
    assert parsed.tzinfo == timezone.utc


def test_db2_timestamp_formatting_non_zero_offset():
    """Verify that datetimes with non-zero offsets are normalized to UTC for Db2."""
    from datetime import datetime, timezone, timedelta
    from app.db.repository import format_db2_timestamp, parse_db_timestamp

    tz_offset = timezone(timedelta(hours=5, minutes=30))
    dt_offset = datetime(2026, 11, 8, 19, 55, 30, 654321, tzinfo=tz_offset)
    formatted = format_db2_timestamp(dt_offset)
    # 19:55:30.654321 +05:30 is 14:25:30.654321 UTC
    assert formatted == "2026-11-08 14:25:30.654321"

    parsed = parse_db_timestamp(formatted)
    expected_utc = dt_offset.astimezone(timezone.utc)
    assert parsed == expected_utc
    assert parsed.tzinfo == timezone.utc


def test_db2_timestamp_formatting_microseconds_preserved():
    """Verify microsecond preservation and boundary precision."""
    from datetime import datetime, timezone
    from app.db.repository import format_db2_timestamp, parse_db_timestamp

    dt_micro = datetime(2026, 1, 1, 0, 0, 0, 999999, tzinfo=timezone.utc)
    formatted = format_db2_timestamp(dt_micro)
    assert formatted == "2026-01-01 00:00:00.999999"

    parsed = parse_db_timestamp(formatted)
    assert parsed.microsecond == 999999


def test_db2_timestamp_none_and_native_handling():
    """Verify safe handling of None and native Db2 datetime objects."""
    from datetime import datetime, timezone
    from app.db.repository import format_db2_timestamp, parse_db_timestamp

    assert format_db2_timestamp(None) is None
    assert parse_db_timestamp(None) is None

    # Native naive datetime from ibm_db_dbi
    native_dt = datetime(2026, 11, 8, 12, 0, 0, 500000)
    parsed = parse_db_timestamp(native_dt)
    assert parsed.tzinfo == timezone.utc
    assert parsed.hour == 12
    assert parsed.microsecond == 500000
