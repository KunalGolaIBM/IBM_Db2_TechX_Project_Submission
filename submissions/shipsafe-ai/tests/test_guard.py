"""The IDE guard: verdicts, merging across tools, languages and limits (real Bandit, no model needed)."""

import pytest

from shipsafe.guard import check_code, language_for
from shipsafe.guard.checker import MAX_CODE_BYTES, GuardIssue, _merge

VULNERABLE = '''import ibm_db
API_SECRET = "sk_live_9f8e7d6c5b4a3210"

def get_order(conn, order_id):
    """Never use eval() here."""
    sql = f"SELECT * FROM ORDERS WHERE ID = '{order_id}'"
    return ibm_db.exec_immediate(conn, sql)
'''


def test_blocks_vulnerable_code_and_merges_tools():
    r = check_code(VULNERABLE, "orders/repo.py")
    assert r.verdict == "block"
    assert r.language == "python"
    assert set(r.checks) == {"secrets", "syntax", "code-rules", "bandit"}
    by_rule = {i.rule_id: i for i in r.issues}
    sqli = by_rule["SQLI-DYNAMIC"]
    assert sqli.line == 6 and sqli.severity == "critical"
    assert sorted(sqli.sources) == ["bandit", "shipsafe_code_rules"]  # Bandit B608 merged into one issue
    assert "SEC-005" in by_rule
    assert not any(i.rule_id == "CODE-EVAL" for i in r.issues)  # docstring mention ignored
    assert r.issues[0].severity == "critical"  # sorted by severity
    d = r.to_dict()
    assert d["max_severity"] == "critical" and "Do not write" in d["summary"]


def test_clean_code():
    r = check_code("def add(a: int, b: int) -> int:\n    return a + b\n", "math_utils.py")
    assert r.verdict == "clean" and r.issues == [] and r.max_severity is None
    assert "No issues" in r.summary()


def test_low_only_code_warns():
    r = check_code("import subprocess\n", "x.py")
    assert r.verdict == "warn" and r.issues[0].rule_id.startswith("B404")
    assert "Safe to write" in r.summary()


def test_syntax_error_blocks():
    r = check_code("def broken(:\n    pass\n", "b.py")
    assert r.verdict == "block" and r.issues[0].rule_id == "PY-SYNTAX"


def test_javascript_and_other_languages():
    js = check_code("document.body.innerHTML = userHtml;\n", "ui/app.ts")
    assert js.language == "typescript" and js.verdict == "block" and "bandit" not in js.checks
    sql = check_code("-- password='hunter2hunter2'\nSELECT 1;\n", "q.sql")
    assert sql.language == "sql" and sql.checks == ["secrets"]
    assert check_code("AKIAABCDEFGHIJKLMNOP", "notes.txt").issues[0].rule_id == "SEC-001"


def test_bandit_can_be_turned_off():
    assert "bandit" not in check_code("x = 1\n", "a.py", use_bandit=False).checks


def test_size_limit():
    with pytest.raises(ValueError, match="larger than"):
        check_code("x" * (MAX_CODE_BYTES + 1), "big.py")


def test_language_for():
    assert language_for("a/b/c.PY") == "python"
    assert language_for("x.jsx") == "javascript"
    assert language_for("Makefile") == "text"


def test_merge_keeps_highest_severity_and_all_sources():
    low = GuardIssue("B602-X", "low", "security", "t", 3, "", "", "", ["bandit"])
    high = GuardIssue("CMD-SHELL", "high", "security", "t", 3, "", "", "", ["shipsafe_code_rules"])
    other = GuardIssue("CMD-SHELL", "medium", "security", "t", 3, "", "", "", ["x"])
    merged = _merge([low, high, other])
    assert len(merged) == 1
    assert merged[0].severity == "high" and merged[0].sources == ["bandit", "shipsafe_code_rules", "x"]
