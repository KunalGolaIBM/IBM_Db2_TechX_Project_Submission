import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import nlu


def test_extract_slots():
    assert nlu.extract("Top 5 customers in Jaipur") == {"n": 5, "cities": ["Jaipur"], "regions": []}
    assert nlu.extract("first ten branches in the north region")["n"] == 10
    assert nlu.extract("top 5000 customers")["n"] is None


def test_adapt_changes_n_only_when_safe():
    sql = "SELECT X FROM T ORDER BY Y FETCH FIRST 10 ROWS ONLY"
    assert "FETCH FIRST 5 ROWS" in nlu.adapt(sql, "Top 10 customers", "Top 5 customers")
    assert nlu.adapt(sql, "Top customers", "Top 5 customers") is None


def test_adapt_swaps_single_city_literal_and_rejects_new_constraints():
    sql = "SELECT 1 FROM T WHERE C.CITY = 'Jaipur' FETCH FIRST 10 ROWS ONLY"
    assert "'Pune'" in nlu.adapt(sql, "top 10 customers in Jaipur", "top 10 customers in Pune")
    assert nlu.adapt(sql, "top 10 customers", "top 10 customers in Pune") is None


def test_domain_gate():
    assert not nlu.in_domain("What is the weather in Delhi?")
    assert nlu.in_domain("Fraud rate by channel")
    assert not nlu.in_domain("Filter them by Jaipur", has_history=False)
    assert nlu.in_domain("Filter them by Jaipur", has_history=True)
    assert nlu.is_followup("Filter them by Jaipur", True)
    assert not nlu.is_followup("Top customers in Jaipur", True)
    assert not nlu.in_domain("What is the weather in Delhi?", has_history=True)
    assert not nlu.in_domain("Tell me a joke about Mumbai", has_history=True)
    assert nlu.in_domain("What about Pune?", has_history=True)
    assert nlu.in_domain("in Jaipur", has_history=True)
    assert nlu.in_domain("only in Jaipur", has_history=True)
