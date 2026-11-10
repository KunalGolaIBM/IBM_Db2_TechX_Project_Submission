"""Tests for the sample shop workload."""

from pathlib import Path

from parity.ingest.loader import deduplicate, load_sql_dir
from parity.ingest.models import tag_query
from parity.translate.rules import find_untranslatable

ROOT = Path(__file__).parent.parent
WORKLOAD = ROOT / "samples" / "workload.sql"


def queries():
    return deduplicate(load_sql_dir(WORKLOAD.parent))


def test_workload_has_target_size():
    assert len(queries()) >= 100


def test_all_workload_queries_are_read_only():
    assert all(query.read_only for query in queries())


def test_workload_has_no_duplicate_queries():
    ids = [query.query_id for query in queries()]
    assert len(ids) == len(set(ids))


def test_workload_covers_four_tables():
    tables = {table for query in queries() for table in query.tables}
    assert {"customers", "products", "orders", "order_items"} <= tables


def test_workload_covers_query_families():
    sql = " ".join(query.source_sql.lower() for query in queries())
    assert "group by" in sql
    assert "join" in sql
    assert "order by" in sql
    assert "limit" in sql
    assert "ilike" in sql
    assert "count(*)" in sql
    assert "between" in sql
    assert "having" in sql


def test_workload_queries_are_deterministic():
    for query in queries():
        assert not query.nondeterministic_calls


def test_workload_translates_without_agents():
    """Most queries must be translatable by rules alone."""
    untranslatable = [
        query for query in queries() if find_untranslatable(query.source_sql)
    ]
    assert len(untranslatable) <= 2


def test_write_queries_are_refused():
    write = tag_query("DELETE FROM customers", "inline")
    assert write.read_only is False
