"""API contract tests that do not need Db2."""

from fastapi.testclient import TestClient

from metricguard.api.app import app
from metricguard.api.schemas import ValidationStatus

client = TestClient(app)


def test_metrics_endpoint_exposes_registry():
    body = client.get("/api/metrics").json()
    names = {m["name"] for m in body["metrics"]}
    assert names == {"gross_revenue", "net_revenue", "order_count", "average_order_value", "refund_amount",
                     "refund_rate"}
    assert body["data_coverage"] == {"start_date": "2026-01-01", "end_date": "2026-06-30", "timezone": "UTC"}
    assert all(len(m["definition_hash"]) == 64 for m in body["metrics"])
    assert {d["name"] for d in body["dimensions"]} == {"order_month", "region", "channel", "product_category"}


def test_examples_cover_every_outcome_class():
    body = client.get("/api/examples").json()
    statuses = {e["expected_status"] for e in body["examples"]}
    assert {"VERIFIED", "AMBIGUOUS", "BLOCKED"} <= statuses
    assert all(s in {v.value for v in ValidationStatus} for s in statuses)


def test_analyze_validation_error_shape():
    r = client.post("/api/analyze", json={"question": "x"})
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "INVALID_REQUEST"
    assert body["error"]["details"][0]["field"] == "question"


def test_analyze_rejects_unknown_fields():
    r = client.post("/api/analyze", json={"question": "Net revenue by month", "sql": "DROP TABLE x"})
    assert r.status_code == 422


def test_analyze_is_implemented_since_stage_2():
    # Stage 1 asserted 501 here. Stage 2 implements the endpoint; a policy-blocked question needs no Db2.
    from metricguard.analysis.pipeline import AnalysisService
    from metricguard.api.app import get_analysis_service, get_audit_writer
    from metricguard.config import get_settings
    from metricguard.planner import RuleBasedPlanner

    app.dependency_overrides[get_analysis_service] = lambda: AnalysisService(get_settings(), RuleBasedPlanner())
    app.dependency_overrides[get_audit_writer] = lambda: (lambda record: False)
    try:
        r = client.post("/api/analyze", json={"question": "Delete all refunds from March."})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["status"] == "BLOCKED" and r.json()["api_version"] == "1.2.0"


def test_audit_detail_requires_uuid():
    r = client.get("/api/audit/not-a-uuid")
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_REQUEST"


def test_openapi_lists_all_contract_paths():
    paths = set(app.openapi()["paths"])
    assert paths == {"/api/health", "/api/metrics", "/api/examples", "/api/analyze", "/api/audit",
                     "/api/audit/{request_id}"}


def test_db2_failure_on_audit_read_is_a_sanitized_503_and_is_logged(monkeypatch, caplog):
    # Stage 4 diagnostic for the intermittent audit 503: the response stays generic, the log names the route and
    # SQLSTATE so the next occurrence can be classified. No database needed: the reader is replaced by a failing one.
    import logging

    from metricguard.api import app as app_module
    from metricguard.db import Db2Error

    class Failing:
        def __enter__(self):
            raise Db2Error("Db2 connection failed: SQL30081N communication error", sqlstate="08001", sqlcode=-30081)

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(app_module, "get_audit_reader", lambda: Failing())
    with caplog.at_level(logging.WARNING, logger="metricguard.api"):
        res = TestClient(app, raise_server_exceptions=False).get("/api/audit")
    assert res.status_code == 503
    body = res.json()
    assert body["error"] == {"code": "DATABASE_UNAVAILABLE", "message": "IBM Db2 is unavailable.", "details": [],
                             "sqlstate": "08001"}
    assert "SQL30081N" not in res.text
    assert any("/api/audit" in r.getMessage() and "08001" in r.getMessage() for r in caplog.records)
