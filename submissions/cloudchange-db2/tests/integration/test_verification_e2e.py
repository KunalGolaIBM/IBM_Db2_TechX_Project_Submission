"""End-to-end integration tests for multi-resource plan verification."""

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


def test_e2e_multi_resource_plan_verification_success():
    """Verify end-to-end verification across multiple resources (EC2, SG, RDS)."""
    # 1. Ingest multiple_resources.json plan
    plan_path = FIXTURES_DIR / "multiple_resources.json"
    with open(plan_path, "r", encoding="utf-8") as f:
        plan_data = json.load(f)

    create_resp = client.post("/api/v1/runs", json=plan_data)
    assert create_resp.status_code == 201
    run_data = create_resp.json()
    run_id = run_data["run_id"]
    predictions = run_data["predictions"]

    # 2. Setup mock AWS responses for all services
    mock_session = MagicMock()
    mock_ec2 = MagicMock()
    mock_rds = MagicMock()

    mock_session.client.side_effect = lambda svc, region_name: mock_ec2 if svc == "ec2" else mock_rds

    # Mock SG response with port 80 ingress
    mock_ec2.describe_security_groups.return_value = {
        "SecurityGroups": [
            {
                "GroupId": "sg-0123456789abcdef0",
                "GroupName": "app_sg",
                "IpPermissions": [
                    {
                        "IpProtocol": "tcp",
                        "FromPort": 80,
                        "ToPort": 80,
                        "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                    }
                ],
            }
        ]
    }

    # Mock RDS response with replaced/updated storage config
    mock_rds.describe_db_instances.return_value = {
        "DBInstances": [
            {
                "DBInstanceIdentifier": "app-db-v2",
                "DbiResourceId": "db-NEWRESOURCEID-2",
                "DBInstanceClass": "db.t3.micro",
                "DBInstanceStatus": "available",
                "AllocatedStorage": 40,
                "StorageType": "gp2",
                "StorageEncrypted": False,
            }
        ]
    }

    mock_factory = AWSClientFactory(session=mock_session)
    mock_orchestrator = VerificationOrchestrator(client_factory=mock_factory)

    app.dependency_overrides[get_verification_orchestrator] = lambda: mock_orchestrator

    try:
        # 3. Submit multi-resource state fixture
        state_path = FIXTURES_DIR / "state_multiple_resources.json"
        with open(state_path, "r", encoding="utf-8") as f:
            state_data = json.load(f)

        verify_resp = client.post(f"/api/v1/runs/{run_id}/verification", json=state_data)
        assert verify_resp.status_code == 200
        verify_data = verify_resp.json()
        assert verify_data["status"] == "VERIFIED"

        # 4. Verify report details
        get_resp = client.get(f"/api/v1/runs/{run_id}/verification")
        assert get_resp.status_code == 200
        results = get_resp.json()["results"]
        assert len(results) == len(predictions)
        for r in results:
            assert r["status"] == "VERIFIED"

    finally:
        app.dependency_overrides.pop(get_verification_orchestrator, None)


def test_e2e_rds_deletion_verification():
    """Verify end-to-end RDS deletion confirmation using ResourceNotFoundError."""
    plan_path = FIXTURES_DIR / "delete_rds.json"
    with open(plan_path, "r", encoding="utf-8") as f:
        plan_data = json.load(f)

    create_resp = client.post("/api/v1/runs", json=plan_data)
    assert create_resp.status_code == 201
    run_id = create_resp.json()["run_id"]

    mock_session = MagicMock()
    mock_rds = MagicMock()
    mock_session.client.return_value = mock_rds

    from backend.app.aws.errors import ResourceNotFoundError
    mock_rds.describe_db_instances.side_effect = ResourceNotFoundError(
        resource_id="db-prod",
        resource_type="RDS DB instance",
    )

    mock_factory = AWSClientFactory(session=mock_session)
    mock_orchestrator = VerificationOrchestrator(client_factory=mock_factory)

    app.dependency_overrides[get_verification_orchestrator] = lambda: mock_orchestrator

    try:
        state_path = FIXTURES_DIR / "state_delete_rds.json"
        with open(state_path, "r", encoding="utf-8") as f:
            state_data = json.load(f)

        verify_resp = client.post(f"/api/v1/runs/{run_id}/verification", json=state_data)
        assert verify_resp.status_code == 200
        assert verify_resp.json()["status"] == "VERIFIED"

        get_resp = client.get(f"/api/v1/runs/{run_id}/verification")
        assert get_resp.status_code == 200
        assert get_resp.json()["results"][0]["status"] == "VERIFIED"
        assert get_resp.json()["results"][0]["observed_value"] == "RESOURCE_NOT_FOUND"

    finally:
        app.dependency_overrides.pop(get_verification_orchestrator, None)
