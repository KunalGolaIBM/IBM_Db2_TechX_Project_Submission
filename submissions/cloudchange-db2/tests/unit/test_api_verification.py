"""Unit tests for Post-Deployment Verification API Endpoints (Phase F4)."""

import json
from pathlib import Path
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from backend.app.api.runs import get_verification_orchestrator
from backend.app.aws.clients import AWSClientFactory
from backend.app.engine.orchestrator import VerificationOrchestrator
from backend.app.main import app

client = TestClient(app)
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def test_api_submit_verification_success():
    """Verify POST /api/v1/runs/{id}/verification executes orchestrator and persists results."""
    # 1. Create Run from fixture
    plan_path = FIXTURES_DIR / "update_ec2_instance_type.json"
    with open(plan_path, "r", encoding="utf-8") as f:
        plan_data = json.load(f)

    create_resp = client.post("/api/v1/runs", json=plan_data)
    assert create_resp.status_code == 201
    run_id = create_resp.json()["run_id"]

    # 2. Mock AWS EC2 describe_instances matching expected t3.large and enabled monitoring
    mock_session = MagicMock()
    mock_ec2 = MagicMock()
    mock_session.client.return_value = mock_ec2
    mock_ec2.describe_instances.return_value = {
        "Reservations": [
            {
                "Instances": [
                    {
                        "InstanceId": "i-0123456789abcdef0",
                        "InstanceType": "t3.large",
                        "Monitoring": {"State": "enabled"},
                        "State": {"Name": "running"},
                    }
                ]
            }
        ]
    }

    mock_factory = AWSClientFactory(session=mock_session)
    mock_orchestrator = VerificationOrchestrator(client_factory=mock_factory)

    app.dependency_overrides[get_verification_orchestrator] = lambda: mock_orchestrator

    try:
        # 3. Submit Terraform state artifact
        state_artifact = {
            "format_version": "1.0",
            "resources": [
                {
                    "mode": "managed",
                    "type": "aws_instance",
                    "name": "api",
                    "instances": [
                        {"attributes": {"id": "i-0123456789abcdef0"}}
                    ],
                }
            ],
        }

        verify_resp = client.post(f"/api/v1/runs/{run_id}/verification", json=state_artifact)
        assert verify_resp.status_code == 200
        verify_data = verify_resp.json()
        assert verify_data["run_id"] == run_id
        assert verify_data["status"] == "VERIFIED"

        # 4. GET /api/v1/runs/{id}/verification returns verification results
        get_ver_resp = client.get(f"/api/v1/runs/{run_id}/verification")
        assert get_ver_resp.status_code == 200
        get_ver_data = get_ver_resp.json()
        assert get_ver_data["status"] == "VERIFIED"
        assert len(get_ver_data["results"]) == 2
        for r in get_ver_data["results"]:
            assert r["status"] == "VERIFIED"

        # 5. GET /api/v1/runs/{id} reflects updated status and verification_results
        get_run_resp = client.get(f"/api/v1/runs/{run_id}")
        assert get_run_resp.status_code == 200
        run_data = get_run_resp.json()
        assert run_data["status"] == "VERIFIED"
        assert len(run_data["verification_results"]) == 2

    finally:
        app.dependency_overrides.pop(get_verification_orchestrator, None)


def test_api_submit_verification_mismatch():
    """Verify that contradictory observed state results in VERIFICATION_FAILED."""
    # 1. Create Run
    plan_path = FIXTURES_DIR / "update_ec2_instance_type.json"
    with open(plan_path, "r", encoding="utf-8") as f:
        plan_data = json.load(f)

    create_resp = client.post("/api/v1/runs", json=plan_data)
    assert create_resp.status_code == 201
    run_id = create_resp.json()["run_id"]

    # 2. Mock AWS EC2 returning t3.small instead of expected t3.large
    mock_session = MagicMock()
    mock_ec2 = MagicMock()
    mock_session.client.return_value = mock_ec2
    mock_ec2.describe_instances.return_value = {
        "Reservations": [
            {
                "Instances": [
                    {
                        "InstanceId": "i-0123456789abcdef0",
                        "InstanceType": "t3.small",
                        "Monitoring": {"State": "enabled"},
                        "State": {"Name": "running"},
                    }
                ]
            }
        ]
    }

    mock_factory = AWSClientFactory(session=mock_session)
    mock_orchestrator = VerificationOrchestrator(client_factory=mock_factory)

    app.dependency_overrides[get_verification_orchestrator] = lambda: mock_orchestrator

    try:
        state_artifact = {
            "resources": [
                {
                    "mode": "managed",
                    "type": "aws_instance",
                    "name": "api",
                    "instances": [{"attributes": {"id": "i-0123456789abcdef0"}}],
                }
            ]
        }

        verify_resp = client.post(f"/api/v1/runs/{run_id}/verification", json=state_artifact)
        assert verify_resp.status_code == 200
        assert verify_resp.json()["status"] == "VERIFICATION_FAILED"

        get_ver_resp = client.get(f"/api/v1/runs/{run_id}/verification")
        assert get_ver_resp.status_code == 200
        assert get_ver_resp.json()["status"] == "VERIFICATION_FAILED"
        assert any(r["status"] == "MISMATCH" for r in get_ver_resp.json()["results"])

    finally:
        app.dependency_overrides.pop(get_verification_orchestrator, None)


def test_api_verification_nonexistent_run_404():
    """Verify 404 RUN_NOT_FOUND when run does not exist."""
    resp = client.post("/api/v1/runs/nonexistent-uuid-1234/verification", json={})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RUN_NOT_FOUND"

    resp_get = client.get("/api/v1/runs/nonexistent-uuid-1234/verification")
    assert resp_get.status_code == 404
    assert resp_get.json()["error"]["code"] == "RUN_NOT_FOUND"
