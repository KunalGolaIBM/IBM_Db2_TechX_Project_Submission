import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from db2_support import VECTOR_DIMENSIONS, build_search_sql, embed, vector_literal


def test_embedding_is_stable_and_normalized():
    first = embed("How do I resolve a deadlock?")
    assert first == embed("How do I resolve a deadlock?")
    assert len(first) == VECTOR_DIMENSIONS
    assert 0.99 < sum(value * value for value in first) ** 0.5 < 1.01


def test_search_uses_db2_vector_distance_and_parameterized_category():
    sql = build_search_sql("DB2SUPPORT.SUPPORT_ARTICLES", "transactions")
    assert "VECTOR_DISTANCE" in sql
    assert "VECTOR(?, 8, FLOAT32)" in sql
    assert "category = ?" in sql
    assert "deadlock" not in sql


def test_vector_literal_has_expected_dimension():
    assert vector_literal([0.0] * VECTOR_DIMENSIONS) == "[0.0000000,0.0000000,0.0000000,0.0000000,0.0000000,0.0000000,0.0000000,0.0000000]"
