import pytest

from src.config import SQL_DIR
from src.sql_loader import bind, section, script_statements


def test_retrieval_query_uses_native_vector_distance():
    sql = section(SQL_DIR / "03_queries.sql", "retrieval")
    assert "VECTOR_DISTANCE" in sql
    assert "VECTOR(CAST(:query_vec AS VARCHAR(32672)), 384, FLOAT32)" in sql
    assert "COSINE" in sql


def test_bind_preserves_parameter_order_and_count():
    sql = section(SQL_DIR / "03_queries.sql", "retrieval")
    bound, params = bind(sql, {"state": "UP", "category": None, "query_vec": "[0.1,0.2]"})
    assert ":" not in bound.replace("'", "")
    assert bound.count("?") == len(params)
    assert params == ("UP", "UP", None, None, "[0.1,0.2]")


def test_missing_parameter_is_reported_clearly():
    sql = section(SQL_DIR / "03_queries.sql", "retrieval")
    with pytest.raises(Exception) as excinfo:
        bind(sql, {"state": "UP"})
    assert "category" in str(excinfo.value)


def test_section_lookup_fails_loudly():
    with pytest.raises(Exception) as excinfo:
        section(SQL_DIR / "03_queries.sql", "nope")
    assert "Available" in str(excinfo.value)


def test_procedure_script_is_split_on_its_own_terminator():
    statements = script_statements(SQL_DIR / "04_procedure.sql")
    assert len(statements) == 1
    assert statements[0].startswith("CREATE OR REPLACE PROCEDURE")
    assert statements[0].rstrip().endswith("END")


def test_schema_script_has_no_leftover_comments():
    statements = script_statements(SQL_DIR / "01_schema.sql")
    assert len(statements) > 10
    assert all("--" not in s for s in statements)
    assert any("VECTOR(384, FLOAT32)" in s for s in statements)
