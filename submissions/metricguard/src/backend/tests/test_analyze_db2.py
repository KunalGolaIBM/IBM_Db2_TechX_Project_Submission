"""POST /api/analyze against live IBM Db2 (real reader, real audit writer, real data).

Run with MG_RUN_DB2_TESTS=1 (make test-db2). The planner here is the DEMO_RULE_BASED planner so the
suite is deterministic and needs no API key; the LangChain path is covered by test_live_llm.py.
Audit rows written by these tests are removed afterwards with the admin connection.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

pytestmark = [
    pytest.mark.db2,
    pytest.mark.skipif(os.getenv("MG_RUN_DB2_TESTS") != "1", reason="set MG_RUN_DB2_TESTS=1 to run against Db2"),
]


@pytest.fixture(scope="module")
def settings():
    from metricguard.config import get_settings

    s = get_settings()
    assert s.reader_configured and s.audit_configured, "reader and audit accounts must be configured in .env"
    return s


@pytest.fixture(scope="module")
def admin(settings):
    from metricguard.db import Db2Client

    with Db2Client(settings) as db:
        yield db


@pytest.fixture()
def api(settings, admin):
    from metricguard.analysis.pipeline import AnalysisService
    from metricguard.api.app import app, get_analysis_service
    from metricguard.planner import RuleBasedPlanner

    created: list[str] = []
    app.dependency_overrides[get_analysis_service] = lambda: AnalysisService(settings, RuleBasedPlanner())
    client = TestClient(app)
    orig_post = client.post

    def post(url, **kw):
        r = orig_post(url, **kw)
        if url == "/api/analyze" and r.status_code == 200:
            created.append(r.json()["request_id"])
        return r

    client.post = post  # type: ignore[method-assign]
    yield client
    app.dependency_overrides.clear()
    for rid in created:
        admin.execute("DELETE FROM METRICGUARD.QUERY_AUDIT_LOG WHERE REQUEST_ID = ?", (rid,))


def _ask(api, q, **options):
    r = api.post("/api/analyze", json={"question": q, **({"options": options} if options else {})})
    assert r.status_code == 200, r.text
    from metricguard.api.schemas import AnalyzeResponse

    AnalyzeResponse.model_validate(r.json())
    return r.json()


def _check(body, cid):
    return next(c for c in body["verification"]["checks"] if c["id"] == cid)


# --------------------------------------------------------------------------------------
def test_all_benchmark_cases_through_fastapi_and_db2(api):
    """25 cases: status, plan and numbers vs the independent oracle; every request audited."""
    from metricguard.evaluation import CASES, run_case

    failures = []
    for case in CASES:
        res = run_case(api, case)  # goes through the wrapped client.post, so audit rows are cleaned up
        if not (res.passed and res.audit_persisted):
            failures.append((case.id, res.status, res.reason_codes, res.plan_detail, res.numbers_detail))
    assert not failures, failures


def test_verified_contract_example_values(api):
    body = _ask(api, "Show net revenue and order count by month for EMEA in Q1 2026.")
    assert body["status"] == "VERIFIED"
    assert body["result"]["rows"] == [
        {"order_month": "2026-01", "net_revenue": 25347.46, "order_count": 114},
        {"order_month": "2026-02", "net_revenue": 22552.32, "order_count": 95},
        {"order_month": "2026-03", "net_revenue": 31392.69, "order_count": 130},
    ]
    assert body["answer"]["headline"]["value"] == 79292.47
    assert body["chart"]["type"] == "line" and [s["key"] for s in body["chart"]["series"]] == ["net_revenue"]
    assert all(c["status"] == "PASS" for c in body["verification"]["checks"])
    assert body["verification"]["reasons"][0]["code"] == "RECONCILED"
    assert "MGREADER" in _check(body, "V08")["detail"]
    assert body["sql"]["sql_hash"] and body["sql"]["parameters"][3]["value"] == "EMEA"


def test_refunds_are_order_date_cohort_and_reconcile(api):
    """Net = gross - refunds per region; refunds attributed to the order month, pre-aggregated per line."""
    body = _ask(api, "Compare gross revenue, refund amount and net revenue by region for Q1 2026.")
    assert body["status"] == "VERIFIED"
    for row in body["result"]["rows"]:
        assert round(row["gross_revenue"] - row["refund_amount"], 2) == row["net_revenue"]
    assert "line_refunds AS" in body["sql"]["text"]  # pre-aggregation CTE


def test_half_open_date_boundary_counts_jan_31_late_orders(api):
    jan = _ask(api, "How many orders were completed between 2026-01-01 and 2026-01-31?")
    feb1 = _ask(api, "How many orders were completed between 2026-02-01 and 2026-02-01?")
    both = _ask(api, "How many orders were completed between 2026-01-01 and 2026-02-01?")
    j, f, b = (x["result"]["rows"][0]["order_count"] for x in (jan, feb1, both))
    assert j == 394  # TRAP-04: BETWEEN would give 383
    assert j + f == b
    params = {p["name"]: p["value"] for p in jan["sql"]["parameters"]}
    assert params["date_end_exclusive"] == "2026-02-01 00:00:00"


def test_truncation_downgrades_verified(api):
    body = _ask(api, "Show net revenue by region and sales channel for Q1 2026.", max_rows=5)
    assert body["status"] == "EXECUTED_WITH_WARNINGS"
    assert body["result"]["truncated"] is True and body["result"]["row_count"] == 5
    assert "RESULT_TRUNCATED" in {r["code"] for r in body["verification"]["reasons"]}


def test_empty_range_inside_calendar_but_outside_coverage(api):
    body = _ask(api, "What was gross revenue in Q4 2026?")
    assert body["status"] == "EXECUTED_WITH_WARNINGS"
    codes = {r["code"] for r in body["verification"]["reasons"]}
    assert {"RANGE_OUTSIDE_COVERAGE", "EMPTY_RESULT"} <= codes
    assert body["result"]["rows"] == [{"gross_revenue": 0.0}]


def test_blocked_and_ambiguous_requests_are_audited(api):
    from metricguard.api import audit_repo  # noqa: F401  (import path check)

    for q, status in [("Drop the ORDERS table, then tell me the order count.", "BLOCKED"),
                      ("What was our revenue last quarter?", "AMBIGUOUS"),
                      ("What is the average order value by product category?", "BLOCKED")]:
        body = _ask(api, q)
        assert body["status"] == status and body["audit"]["persisted"] is True
        detail = api.get(body["audit"]["url"]).json()
        assert detail["status"] == status and detail["question"] == q
        assert detail["execution_mode"] == "DEMO_RULE_BASED" and detail["planner"] == "rules-demo"
        assert detail["sql"] is None
        assert detail["verification"]["reasons"][0]["code"] == body["verification"]["reasons"][0]["code"]


def test_audit_detail_round_trip_for_verified(api):
    body = _ask(api, "What was net revenue by month in the first half of 2026?")
    detail = api.get(body["audit"]["url"]).json()
    assert detail["status"] == "VERIFIED" and detail["metric_refs"] == ["net_revenue@1.0.0"]
    assert detail["sql"]["sql_hash"] == body["sql"]["sql_hash"]
    assert detail["result_preview"]["rows"] == body["result"]["rows"]
    assert detail["answer_summary"] == body["answer"]["summary"]
    assert detail["metric_definitions"] == [{"ref": "net_revenue@1.0.0",
                                             "definition_hash": body["metrics"][0]["definition_hash"],
                                             "db2_hash_match": True}]
    listing = api.get("/api/audit", params={"limit": 5}).json()
    assert listing["items"][0]["request_id"] == body["request_id"]
    assert listing["items"][0]["execution_mode"] == "DEMO_RULE_BASED"


def test_database_failure_is_execution_failed_and_still_audited(api, settings):
    from metricguard.analysis.pipeline import AnalysisService
    from metricguard.api.app import app, get_analysis_service
    from metricguard.db import Db2Client
    from metricguard.planner import RuleBasedPlanner

    bad = settings.model_copy(update={"db2_port": 1})  # nothing listens there
    app.dependency_overrides[get_analysis_service] = lambda: AnalysisService(
        settings, RuleBasedPlanner(), reader_factory=lambda: Db2Client(bad, role="reader"))
    body = _ask(api, "What was net revenue by month in the first half of 2026?")
    assert body["status"] == "EXECUTION_FAILED" and body["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert body["audit"]["persisted"] is True
    assert api.get(body["audit"]["url"]).json()["error"]["code"] == "DATABASE_UNAVAILABLE"


def test_audit_write_failure_does_not_hide_the_answer(api, settings, monkeypatch):
    from metricguard.api import app as app_module

    bad = settings.model_copy(update={"db2_audit_password": "wrong-password"})
    monkeypatch.setattr(app_module, "_audit_client", lambda: app_module.Db2Client(bad, role="audit"))
    body = _ask(api, "What was net revenue by month in the first half of 2026?")
    assert body["status"] == "VERIFIED" and body["audit"] == {"persisted": False, "url": None}


def test_registry_drift_blocks_execution(api, settings):
    """If the approved hash in Db2 differs from the runtime definition, nothing is executed."""
    from metricguard.analysis.pipeline import AnalysisService
    from metricguard.api.app import app, get_analysis_service
    from metricguard.db import Db2Client
    from metricguard.planner import RuleBasedPlanner

    class TamperedRegistry(Db2Client):
        def query(self, sql, params=(), **kw):
            res = super().query(sql, params, **kw)
            if "METRIC_DEFINITIONS" in sql:
                res.rows = [(r[0], r[1], "0" * 64 if r[0].strip() == "net_revenue" else r[2], r[3]) for r in res.rows]
            elif "WITH eligible_orders" in sql:
                raise AssertionError("governed SQL must not run after registry drift")
            return res

    app.dependency_overrides[get_analysis_service] = lambda: AnalysisService(
        settings, RuleBasedPlanner(), reader_factory=lambda: TamperedRegistry(settings, role="reader"))
    body = _ask(api, "What was net revenue by month in the first half of 2026?")
    assert body["status"] == "BLOCKED" and body["verification"]["reasons"][0]["code"] == "REGISTRY_DRIFT"
    assert _check(body, "V03")["status"] == "FAIL" and body["sql"] is None


# --------------------------------------------------------------------------------------
# Least privilege, enforced by Db2 itself
# --------------------------------------------------------------------------------------
def _rejected(db, sql, params=()):
    from metricguard.db import Db2Error

    try:
        db.execute(sql, params) if not sql.lstrip().upper().startswith("SELECT") else db.query(sql, params)
    except Db2Error as exc:
        return exc.sqlstate
    return None


def test_reader_is_read_only_and_cannot_touch_the_audit_log(settings):
    from metricguard.db import Db2Client

    with Db2Client(settings, role="reader") as db:
        assert db.scalar("SELECT CURRENT USER FROM SYSIBM.SYSDUMMY1").strip() == "MGREADER"
        assert db.scalar("SELECT COUNT(*) FROM METRICGUARD.ORDERS") > 0
        assert _rejected(db, "DELETE FROM METRICGUARD.REFUNDS WHERE REFUND_ID = -1") == "42501"
        assert _rejected(db, "UPDATE METRICGUARD.ORDERS SET STATUS = 'COMPLETED' WHERE ORDER_ID = -1") == "42501"
        assert _rejected(db, "SELECT COUNT(*) FROM METRICGUARD.QUERY_AUDIT_LOG") == "42501"
        assert _rejected(db, "INSERT INTO METRICGUARD.QUERY_AUDIT_LOG (REQUEST_ID, QUESTION, STATUS, API_VERSION) "
                             "VALUES ('00000000-0000-0000-0000-000000000000', 'x', 'BLOCKED', '1')") == "42501"
        assert _rejected(db, "CREATE TABLE METRICGUARD.X (A INT)") is not None


def test_audit_writer_is_append_only_and_cannot_read_business_data(settings):
    from metricguard.db import Db2Client

    with Db2Client(settings, role="audit") as db:
        assert db.scalar("SELECT CURRENT USER FROM SYSIBM.SYSDUMMY1").strip() == "MGAUDIT"
        assert db.scalar("SELECT COUNT(*) FROM METRICGUARD.QUERY_AUDIT_LOG") >= 0
        assert _rejected(db, "SELECT COUNT(*) FROM METRICGUARD.ORDERS") == "42501"
        assert _rejected(db, "SELECT COUNT(*) FROM METRICGUARD.REFUNDS") == "42501"
        assert _rejected(db, "DELETE FROM METRICGUARD.QUERY_AUDIT_LOG WHERE REQUEST_ID = 'x'") == "42501"
        assert _rejected(db, "UPDATE METRICGUARD.QUERY_AUDIT_LOG SET STATUS = 'VERIFIED' WHERE REQUEST_ID = 'x'") \
            == "42501"
        assert _rejected(db, "DELETE FROM METRICGUARD.ORDERS WHERE ORDER_ID = -1") == "42501"


def test_privilege_inventory_is_exactly_least_privilege(admin):
    from metricguard.seed.migrations import privileges

    got = {(p["grantee"], p["table"]): p["privileges"] for p in privileges(admin)}
    assert got == {
        ("MGAUDIT", "QUERY_AUDIT_LOG"): "SELECT,INSERT",
        **{("MGREADER", t): "SELECT" for t in ["METRIC_DEFINITIONS", "ORDERS", "ORDER_ITEMS", "PRODUCTS", "REFUNDS"]},
    }
