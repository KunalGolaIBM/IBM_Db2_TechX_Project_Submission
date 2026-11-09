import pytest
from app.db.connection import Db2ConnectionManager
from app.db.repository import Db2IncidentRepository
from app.models.incident import (
    Incident,
    IncidentAction,
    IncidentSeverity,
    IncidentStatus,
)


@pytest.fixture
def repo():
    # Use SQLite in-memory for testing Db2 repository logic cleanly
    mgr = Db2ConnectionManager(use_mock=True)
    repository = Db2IncidentRepository(mgr)
    repository.init_schema()
    return repository


def test_create_and_get_incident(repo):
    inc = Incident(
        title="Db2 SQL0964C Log Full",
        description="Transaction log for database testdb is full",
        service="db2-database",
        severity=IncidentSeverity.CRITICAL,
    )
    saved = repo.create(inc)
    assert saved.id == inc.id

    fetched = repo.get(inc.id)
    assert fetched is not None
    assert fetched.id == inc.id
    assert fetched.title == "Db2 SQL0964C Log Full"
    assert fetched.severity == IncidentSeverity.CRITICAL
    assert len(fetched.history) >= 1
    assert fetched.history[0].event == "INCIDENT_REGISTERED"


def test_list_incidents_filtering(repo):
    inc1 = Incident(
        title="Auth Failure",
        description="JWT token invalid",
        service="auth",
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.OPEN,
    )
    inc2 = Incident(
        title="Billing Timeout",
        description="Stripe slow response",
        service="billing",
        severity=IncidentSeverity.LOW,
        status=IncidentStatus.RESOLVED,
    )
    repo.create(inc1)
    repo.create(inc2)

    # Filter by service
    auth_list, count = repo.list(service="auth")
    assert count == 1
    assert auth_list[0].service == "auth"

    # Filter by severity
    high_list, count = repo.list(severity="HIGH")
    assert count == 1
    assert high_list[0].title == "Auth Failure"

    # Filter by status
    res_list, count = repo.list(status="RESOLVED")
    assert count >= 1


def test_patch_incident(repo):
    inc = Incident(
        title="Frontend CDN Delay",
        description="Assets serving with latency",
        service="cdn",
        severity=IncidentSeverity.LOW,
    )
    repo.create(inc)

    patched = repo.patch(
        incident_id=inc.id,
        status=IncidentStatus.RESOLVED,
        resolution="CDN cache purged successfully",
    )
    assert patched is not None
    assert patched.status == IncidentStatus.RESOLVED
    assert patched.resolution == "CDN cache purged successfully"

    # Verify event recorded in history
    fetched = repo.get(inc.id)
    events = [e.event for e in fetched.history]
    assert "INCIDENT_PATCHED" in events


def test_parameterized_query_safety(repo):
    # Test injection-prone strings are stored safely
    malicious_title = "Title with '; DROP TABLE incidents; --"
    inc = Incident(
        title=malicious_title,
        description="Testing SQL injection resistance",
        service="security",
    )
    repo.create(inc)
    fetched = repo.get(inc.id)
    assert fetched is not None
    assert fetched.title == malicious_title
