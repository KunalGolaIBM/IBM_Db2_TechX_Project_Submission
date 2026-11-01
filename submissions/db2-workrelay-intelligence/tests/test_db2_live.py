import os
import pytest
from app.db.connection import Db2ConnectionManager, IBM_DB_AVAILABLE
from app.db.repository import Db2IncidentRepository
from app.models.incident import Incident, IncidentSeverity, IncidentStatus

# Only run if genuine Db2 credentials and native driver are present
is_db2_configured = (
    IBM_DB_AVAILABLE
    and bool(os.getenv("DB2_HOST"))
    and os.getenv("DB2_HOST").lower() != "mock"
    and not os.getenv("DB2_USE_MOCK", "").lower() in ("true", "1", "yes")
)


@pytest.mark.skipif(
    not is_db2_configured,
    reason="Live IBM Db2 instance not configured or ibm_db native driver is not installed.",
)
def test_live_db2_connection_probe():
    """Validates real connectivity against an active IBM Db2 Community Edition or Cloud instance."""
    mgr = Db2ConnectionManager(use_mock=False)
    assert mgr.is_db2_active is True
    health = mgr.check_health()
    assert health["connected"] is True
    assert health["mode"] == "ibm_db"
    assert health["error"] is None


@pytest.mark.skipif(
    not is_db2_configured,
    reason="Live IBM Db2 instance not configured or ibm_db native driver is not installed.",
)
def test_live_db2_schema_and_crud():
    """Validates native Db2 DDL initialization and transactional CRUD on live Db2."""
    mgr = Db2ConnectionManager(use_mock=False)
    repo = Db2IncidentRepository(mgr)

    # Execute schema_db2.sql on genuine Db2 instance
    repo.init_schema_db2()

    test_inc = Incident(
        title="Live Db2 Verification Incident",
        description="Verifying native ibm_db transactional execution against Db2 Community Edition",
        service="live-db2-test",
        severity=IncidentSeverity.HIGH,
    )
    created = repo.create(test_inc)
    assert created.id == test_inc.id

    fetched = repo.get(test_inc.id)
    assert fetched is not None
    assert fetched.title == test_inc.title

    patched = repo.patch(test_inc.id, status=IncidentStatus.RESOLVED, resolution="Live Db2 verified")
    assert patched is not None
    assert patched.status == IncidentStatus.RESOLVED

