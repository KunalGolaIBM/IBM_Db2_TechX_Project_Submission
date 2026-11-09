"""Phase 01B API behaviour that needs no database: auth ordering, roles, headers, CORS, docs."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from civiclens.agent.llm import llm_status
from civiclens.agent.tools import TOOL_NAMES, CivicLensToolkit
from civiclens.api.deps import get_db
from civiclens.api.main import create_app
from civiclens.auth import CAPABILITIES, capabilities_for
from civiclens.config import Settings, get_settings

A, R = "a" * 30, "r" * 30
ANA, REV = {"Authorization": f"Bearer {A}"}, {"Authorization": f"Bearer {R}"}


@pytest.fixture()
def tokens(monkeypatch):
    monkeypatch.setenv("CIVICLENS_AUTH_TOKENS", f"alice:analyst:{A},rita:reviewer:{R}")


def client(*, override_db: bool = True) -> TestClient:
    app = create_app()
    if override_db:
        app.dependency_overrides[get_db] = lambda: None  # must never be needed for these checks
    return TestClient(app)


# ----------------------------------------------------------------------------- identity
def test_me_returns_role_and_capabilities(tokens):
    c = client()
    ana = c.get("/api/me", headers=ANA).json()
    rev = c.get("/api/me", headers=REV).json()
    assert ana == {"user_id": "alice", "role": "analyst", "capabilities": list(CAPABILITIES["analyst"])}
    assert rev["role"] == "reviewer" and rev["capabilities"] == ["recommendation:decide"]
    assert "recommendation:decide" not in ana["capabilities"]  # separation of duties is visible to the UI
    assert capabilities_for("nobody") == ()


def test_me_requires_a_valid_token(tokens):
    c = client()
    assert c.get("/api/me").status_code == 401
    assert c.get("/api/me", headers={"Authorization": "Bearer wrong"}).status_code == 401


# ----------------------------------------------------------------------------- auth before database
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/overview"),
        ("GET", "/api/recommendations"),
        ("GET", "/api/investigations"),
        ("POST", "/api/complaints"),
    ],
)
def test_unauthenticated_requests_never_reach_the_database(tokens, monkeypatch, method, path):
    """No DB override and no DB credentials: an anonymous caller must get 401, not a 503 that
    would reveal an outage (or, with a working DB, cost a connection)."""
    monkeypatch.delenv("DB2_PASSWORD", raising=False)
    r = client(override_db=False).request(method, path, json={} if method == "POST" else None)
    assert r.status_code == 401


def test_authenticated_request_with_database_down_is_a_generic_503(tokens, monkeypatch):
    monkeypatch.delenv("DB2_PASSWORD", raising=False)
    r = client(override_db=False).get("/api/overview", headers=ANA)
    assert r.status_code == 503 and r.json()["detail"]["code"] == "DB_UNAVAILABLE"


# ----------------------------------------------------------------------------- complaint intake
def test_complaint_creation_is_analyst_only(tokens):
    c = client()
    body = {"category": "POTHOLE", "title": "Hole", "description": "Deep hole", "latitude": 1, "longitude": 1}
    assert c.post("/api/complaints", json=body).status_code == 401
    forbidden = c.post("/api/complaints", json=body, headers=REV)
    assert forbidden.status_code == 403 and forbidden.json()["detail"]["code"] == "FORBIDDEN"
    assert c.post("/api/complaints", json={"category": "NOPE"}, headers=ANA).status_code == 422


# ----------------------------------------------------------------------------- hardening
def test_security_headers_on_api_responses():
    r = client().get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["referrer-policy"] == "no-referrer"


def test_interactive_docs_are_disabled_in_production(monkeypatch):
    dev = client().get("/openapi.json")
    assert dev.status_code == 200
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()  # settings are cached per process
    prod = client()
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert prod.get(path).status_code == 404
    assert prod.get("/api/health").status_code == 200


def test_cors_allows_only_configured_origins(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.org, http://localhost:5173")
    get_settings.cache_clear()
    c = client()
    ok = c.options(
        "/api/me",
        headers={
            "Origin": "https://app.example.org",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert ok.headers.get("access-control-allow-origin") == "https://app.example.org"
    assert "authorization" in ok.headers.get("access-control-allow-headers", "").lower()
    bad = c.options(
        "/api/me",
        headers={"Origin": "https://evil.example.net", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in bad.headers
    assert "access-control-allow-credentials" not in ok.headers  # bearer tokens, never cookies


@pytest.mark.parametrize("bad", ["*", "https://*.example.org", "https://x.example.org/path", "ftp://x.org"])
def test_cors_rejects_wildcards_and_malformed_origins(bad):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_origins=bad)


# ----------------------------------------------------------------------------- LLM status & tool names
def test_llm_status_never_exposes_secrets():
    off = llm_status(Settings(_env_file=None))
    assert off == {"configured": False, "provider": "none", "model": None, "problem": None}
    partial = llm_status(
        Settings(_env_file=None, llm_provider="anthropic", anthropic_api_key="sk-secret-value")
    )
    assert partial["configured"] is False and "LLM_MODEL is not set." in partial["problem"]
    assert "sk-secret-value" not in str(partial)
    missing_key = llm_status(Settings(_env_file=None, llm_provider="openai", llm_model="m"))
    assert missing_key["configured"] is False and "OPENAI_API_KEY is not set." in missing_key["problem"]


def test_tool_names_constant_matches_the_real_toolkit():
    names = [t.name for t in CivicLensToolkit(object(), investigation_id=None).tools()]
    assert tuple(names) == TOOL_NAMES
