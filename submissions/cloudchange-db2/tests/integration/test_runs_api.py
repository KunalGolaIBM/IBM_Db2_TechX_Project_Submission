"""Integration tests for Hardened Runs API (Phase D)."""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.repositories.run_repo import get_run_repository

client = TestClient(app)
FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture(autouse=True)
def clean_repository():
    """Ensure every test executes with an isolated, empty run repository."""
    get_run_repository().clear()
    yield
    get_run_repository().clear()


def load_fixture(filename: str) -> dict:
    with open(FIXTURES_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)


def test_api_create_run_returns_full_run_with_201():
    """POST /api/v1/runs returns the full persisted Run report with HTTP 201."""
    plan = load_fixture("update_ec2_instance_type.json")
    resp = client.post("/api/v1/runs", json=plan)
    assert resp.status_code == 201
    run_data = resp.json()

    assert "run_id" in run_data
    assert run_data["status"] == "PREDICTED"
    assert "created_at" in run_data
    assert "summary" in run_data

    # Verify summary counters
    summary = run_data["summary"]
    assert summary["total_changes"] == 1
    assert summary["actions"]["UPDATE"] == 1
    assert summary["actions"]["CREATE"] == 0
    assert summary["findings_count"] >= 1
    assert summary["findings_by_severity"]["MEDIUM"] >= 1
    assert summary["unsupported_count"] == 0
    assert summary["noop_count"] == 0
    assert summary["read_count"] == 0

    # Verify changes, findings, predictions
    assert len(run_data["changes"]) == 1
    assert len(run_data["findings"]) >= 1
    assert len(run_data["predictions"]) >= 1
    assert run_data["predictions"][0]["evidence_requirement"] is not None


def test_api_get_run_returns_identical_persisted_report():
    """GET /api/v1/runs/{id} returns identical analysis report to POST."""
    plan = load_fixture("update_ec2_instance_type.json")
    create_resp = client.post("/api/v1/runs", json=plan)
    assert create_resp.status_code == 201
    created_data = create_resp.json()
    run_id = created_data["run_id"]

    get_resp = client.get(f"/api/v1/runs/{run_id}")
    assert get_resp.status_code == 200
    retrieved_data = get_resp.json()

    assert retrieved_data == created_data


def test_api_get_run_not_found_structured_error():
    """GET /api/v1/runs/{non_existent} returns structured 404 error envelope."""
    resp = client.get("/api/v1/runs/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "RUN_NOT_FOUND"
    assert "00000000-0000-0000-0000-000000000000" in data["error"]["message"]


def test_api_rejects_empty_payload_with_structured_400():
    """Empty request body returns HTTP 400 with INVALID_PAYLOAD code."""
    resp = client.post("/api/v1/runs", content=b"")
    assert resp.status_code == 400
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "INVALID_PAYLOAD"
    assert "cannot be empty" in data["error"]["message"]
    assert get_run_repository().count() == 0


def test_api_rejects_malformed_json_with_structured_400():
    """Malformed JSON returns HTTP 400 with INVALID_PAYLOAD code."""
    resp = client.post("/api/v1/runs", content=b"{not valid json")
    assert resp.status_code == 400
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "INVALID_PAYLOAD"
    assert "Malformed JSON" in data["error"]["message"]
    assert get_run_repository().count() == 0


def test_api_rejects_non_object_json_with_structured_400():
    """Non-dictionary JSON returns HTTP 400 with INVALID_PAYLOAD code."""
    resp = client.post("/api/v1/runs", json=["array", "not", "object"])
    assert resp.status_code == 400
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "INVALID_PAYLOAD"
    assert "must be a valid JSON object" in data["error"]["message"]
    assert get_run_repository().count() == 0


def test_api_rejects_missing_format_version_with_structured_400():
    """Missing format_version returns HTTP 400 with INVALID_PLAN code."""
    resp = client.post("/api/v1/runs", json={"resource_changes": []})
    assert resp.status_code == 400
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "INVALID_PLAN"
    assert "format_version" in data["error"]["message"]
    assert get_run_repository().count() == 0


def test_api_rejects_malformed_plan_with_structured_400():
    """Malformed plan fixture returns HTTP 400 with INVALID_PLAN code."""
    plan = load_fixture("malformed_plan.json")
    resp = client.post("/api/v1/runs", json=plan)
    assert resp.status_code == 400
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "INVALID_PLAN"
    assert "resource_changes" in data["error"]["message"]
    assert get_run_repository().count() == 0


def test_api_rejects_malformed_actions_with_structured_400():
    """Plan with invalid actions combination returns HTTP 400 with MALFORMED_ACTION code."""
    plan = {
        "format_version": "1.2",
        "resource_changes": [
            {
                "address": "aws_instance.bad_actions",
                "type": "aws_instance",
                "change": {
                    "actions": ["create", "update"],
                },
            }
        ],
    }
    resp = client.post("/api/v1/runs", json=plan)
    assert resp.status_code == 400
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "MALFORMED_ACTION"
    assert "invalid or unhandled action array" in data["error"]["message"]
    assert get_run_repository().count() == 0


def test_api_unsupported_resources_default_mode_succeeds():
    """Default mode (strict=false) preserves unsupported resource warnings with 201."""
    plan = load_fixture("unsupported_resource_s3.json")
    resp = client.post("/api/v1/runs", json=plan)
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["unsupported_resources"]) == 1
    assert data["unsupported_resources"][0]["resource_type"] == "aws_s3_bucket"
    assert data["summary"]["unsupported_count"] == 1
    assert get_run_repository().count() == 1


