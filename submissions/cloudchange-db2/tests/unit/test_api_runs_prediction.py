"""Unit tests verifying that Run API populates findings and predictions from ImpactPredictor."""

import json
from pathlib import Path
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def test_create_run_populates_findings_and_predictions():
    # Load update_ec2_instance_type.json fixture
    plan_path = FIXTURES_DIR / "update_ec2_instance_type.json"
    with open(plan_path, "r", encoding="utf-8") as f:
        plan_data = json.load(f)

    # 1. Create Run
    create_resp = client.post("/api/v1/runs", json=plan_data)
    assert create_resp.status_code == 201
    run_id = create_resp.json()["run_id"]

    # 2. Retrieve Run
    get_resp = client.get(f"/api/v1/runs/{run_id}")
    assert get_resp.status_code == 200
    run_data = get_resp.json()

    # Verify findings
    findings = run_data["findings"]
    assert len(findings) >= 1
    cost_finding = next((f for f in findings if f["rule_id"] == "CC-EC2-COST-001"), None)
    assert cost_finding is not None
    assert cost_finding["category"] == "COST"
    assert cost_finding["severity"] == "MEDIUM"

    # Verify predictions
    predictions = run_data["predictions"]
    assert len(predictions) >= 1
    cost_pred = next((p for p in predictions if p["metric"] == "instance_type"), None)
    assert cost_pred is not None
    assert cost_pred["expected_value"] == "t3.large"
    assert cost_pred["direction"] == "SCALE_UP"
    assert cost_pred["verification_approach"] == "EXACT_MATCH"

    # Verify evidence requirement attached to prediction
    evidence_req = cost_pred["evidence_requirement"]
    assert evidence_req is not None
    assert evidence_req["service"] == "ec2"
    assert evidence_req["resource_type"] == "instance"
    assert evidence_req["field"] == "instance_type"
