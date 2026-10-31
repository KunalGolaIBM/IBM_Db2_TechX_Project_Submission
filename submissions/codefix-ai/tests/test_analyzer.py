"""
Unit tests for CodeFix AI Python Static Analyzer (analyzer.py)
Tests deterministic syntax checking, AST node inspection, and anti-pattern warnings.
"""

import pytest
from analyzer import analyze_code, analyze_python_code


def test_clean_python_code():
    """Valid Python code should pass with no syntax errors and no warnings."""
    code = """
def add_numbers(a: int, b: int) -> int:
    return a + b

result = add_numbers(10, 20)
"""
    result = analyze_code(code, "python")
    assert result["is_valid_syntax"] is True
    assert result["has_warnings"] is False
    assert result["syntax_error"] is None
    assert len(result["warnings"]) == 0
    assert "passed cleanly" in result["summary"]


def test_syntax_error_missing_colon():
    """Syntax error such as missing colon in 'if' or 'for' must be detected with line number."""
    bad_code = """
def check_value(x):
    if x > 10
        return True
    return False
"""
    result = analyze_code(bad_code, "python")
    assert result["is_valid_syntax"] is False
    assert result["syntax_error"] is not None
    assert result["syntax_error"]["line"] == 3
    assert "expected ':'" in result["syntax_error"]["message"]
    assert any("expected ':'" in d for d in result["diagnostics"])


def test_syntax_error_unclosed_parenthesis():
    """Unclosed parenthesis or brackets should be reported as syntax error."""
    bad_code = "print(10 + 20"
    result = analyze_code(bad_code, "python")
    assert result["is_valid_syntax"] is False
    assert result["syntax_error"] is not None
    assert result["syntax_error"]["line"] == 1


def test_mutable_default_argument():
    """Mutable default argument (list/dict/set) should trigger an anti-pattern warning."""
    code = """
def append_item(item, items=[]):
    items.append(item)
    return items
"""
    result = analyze_code(code, "python")
    assert result["is_valid_syntax"] is True
    assert result["has_warnings"] is True
    warning_msgs = [w["message"] for w in result["warnings"]]
    assert any("Mutable default argument" in m for m in warning_msgs)
    assert any("items" in m for m in warning_msgs)


def test_bare_except_clause():
    """Bare 'except:' catching SystemExit/KeyboardInterrupt should trigger a warning."""
    code = """
try:
    val = int("abc")
except:
    val = 0
"""
    result = analyze_code(code, "python")
    assert result["is_valid_syntax"] is True
    assert result["has_warnings"] is True
    warning_msgs = [w["message"] for w in result["warnings"]]
    assert any("Bare 'except:'" in m for m in warning_msgs)


def test_compare_to_none_warning():
    """Comparison using '== None' should warn and recommend 'is None'."""
    code = """
def is_empty(val):
    if val == None:
        return True
    return False
"""
    result = analyze_code(code, "python")
    assert result["is_valid_syntax"] is True
    assert result["has_warnings"] is True
    warning_msgs = [w["message"] for w in result["warnings"]]
    assert any("Comparison to None using '=='" in m for m in warning_msgs)


def test_shadowing_builtins_warning():
    """Function or variable names shadowing Python built-ins should trigger a warning."""
    code = """
def list():
    return [1, 2, 3]
"""
    result = analyze_code(code, "python")
    assert result["is_valid_syntax"] is True
    assert result["has_warnings"] is True
    warning_msgs = [w["message"] for w in result["warnings"]]
    assert any("shadows Python built-in" in m for m in warning_msgs)


def test_division_by_zero_literal():
    """Static division by literal 0 should be flagged before execution."""
    code = """
def calculate():
    x = 100 / 0
    return x
"""
    result = analyze_code(code, "python")
    assert result["is_valid_syntax"] is True
    assert result["has_warnings"] is True
    warning_msgs = [w["message"] for w in result["warnings"]]
    assert any("ZeroDivisionError" in m for m in warning_msgs)


def test_unreachable_code_after_return():
    """Dead code following a return statement should be flagged."""
    code = """
def compute():
    return 42
    print("This will never execute")
"""
    result = analyze_code(code, "python")
    assert result["is_valid_syntax"] is True
    assert result["has_warnings"] is True
    warning_msgs = [w["message"] for w in result["warnings"]]
    assert any("Unreachable code detected" in m for m in warning_msgs)


def test_non_python_language_dispatch():
    """Non-Python languages should bypass Python AST parser without throwing Python syntax errors."""
    js_code = "function hello() { console.log('hello'); }"
    result = analyze_code(js_code, "javascript")
    assert result["language"] == "javascript"
    assert result["is_valid_syntax"] is True
    assert "bypassed" in result["summary"].lower()


def test_empty_source_code():
    """Empty or whitespace-only code should be handled gracefully."""
    result = analyze_code("   ", "python")
    assert result["is_valid_syntax"] is False
    assert "No code provided" in result["summary"]
