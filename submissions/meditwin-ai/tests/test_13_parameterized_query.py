"""
Test Category 13: Parameterized Query Test
Validates that all SQL queries in Db2Repository use parameter placeholders ('?') rather than string formatting.
"""

import inspect
from db.repository import Db2Repository


def test_repository_methods_use_parameter_markers():
    """Inspect repository source code to ensure parameterized markers '?' are used in all SQL."""
    source = inspect.getsource(Db2Repository)

    # Check for presence of parameter markers
    assert "?" in source

    # Ensure no f-string interpolation of direct user input into SQL clauses
    # (Only table/WHERE assembly with ? markers is allowed)
    disallowed_patterns = [
        "f\"SELECT * FROM PATIENT WHERE demo_code = '{",
        "f\"SELECT * FROM OBSERVATION WHERE test_code = '{",
        "f\"INSERT INTO PATIENT VALUES ('{",
        "f\"DELETE FROM",
    ]
    for pattern in disallowed_patterns:
        assert pattern not in source, f"Found insecure SQL construction: {pattern}"


def test_no_unrestricted_query_method():
    """Ensure repository does not expose an arbitrary raw SQL executor to the LLM."""
    repo_methods = [m for m in dir(Db2Repository) if not m.startswith("_")]
    assert "execute_arbitrary_sql" not in repo_methods
    assert "run_raw_sql" not in repo_methods
    assert "query" not in repo_methods