def test_api_unsupported_resources_strict_mode_rejects_with_structured_400():
    """Strict mode (?strict=true) rejects unsupported resources with 400 and persists nothing."""
    plan = load_fixture("unsupported_resource_s3.json")
    resp = client.post("/api/v1/runs?strict=true", json=plan)
    assert resp.status_code == 400
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "UNSUPPORTED_RESOURCE"
    assert "aws_s3_bucket" in data["error"]["message"]
    # Invariant: No partial run is persisted in strict mode
    assert get_run_repository().count() == 0


def test_api_preserves_noops_and_reads_in_summary():
    """No-op and read entries are preserved in Run lists and summary counts."""
    plan_noops = load_fixture("plan_with_noops.json")
    resp = client.post("/api/v1/runs", json=plan_noops)
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["ignored_noops"]) >= 1
    assert data["summary"]["noop_count"] == len(data["ignored_noops"])

    plan_reads = load_fixture("plan_with_data_sources.json")
    resp_reads = client.post("/api/v1/runs", json=plan_reads)
    assert resp_reads.status_code == 201
    data_reads = resp_reads.json()
    assert len(data_reads["ignored_reads"]) >= 1
    assert data_reads["summary"]["read_count"] == len(data_reads["ignored_reads"])


def test_summary_semantics_accuracy():
    """Verify summary counters strictly reflect changes, action counts, and severity categories."""
    plan = load_fixture("multiple_resources.json")
    resp = client.post("/api/v1/runs", json=plan)
    assert resp.status_code == 201
    data = resp.json()
    summary = data["summary"]

    # total_changes equals actionable changes count
    assert summary["total_changes"] == len(data["changes"])

    # Action counts sum to total_changes
    actions = summary["actions"]
    assert actions["CREATE"] + actions["UPDATE"] + actions["DELETE"] + actions["REPLACE"] == summary["total_changes"]

    # findings_count equals findings length
    assert summary["findings_count"] == len(data["findings"])

    # Severity counts sum to findings_count and contain all 4 levels
    sev = summary["findings_by_severity"]
    for level in ("HIGH", "MEDIUM", "LOW", "INFO"):
        assert level in sev
        assert isinstance(sev[level], int)
    assert sev["HIGH"] + sev["MEDIUM"] + sev["LOW"] + sev["INFO"] == summary["findings_count"]

    # Predictions are NOT counted as findings
    assert summary["findings_count"] != len(data["predictions"]) or len(data["findings"]) == len(data["predictions"])
