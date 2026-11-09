import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import agents


def plan(q, role):
    return agents.write_sql({"question": q, "role": role, "session": "t", "trace": []})


def test_destructive_request_emits_unsafe_sql_for_guard_demo():
    assert plan("delete all customers", "analyst")["sql"].startswith("DELETE")


def test_analyst_top_customers_has_no_pii():
    sql = plan("top 10 customers by balance", "analyst")["sql"]
    assert "FULL_NAME" not in sql and "EMAIL" not in sql


def test_admin_top_customers_includes_names():
    assert "FULL_NAME" in plan("top 10 customers by balance", "admin")["sql"]


def test_unknown_topic_is_fatal_with_clear_message():
    out = plan("what is the weather", "analyst")
    assert out["fatal"] and "Demo mode understands" in out["error"]


def test_hash_chain_is_deterministic_and_sensitive():
    a = agents.chain_hash("0" * 64, "t", "analyst", "q", "sql", "OK")
    assert a == agents.chain_hash("0" * 64, "t", "analyst", "q", "sql", "OK")
    assert a != agents.chain_hash("0" * 64, "t", "analyst", "q2", "sql", "OK")


def test_routing():
    assert agents.after_write({"fatal": True}) == "persist"
    assert agents.after_guard({"error": "x", "attempts": 1}) == "write"
    assert agents.after_guard({"error": "x", "attempts": 3}) == "persist"
    assert agents.after_guard({"error": "Write/DDL", "attempts": 1, "fatal": True}) == "persist"


def test_demo_followup_applies_city_to_previous_topic():
    sql, _ = agents.plan_demo("Filter them by Jaipur", "analyst", [["Top 10 customers by balance", "SELECT 1"]])
    assert "C.CITY = 'Jaipur'" in sql and "FETCH FIRST 10" in sql


def test_demo_n_slot_and_pii_by_role():
    sql, _ = agents.plan_demo("Top 5 customers by balance", "analyst", [])
    assert "FETCH FIRST 5 ROWS ONLY" in sql and "FULL_NAME" not in sql


def test_demo_rejects_unsupported_followup_filter():
    sql, why = agents.plan_demo("only in Jaipur", "analyst", [["Fraud rate by channel", "SELECT 1"]])
    assert sql is None and "cannot apply" in why


def test_prompt_formats():
    msg = agents.PROMPT.format(ddl=agents.SCHEMA_DDL, ctx="c", gl="g", role="analyst", hist="", err="", q="top 3 customers")
    assert "OUT_OF_SCOPE" in msg and msg.endswith("SQL:")


def test_live_mode_lets_llm_classify_scope_but_demo_refuses():
    saved = agents.LLM
    try:
        agents.LLM = None
        assert agents.intent({"question": "Show me revenue by month", "history": [], "trace": []}).get("oos")
        agents.LLM = object()
        assert not agents.intent({"question": "Show me revenue by month", "history": [], "trace": []}).get("oos")
    finally:
        agents.LLM = saved
