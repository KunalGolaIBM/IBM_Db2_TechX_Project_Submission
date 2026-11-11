from redb.config import Settings
from redb.llm import Brain, heuristic_rewrite
from redb.sqlguard import is_safe
from redb.workload import WORKLOAD


def test_offline_brain():
    b = Brain(Settings(google_api_key=""))
    assert not b.online and "offline" in b.mode
    d = b.diagnose({"sql": WORKLOAD["W3"], "flags": [{"kind": "TABLE_SCAN", "detail": "full scan of RETAIL.ORDERS"}]})
    assert d["severity"] == "high" and d["source"] == "heuristic"
    assert len(b.embed("x")) == 768


def test_year_month_rewrite():
    r = heuristic_rewrite(WORKLOAD["W3"])
    assert r.should_rewrite and is_safe(r.sql)
    assert "ORDER_DATE >= '2024-03-01' AND ORDER_DATE < '2024-04-01'" in r.sql
    dec = heuristic_rewrite("SELECT 1 FROM T WHERE YEAR(D) = 2024 AND MONTH(D) = 12")
    assert "D < '2025-01-01'" in dec.sql


def test_not_in_rewrite_requires_not_null():
    assert not heuristic_rewrite(WORKLOAD["W5"], set()).should_rewrite
    r = heuristic_rewrite(WORKLOAD["W5"], {"CUSTOMER_ID"})
    assert r.should_rewrite and is_safe(r.sql)
    assert "NOT EXISTS (SELECT 1 FROM RETAIL.ORDERS O WHERE O.CUSTOMER_ID = C.CUSTOMER_ID AND" in r.sql


def test_union_to_in_rewrite():
    r = heuristic_rewrite(WORKLOAD["W7"])
    assert r.should_rewrite and is_safe(r.sql)
    assert r.sql == ("SELECT DISTINCT CUSTOMER_ID, ORDER_DATE, TOTAL_AMOUNT FROM RETAIL.ORDERS "
                     "WHERE STATUS IN ('PENDING', 'CANCELLED') AND TOTAL_AMOUNT > 900")
    assert not heuristic_rewrite("SELECT A FROM T WHERE X = 1 UNION SELECT B FROM T WHERE X = 2").should_rewrite
