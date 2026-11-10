"""Tests for workload ingestion and tagging."""

from pathlib import Path

import pytest

from parity.ingest.loader import (
    deduplicate,
    load_sql_dir,
    load_sql_file,
    load_sql_text,
    split_statements,
)
from parity.ingest.models import extract_tables, normalize_sql, sql_hash, tag_query


def test_split_statements():
    assert split_statements("SELECT 1; SELECT 2;") == ["SELECT 1", "SELECT 2"]
    assert split_statements("  ; ") == []


def test_tag_read_only_query():
    query = tag_query("SELECT id FROM users WHERE id = 1", origin="file.sql")
    assert query.read_only is True
    assert query.tables == ("users",)
    assert "read_only" in query.tags
    assert query.query_id


def test_tag_write_query_marked_not_read_only():
    query = tag_query("DELETE FROM users", origin="log")
    assert query.read_only is False
    assert "write" in query.tags


def test_tag_nondeterministic():
    query = tag_query("SELECT now() FROM events", origin="log")
    assert query.nondeterministic_calls == ("now",)
    assert "nondeterministic" in query.tags


def test_extract_tables_join():
    tables = extract_tables("SELECT * FROM orders JOIN users ON orders.user_id = users.id")
    assert tables == ("orders", "users")


def test_hash_stable_and_whitespace_insensitive():
    assert sql_hash("SELECT  1") == sql_hash("SELECT 1")
    assert normalize_sql("SELECT\n 1") == "SELECT 1"


def test_empty_sql_rejected():
    with pytest.raises(ValueError):
        tag_query("   ", origin="file.sql")


def test_load_sql_text_multiple():
    queries = load_sql_text("SELECT 1; SELECT 2", origin="inline")
    assert len(queries) == 2
    assert all(q.origin == "inline" for q in queries)


def test_load_sql_file(tmp_path: Path):
    path = tmp_path / "q.sql"
    path.write_text("SELECT 1; SELECT 2;", encoding="utf-8")
    queries = load_sql_file(path)
    assert len(queries) == 2


def test_load_sql_file_missing(tmp_path: Path):
    with pytest.raises(ValueError, match="file not found"):
        load_sql_file(tmp_path / "missing.sql")


def test_load_sql_dir(tmp_path: Path):
    (tmp_path / "b.sql").write_text("SELECT 2;", encoding="utf-8")
    (tmp_path / "a.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "ignore.txt").write_text("SELECT 99;", encoding="utf-8")
    queries = load_sql_dir(tmp_path)
    assert [q.source_sql for q in queries] == ["SELECT 1", "SELECT 2"]


def test_deduplicate_keeps_first():
    queries = load_sql_text("SELECT 1; SELECT 1; SELECT 2", origin="inline")
    unique = deduplicate(queries)
    assert len(unique) == 2
    assert unique[0].source_sql == "SELECT 1"

def test_load_sql_file_with_bom(tmp_path: Path):
    path = tmp_path / "q.sql"
    path.write_bytes(b"\xef\xbb\xbfSELECT 1; SELECT 2;")
    queries = load_sql_file(path)
    assert len(queries) == 2
    assert all(q.read_only for q in queries)


def test_load_sql_text_with_bom():
    queries = load_sql_text("\ufeffSELECT 1", origin="inline")
    assert queries[0].read_only
    assert queries[0].source_sql == "SELECT 1"
