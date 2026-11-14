"""Workload capture, the CI gate, the cost check, minimisation, the in-engine
model call and the MCP tools.

The first half needs no database. The second half is marked ``db2``; the tests
that need something optional (the Explain tables, a registered external model)
skip themselves when it is not installed, so the suite passes on a database
that has only been through ``python -m src.setup_db``.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from src import capture, costgate, mcp_server
from src.config import llm_config
from src.datasets import DatasetAgent
from src.engines import SqliteSource
from src.main import _gate, _write_json

pytestmark_db2 = pytest.mark.db2
TABLES = ("customers", "orders")


# --------------------------------------------------------------------------
# workload capture
# --------------------------------------------------------------------------
def _file(tmp_path, text):
    path = tmp_path / "workload.sql"
    path.write_text(text, encoding="utf-8")
    return path


def test_capture_keeps_only_read_only_statements_over_the_named_tables(tmp_path):
    taken = capture.from_file(_file(tmp_path, """
        -- what the application sends
        SELECT id FROM customers WHERE name = 'a';
        SELECT id FROM customers WHERE name = 'a';
        SELECT o.id FROM orders o JOIN customers c ON c.id = o.customer_id;
        DELETE FROM customers;
        SELECT * FROM invoices;
        SELECT table_name FROM information_schema.tables;
        SELECT id FROM customers WHERE id = $1;
        SELECT id FROM customers WHERE id = ?;
    """), "postgres", TABLES)
    assert taken.seen == 8
    assert [count for _, count in taken.kept] == [2, 1]
    assert taken.kept[0][0] == "SELECT id FROM customers WHERE name = 'a'"
    assert taken.not_read_only == 1
    assert taken.other_tables == 2
    assert taken.normalised == 2
    assert "2 distinct statement(s) kept of 8" in taken.summary()


def test_a_placeholder_inside_a_string_literal_is_not_a_placeholder(tmp_path):
    taken = capture.from_file(_file(tmp_path, "SELECT id FROM customers WHERE name = 'why?'"),
                              "mysql", TABLES)
    assert len(taken.kept) == 1 and taken.normalised == 0


def test_a_cte_name_is_not_a_table_and_a_qualified_name_is_out_of_scope():
    assert capture.tables_of(
        "WITH big AS (SELECT id FROM orders) SELECT id FROM big", "postgres") == {"orders"}
    assert capture.tables_of("SELECT 1 FROM sales.customers", "tsql") == {"<qualified>"}


def test_captured_statements_carry_their_rank_and_execution_count():
    taken = capture.Captured(dialect="mysql", origin="x", kept=[("SELECT 1 FROM customers", 412)])
    (statement,) = taken.statements("captured")
    assert statement.name == "captured.q001_x412" and statement.dialect == "mysql"


def test_an_engine_with_no_statement_record_says_so():
    with pytest.raises(ValueError, match="sql file"):
        capture.from_engine(SqliteSource(), "sqlite", TABLES)


# --------------------------------------------------------------------------
# the CI gate and the JSON report
# --------------------------------------------------------------------------
def _report(*statuses):
    return SimpleNamespace(results=[
        SimpleNamespace(
            status=s, case_name=f"c{n}", statement=SimpleNamespace(dialect="mysql", sql="SELECT 1"),
            db2_sql="SELECT 1", first_sqlcode=None, repair=None, repaired=False,
            semantic_repair=None, semantic=None, datasets_used=12, minimal=None,
            cost_before=None, cost_after=None,
            compile_cert="aa", semantic_cert=None)
        for n, s in enumerate(statuses)
    ])


@pytest.mark.parametrize("statuses, fail_on, code", [
    (("PROVEN_EQUIVALENT", "PROVEN_DIFFERENT"), "none", 0),
    (("PROVEN_EQUIVALENT", "VACUOUS"), "different", 0),
    (("PROVEN_EQUIVALENT", "PROVEN_DIFFERENT"), "different", 2),
    (("PROVEN_EQUIVALENT", "COMPILE_FAIL"), "different", 2),
    (("PROVEN_EQUIVALENT", "VACUOUS"), "unproven", 2),
    (("PROVEN_EQUIVALENT", "PROVEN_EQUIVALENT"), "unproven", 0),
])
def test_the_gate_holds_a_branch_on_exactly_what_was_asked(statuses, fail_on, code, capsys):
    assert _gate(_report(*statuses), fail_on) == code


def test_the_json_report_counts_by_status(tmp_path):
    out = tmp_path / "report.json"
    _write_json(_report("PROVEN_EQUIVALENT", "PROVEN_DIFFERENT", "PROVEN_EQUIVALENT"), str(out))
    body = json.loads(out.read_text(encoding="utf-8"))
    assert body["statements"] == 3
    assert body["by_status"] == {"PROVEN_EQUIVALENT": 2, "PROVEN_DIFFERENT": 1}
    assert body["results"][0]["compile_certificate"] == "aa"


# --------------------------------------------------------------------------
# cost ratio, transport config, MCP guards
# --------------------------------------------------------------------------
def test_a_cost_ratio_needs_both_estimates():
    assert costgate.ratio(10.0, 40.0) == 4.0
    assert costgate.ratio(None, 40.0) is None and costgate.ratio(10.0, None) is None
    assert costgate.ratio(0.0, 5.0) is None


def test_the_in_engine_transport_needs_no_key_in_the_application(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "tiered")
    monkeypatch.setenv("LLM_TRANSPORT", "db2")
    monkeypatch.setenv("LLM_API_KEY", "")
    cfg = llm_config()
    assert cfg.in_db2 and cfg.reachable
    monkeypatch.setenv("LLM_TRANSPORT", "http")
    assert not llm_config().in_db2


def test_the_mcp_server_offers_four_questions_and_no_actions():
    import asyncio

    tools = asyncio.run(mcp_server.build_server().list_tools())
    assert {t.name for t in tools} == {
        "check_compiles", "prove_statement", "estimate_cost", "ledger_summary"}


def test_an_agent_cannot_reach_a_connection_with_anything_but_a_query():
    # Refused before any connection is opened: these run with no database.
    assert "refused_before_db2" in mcp_server.check_compiles("DROP TABLE customers")
    assert "refused_before_db2" in mcp_server.estimate_cost("DELETE FROM customers")
    assert mcp_server.prove_statement("UPDATE customers SET name = 'x'", "mysql")["status"] == "REFUSED"
    assert mcp_server.prove_statement("SELECT 1", "oracle")["status"] == "REFUSED"


# --------------------------------------------------------------------------
# against Db2
# --------------------------------------------------------------------------
@pytestmark_db2
def test_db2_estimates_a_statement_without_running_it(owner_conn):
    from src import db
    from src.counterexample import FIXTURE_SCHEMA, ensure_fixture_schema

    ensure_fixture_schema(owner_conn)
    db.execute(owner_conn, f"SET CURRENT SCHEMA {FIXTURE_SCHEMA}")
    cost = costgate.estimate(owner_conn, "SELECT id FROM customers WHERE id = 1")
    if cost is None:
        pytest.skip("Explain tables not installed (scripts/create_explain_tables.sh)")
    assert cost > 0
    wrapped = costgate.estimate(
        owner_conn, "SELECT c.id FROM customers c, customers d WHERE UPPER(c.name) = UPPER(d.name)")
    assert wrapped > cost
    # Not a query Db2 can compile: no estimate, and no exception.
    assert costgate.estimate(owner_conn, "SELECT nothing FROM nowhere_at_all") is None


@pytestmark_db2
def test_a_counterexample_is_shrunk_and_still_disagrees(app_conn, owner_conn):
    from src import samples
    from src.pipeline import Pipeline

    agent = DatasetAgent()
    pipeline = Pipeline(app_conn=app_conn, owner_conn=owner_conn, sources={"sqlite": SqliteSource()},
                        dataset_agent=agent, learn=False, semantic_repair=False)
    try:
        samples.discover(pipeline.sources, agent)
        (statement,) = [s for s in samples.statements(("sqlite",)) if s.name == "hr.name_search"]
        result = pipeline.run_statement(statement)
    finally:
        pipeline.close()
    assert result.status == "PROVEN_DIFFERENT"
    minimal = result.minimal
    assert minimal is not None
    assert 0 < minimal.rows_after <= minimal.rows_before
    assert sorted(minimal.source_rows) != sorted(minimal.db2_rows)
    assert minimal.as_detail()["rows_after"] == minimal.rows_after


def _has_ask_model(owner_conn) -> bool:
    from src import db

    row = db.fetch_one(
        owner_conn,
        "SELECT COUNT(*) FROM SYSCAT.PROCEDURES WHERE PROCSCHEMA = 'PORTPROOF' "
        "AND PROCNAME = 'ASK_MODEL'")
    return bool(row and int(row[0]))


@pytestmark_db2
def test_the_engine_refuses_a_model_call_once_the_budget_is_spent(app_conn, owner_conn):
    """Budget 0: Db2 signals before TEXT_GENERATION runs, so this costs nothing."""
    from src import db

    if not _has_ask_model(owner_conn):
        pytest.skip("no in-engine model registered (python -m src.setup_model)")
    before = db.fetch_one(owner_conn, "SELECT COUNT(*) FROM PORTPROOF.LLM_CALL")[0]
    with pytest.raises(db.Db2Error) as refused:
        db.call_proc(app_conn, "PORTPROOF.ASK_MODEL",
                     ("DATASET", "t/budget", "say hi", None, 0, None))
    assert refused.value.sqlstate == "75002" or "budget" in str(refused.value)
    assert db.fetch_one(owner_conn, "SELECT COUNT(*) FROM PORTPROOF.LLM_CALL")[0] == before


@pytestmark_db2
def test_the_runtime_user_cannot_call_the_model_around_the_ledger(app_conn, owner_conn):
    from src import db

    if not _has_ask_model(owner_conn):
        pytest.skip("no in-engine model registered (python -m src.setup_model)")
    with pytest.raises(db.Db2Error) as refused:
        db.fetch_one(app_conn, "VALUES TEXT_GENERATION('hi' USING PORTPROOF.PP_MODEL)")
    assert refused.value.sqlcode == -551
