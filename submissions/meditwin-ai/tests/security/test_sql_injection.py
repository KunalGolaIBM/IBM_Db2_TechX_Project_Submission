"""
Security Tests: SQL Injection Defense & Parameterized Query Verification
"""

import inspect
from db.repository import Db2Repository
from services.retrieval_service import identify_test_code


def test_repository_source_uses_parameter_markers_only():
    source = inspect.getsource(Db2Repository)
    assert "?" in source
    disallowed = [
        "f\"SELECT * FROM PATIENT WHERE demo_code = '{",
        "f\"INSERT INTO PATIENT VALUES ('{",
        "f\"SELECT * FROM OBSERVATION WHERE test_code = '{",
    ]
    for pattern in disallowed:
        assert pattern not in source, f"Vulnerable SQL pattern detected: {pattern}"


def test_malicious_query_payloads_do_not_inject():
    payloads = [
        "What is HbA1c'; DROP TABLE PATIENT; --",
        "' OR 1=1 --",
        "'; EXEC xp_cmdshell('dir'); --",
        "HbA1c' UNION SELECT username, password FROM users --",
    ]
    for p in payloads:
        code = identify_test_code(p)
        if "hba1c" in p.lower():
            assert code == "HBA1C"
        else:
            assert code is None

