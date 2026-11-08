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
