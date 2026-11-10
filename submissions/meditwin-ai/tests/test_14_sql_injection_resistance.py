"""
Test Category 14: SQL Injection Resistance Test
Verifies that malicious injection payloads passed into queries remain literal values.
"""

from services.retrieval_service import identify_test_code, identify_test_name_keyword


def test_malicious_inputs_do_not_inject_sql():
    """Verify that SQL injection strings in queries do not match or break retrieval identification."""
    malicious_inputs = [
        "What is HbA1c'; DROP TABLE PATIENT; --",
        "Show me ' OR 1=1 --",
        "'; EXEC xp_cmdshell('dir'); --",
        "HbA1c' UNION SELECT username, password FROM users --",
        "<script>alert(1)</script>",
    ]

    for payload in malicious_inputs:
        code = identify_test_code(payload)
        # Should either identify HBA1C safely without syntax error, or return None
        if "hba1c" in payload.lower():
            assert code == "HBA1C"
        else:
            assert code is None

