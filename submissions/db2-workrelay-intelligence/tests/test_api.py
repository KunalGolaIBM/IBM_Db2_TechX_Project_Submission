import pytest
from fastapi import HTTPException
from app.api import create_app
from app.db.connection import Db2ConnectionManager
from app.db.repository import Db2IncidentRepository
from app.agent.coordinator import IncidentCoordinator
from app.models.incident import (
    IncidentCreateRequest,
    IncidentUpdateRequest,
    IncidentSeverity,
    IncidentStatus,
)


class ApiTestClient:
    """
    Lightweight, zero-network test client for FastAPI endpoints.
    Invokes endpoint functions directly, avoiding ASGI socket blocking
    in sandboxed test environments.
    """

    def __init__(self, app):
        self.app = app
        self.routes = {}
        for r in app.routes:
            if hasattr(r, "path") and hasattr(r, "endpoint"):
                methods = getattr(r, "methods", {"GET"})
                for m in methods:
                    self.routes[(m.upper(), r.path)] = r.endpoint

    def get(self, path: str, **params):
        if path.startswith("/incidents/"):
            inc_id = path.split("/incidents/")[1]
            endpoint = self.routes.get(("GET", "/incidents/{incident_id}"))
            return endpoint(incident_id=inc_id)

        endpoint = self.routes.get(("GET", path))
        if not endpoint:
            raise ValueError(f"Route GET {path} not found")
        return endpoint(**params)

    def post(self, path: str, json: dict):
        endpoint = self.routes.get(("POST", path))
        if not endpoint:
            raise ValueError(f"Route POST {path} not found")

        if path == "/incidents":
            req = IncidentCreateRequest(**json)
            return endpoint(req)
        elif path == "/knowledge/query":
            return endpoint(json)
        elif path == "/knowledge/ingest":
            return endpoint(json)
        return endpoint(json)

    def patch(self, path: str, json: dict):
        if path.startswith("/incidents/"):
            inc_id = path.split("/incidents/")[1]
            endpoint = self.routes.get(("PATCH", "/incidents/{incident_id}"))
            req = IncidentUpdateRequest(**json)
            return endpoint(incident_id=inc_id, req=req)
        raise ValueError(f"Route PATCH {path} not found")


@pytest.fixture
def client():
    mgr = Db2ConnectionManager(use_mock=True)
    repo = Db2IncidentRepository(mgr)
    repo.init_schema_sqlite()
    coord = IncidentCoordinator(repo)
    app = create_app(repository=repo, coordinator=coord)
    return ApiTestClient(app)


def test_health_endpoint(client):
    res = client.get("/health")
    assert res.status in ("healthy", "degraded")
    assert res.service == "db2-workrelay-intelligence"
    assert res.db2_connected is True
    assert res.db2_mode == "sqlite_mock"
    assert res.ai_status["engine_ready"] is True


def test_create_and_retrieve_incident(client):
    payload = {
        "title": "Db2 Connection Timeout",
        "description": "Application pool unable to borrow connection within 5000ms",
        "service": "database",
        "severity": "HIGH",
    }
    create_res = client.post("/incidents", json=payload)
    created_data = create_res.incident
    inc_id = created_data.id
    assert inc_id.startswith("INC-")
    assert created_data.title == payload["title"]
    assert created_data.service == payload["service"]
    assert created_data.status in [IncidentStatus.RESOLVED, IncidentStatus.INVESTIGATING, IncidentStatus.OPEN]

    # Retrieve by ID
    get_res = client.get(f"/incidents/{inc_id}")
    assert get_res.incident.id == inc_id


def test_auto_classification_on_creation(client):
    payload = {
        "title": "Critical production outage on payment core",
        "description": "P0 database down and orders failing",
        "service": "payment-core",
    }
    res = client.post("/incidents", json=payload)
    data = res.incident
    assert data.severity == IncidentSeverity.CRITICAL


def test_list_incidents(client):
    client.post("/incidents", json={
        "title": "Minor warning",
        "description": "Disk 70% threshold warning",
        "service": "infra",
        "severity": "LOW",
    })
    res = client.get("/incidents", limit=10, offset=0)
    assert res.total >= 1
    assert len(res.items) >= 1


def test_patch_incident_status(client):
    create_res = client.post("/incidents", json={
        "title": "Temporary network blip",
        "description": "Packet loss observed",
        "service": "network",
    })
    inc_id = create_res.incident.id

    patch_res = client.patch(f"/incidents/{inc_id}", json={
        "status": "RESOLVED",
        "resolution": "Network routes re-converged",
    })
    data = patch_res.incident
    assert data.status == IncidentStatus.RESOLVED
    assert data.resolution == "Network routes re-converged"


def test_structured_error_handling_not_found(client):
    with pytest.raises(HTTPException) as excinfo:
        client.get("/incidents/INC-NONEXISTENT")
    assert excinfo.value.status_code == 404
    assert "not found" in excinfo.value.detail.lower()


def test_knowledge_query_endpoint(client):
    res = client.post("/knowledge/query", json={
        "query": "Db2 connection pool exhaustion and timeout",
        "service": "database",
    })
    assert res["matches_count"] >= 1
    assert "recommendation" in res
    assert "matches" in res


def test_knowledge_ingest_endpoint(client):
    res = client.post("/knowledge/ingest", json={
        "doc_id": "RUNBOOK-INGEST-01",
        "title": "Ingested Runbook",
        "category": "test",
        "service": "test-service",
        "content": "Test content for runbook ingestion",
        "resolution_steps": "Follow test resolution",
    })
    assert res["status"] == "ingested"
    assert res["doc_id"] == "RUNBOOK-INGEST-01"
