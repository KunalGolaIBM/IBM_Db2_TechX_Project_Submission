"""Live IBM Db2 integration tests. Run with: MG_RUN_DB2_TESTS=1 make test-db2 (after make db-init)."""

import json
import os
import uuid

import pytest
from fastapi.testclient import TestClient

pytestmark = [
    pytest.mark.db2,
    pytest.mark.skipif(os.getenv("MG_RUN_DB2_TESTS") != "1", reason="set MG_RUN_DB2_TESTS=1 to run against Db2"),
]


@pytest.fixture(scope="module")
def db():
    from metricguard.db import Db2Client

    with Db2Client() as client:
        yield client


def test_health_endpoint_reports_live_db2():
    from metricguard.api.app import app

    r = TestClient(app).get("/api/health")
    body = r.json()
    assert r.status_code == 200, body
    assert body["status"] == "ok"
    assert body["database"]["status"] == "up" and body["database"]["tables_present"] == 6
    assert body["registry"]["db_hash_match"] is True


def test_golden_examples_match_oracle(db):
    from metricguard.config import get_settings
    from metricguard.core.examples import EXAMPLES
    from metricguard.seed import oracle
    from metricguard.seed.generator import generate
    from metricguard.verification import _apply_order_limit, run_plan

    ds = generate()
    for ex in EXAMPLES:
        if ex.reference_plan is None:
            continue
        p = ex.reference_plan
        rows, _ = run_plan(db, p, get_settings().max_result_rows)
        expected = _apply_order_limit(
            oracle.compute(ds, metrics=p.metric_names, dimensions=p.dimensions, start=p.date_range.start_date,
                           end=p.date_range.end_date, filters={f.field: f.values for f in p.filters}),
            p,
        )
        assert rows == expected, ex.id


def test_audit_roundtrip_via_api(db):
    from metricguard import API_CONTRACT_VERSION
    from metricguard.api import audit_repo
    from metricguard.api.app import app

    rid = str(uuid.uuid4())
    audit_repo.insert(db, {
        "request_id": rid, "question": "integration test", "status": "BLOCKED",
        "status_reason": "DIMENSION_NOT_ALLOWED", "metric_refs": "average_order_value@1.0.0",
        "planner": "pytest", "plan_json": None, "verification_json": json.dumps({
            "status": "BLOCKED", "summary": "blocked", "reasons": [], "checks": []}),
        "total_ms": 1, "planning_ms": 0, "validation_ms": 1, "api_version": API_CONTRACT_VERSION,
    })
    try:
        client = TestClient(app)
        detail = client.get(f"/api/audit/{rid}").json()
        assert detail["status"] == "BLOCKED" and detail["metric_refs"] == ["average_order_value@1.0.0"]
        listing = client.get("/api/audit", params={"status": "BLOCKED", "limit": 100}).json()
        assert rid in {i["request_id"] for i in listing["items"]}
        missing = client.get(f"/api/audit/{uuid.uuid4()}")
        assert missing.status_code == 404 and missing.json()["error"]["code"] == "AUDIT_NOT_FOUND"
    finally:
        db.execute("DELETE FROM METRICGUARD.QUERY_AUDIT_LOG WHERE REQUEST_ID = ?", (rid,))
