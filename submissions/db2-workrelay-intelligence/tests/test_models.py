from datetime import datetime, timezone
from app.models.incident import (
    ActionStatus,
    Incident,
    IncidentAction,
    IncidentCreateRequest,
    IncidentEvent,
    IncidentSeverity,
    IncidentStatus,
    IncidentUpdateRequest,
)


def test_incident_creation_and_defaults():
    inc = Incident(
        title="Payment gateway timeout",
        description="High volume of timeout exceptions on stripe webhooks",
        service="payment-gateway",
    )
    assert inc.id.startswith("INC-")
    assert inc.severity == IncidentSeverity.MEDIUM
    assert inc.status == IncidentStatus.OPEN
    assert inc.current_step == "incident_received"
    assert len(inc.history) == 0
    assert len(inc.actions) == 0
    assert inc.created_at <= datetime.now(timezone.utc)


def test_incident_record_event():
    inc = Incident(
        title="Cache eviction",
        description="Redis memory high",
        service="cache",
    )
    evt = inc.record_event("TRIAGE_STARTED", step="triaging", details={"actor": "sre"})
    assert len(inc.history) == 1
    assert evt.event == "TRIAGE_STARTED"
    assert evt.step == "triaging"
    assert evt.details["actor"] == "sre"
    assert evt.status == IncidentStatus.OPEN


def test_incident_request_models():
    req = IncidentCreateRequest(
        title="DB Deadlock",
        description="Transaction lock wait timeout",
        service="db2",
        severity=IncidentSeverity.HIGH,
    )
    assert req.title == "DB Deadlock"
    assert req.severity == IncidentSeverity.HIGH

    patch = IncidentUpdateRequest(
        status=IncidentStatus.RESOLVED,
        resolution="Lock killed and transaction committed",
    )
    assert patch.status == IncidentStatus.RESOLVED
    assert patch.resolution is not None
