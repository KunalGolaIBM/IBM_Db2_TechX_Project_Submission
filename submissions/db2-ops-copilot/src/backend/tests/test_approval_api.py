"""Offline API coverage for proposal creation and human approval decisions."""

from __future__ import annotations

from datetime import timedelta

from app.core.config import get_settings


def _action(table: str = "DEMO_SERVERS") -> dict:
    return {
        "action_type": "runstats",
        "params": {"schema": "APP", "table": table},
        "rationale": "Refresh stale optimizer statistics.",
    }


def _propose(client, actions: list[dict] | None = None):
    return client.post(
        "/api/v1/agent/propose",
        json={"actions": actions or [_action()], "session_id": "demo-session"},
    )


def test_proposal_lists_and_retrieves_pending_approval_without_execution(client):
    response = _propose(client)

    assert response.status_code == 200
    body = response.json()
    approval = body["approvals"][0]
    assert body["tool_calls"] == 1
    assert body["mock"] is True
    assert approval["status"] == "PENDING"
    assert approval["statement"] == (
        "CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE APP.DEMO_SERVERS "
        "WITH DISTRIBUTION AND DETAILED INDEXES ALL')"
    )
    assert client.app.state.registry.database.simulated_admin_statements == []

    listed = client.get("/api/v1/approvals")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["approvals"][0]["id"] == approval["id"]
    assert listed.json()["execution_mode"] == "mock_simulated"

    detail = client.get(f"/api/v1/approvals/{approval['id']}")
    assert detail.status_code == 200
    assert detail.json()["params"] == {"schema": "APP", "table": "DEMO_SERVERS"}


def test_invalid_action_batch_is_rejected_without_partial_approval(client):
    response = _propose(client, [_action(), {
        "action_type": "create_index",
        "params": {"schema": "APP", "table": "DEMO_SERVERS"},
        "rationale": "Missing required column.",
    }])

    assert response.status_code == 422
    assert client.get("/api/v1/approvals").json()["total"] == 0
    assert client.app.state.registry.database.simulated_admin_statements == []


def test_proposal_enforces_configured_tool_call_limit(client):
    limit = get_settings().agent_max_tool_calls
    response = _propose(client, [_action(f"TABLE_{i}") for i in range(limit + 1)])

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "AGENT_TOOL_LIMIT"
    assert response.json()["error"]["detail"] == {
        "requested": limit + 1,
        "max_tool_calls": limit,
    }
    assert client.get("/api/v1/approvals").json()["total"] == 0


def test_invalid_and_missing_approval_ids(client):
    assert client.get("/api/v1/approvals/not-an-id").status_code == 422
    missing = client.get("/api/v1/approvals/apr_000000000000")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "APPROVAL_NOT_FOUND"


def test_decision_validation_rejection_and_actor_sanitization(client):
    invalid_id = _propose(client).json()["approvals"][0]["id"]
    invalid = client.post(
        f"/api/v1/approvals/{invalid_id}/decision",
        json={"decision": "DELETE", "actor": "operator"},
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "APPROVAL_INVALID_DECISION"
    assert client.get(f"/api/v1/approvals/{invalid_id}").json()["status"] == "PENDING"
    assert client.app.state.registry.database.simulated_admin_statements == []

    rejected = client.post(
        f"/api/v1/approvals/{invalid_id}/decision",
        json={"decision": "reject", "actor": "ops\nadmin", "reason": "Not needed"},
    )
    assert rejected.status_code == 200
    approval = rejected.json()["approval"]
    assert approval["status"] == "REJECTED"
    assert approval["decided_by"] == "ops admin"
    assert client.app.state.registry.database.simulated_admin_statements == []


def test_approval_is_simulated_and_audited_in_mock_mode(client):
    approval_id = _propose(client).json()["approvals"][0]["id"]
    response = client.post(
        f"/api/v1/approvals/{approval_id}/decision",
        json={"decision": "approve", "actor": "operator"},
    )

    assert response.status_code == 200
    approval = response.json()["approval"]
    assert approval["status"] == "EXECUTED"
    assert approval["execution"]["simulated"] is True
    assert "not executed against any database" in approval["execution"]["detail"]
    assert client.app.state.registry.database.simulated_admin_statements == [
        approval["statement"]
    ]
    audit = client.app.state.registry.audit.list_recent(20)
    assert [entry.status for entry in audit if entry.operation == "approval"] == [
        "EXECUTED",
        "APPROVED",
        "APPROVAL_REQUESTED",
    ]

    already_decided = client.post(
        f"/api/v1/approvals/{approval_id}/decision",
        json={"decision": "approve"},
    )
    assert already_decided.status_code == 409


def test_expired_approval_cannot_be_approved_and_expiry_is_audited(client):
    approval_id = _propose(client).json()["approvals"][0]["id"]
    approval = client.app.state.approval_store.get(approval_id)
    approval.expires_at = approval.created_at - timedelta(seconds=1)

    response = client.post(
        f"/api/v1/approvals/{approval_id}/decision",
        json={"decision": "approve"},
    )

    assert response.status_code == 410
    assert response.json()["error"]["code"] == "APPROVAL_EXPIRED"
    assert client.get(f"/api/v1/approvals/{approval_id}").json()["status"] == "EXPIRED"
    audit = client.app.state.registry.audit.list_recent(20)
    assert any(entry.status == "EXPIRED" and entry.operation == "approval" for entry in audit)
    assert client.app.state.registry.database.simulated_admin_statements == []


def test_proposal_rejects_reserved_schema(client):
    action = _action()
    action["params"]["schema"] = "SYSCAT"
    response = _propose(client, [action])

    assert response.status_code == 422
    assert client.get("/api/v1/approvals").json()["total"] == 0
