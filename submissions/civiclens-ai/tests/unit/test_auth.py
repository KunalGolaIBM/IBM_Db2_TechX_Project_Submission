import pytest
from fastapi.testclient import TestClient

from civiclens.api.deps import get_db
from civiclens.api.main import create_app
from civiclens.auth import AuthConfigError, parse_tokens

A, R = "a" * 30, "r" * 30


def test_parse_tokens_roles_and_ids():
    table = parse_tokens(f"alice:analyst:{A}, rita:reviewer:{R}")
    assert table[A].user_id == "alice" and table[A].role == "analyst"
    assert table[R].role == "reviewer"


@pytest.mark.parametrize(
    "raw",
    [
        "alice:analyst:short",  # weak token
        f"alice:admin:{A}",  # unknown role
        f"Alice Bad:analyst:{A}",  # invalid id
        f"alice:analyst:{A},bob:reviewer:{A}",  # duplicate token
        f"alice:analyst:{A},alice:reviewer:{R}",  # duplicate id
        "justonepart",
    ],
)
def test_parse_tokens_rejects_bad_config(raw):
    with pytest.raises(AuthConfigError):
        parse_tokens(raw)


def _client(monkeypatch, tokens: str | None = f"alice:analyst:{A},rita:reviewer:{R}"):
    if tokens is not None:
        monkeypatch.setenv("CIVICLENS_AUTH_TOKENS", tokens)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: None  # auth must fail/pass before any DB use
    return TestClient(app)


def test_fails_closed_when_auth_not_configured(monkeypatch):
    r = _client(monkeypatch, None).get("/api/investigations")
    assert r.status_code == 503 and r.json()["detail"]["code"] == "AUTH_NOT_CONFIGURED"


def test_a_misconfigured_server_fails_closed_without_naming_users_or_tokens(monkeypatch, caplog):
    weak = "w3akT0ken"
    with caplog.at_level("ERROR", logger="civiclens"):
        r = _client(monkeypatch, f"alice:analyst:{weak}").get(
            "/api/investigations", headers={"Authorization": f"Bearer {weak}"}
        )
    assert r.status_code == 503 and r.json()["detail"]["code"] == "AUTH_MISCONFIGURED"
    assert "alice" not in r.text and weak not in r.text  # the caller learns nothing about the configuration
    assert (
        "alice" in caplog.text and weak not in caplog.text
    )  # the operator can still see why (never the token)


def test_missing_and_wrong_token_are_401(monkeypatch):
    c = _client(monkeypatch)
    assert c.get("/api/investigations").status_code == 401
    r = c.get("/api/investigations", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401 and r.json()["detail"]["code"] == "UNAUTHENTICATED"


def test_roles_are_enforced_before_the_database(monkeypatch):
    c = _client(monkeypatch)
    ana, rev = {"Authorization": f"Bearer {A}"}, {"Authorization": f"Bearer {R}"}
    body = {"title": "Potholes", "question": "Where are potholes?"}
    assert c.post("/api/investigations", json=body, headers=rev).status_code == 403
    assert (
        c.post("/api/recommendations/1/decision", json={"decision": "APPROVED"}, headers=ana).status_code
        == 403
    )
    assert c.post("/api/investigations/1/run", headers=rev).status_code == 403


def test_reviewer_identity_cannot_be_supplied_in_the_body(monkeypatch):
    c = _client(monkeypatch)
    r = c.post(
        "/api/recommendations/1/decision",
        json={"decision": "APPROVED", "reviewer": "someone-else"},
        headers={"Authorization": f"Bearer {R}"},
    )
    assert r.status_code == 422


def test_rejection_requires_a_comment(monkeypatch):
    c = _client(monkeypatch)
    r = c.post(
        "/api/recommendations/1/decision",
        json={"decision": "REJECTED"},
        headers={"Authorization": f"Bearer {R}"},
    )
    assert r.status_code == 422
