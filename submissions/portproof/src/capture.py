"""Take the workload from the source, so the proof is of what actually runs.

A corpus is what somebody thought to write down. A migration is judged on the
statements the application sends, weighted by how often it sends them. Three
of the four source engines keep that record themselves, and this module reads
it:

* **MySQL**: ``performance_schema.events_statements_summary_by_digest``. Its
  ``QUERY_SAMPLE_TEXT`` is one real statement per digest, literals intact, and
  ``COUNT_STAR`` is how often the digest ran.
* **SQL Server**: ``sys.dm_exec_query_stats`` joined to
  ``sys.dm_exec_sql_text``, the plan cache's own text and execution count.
* **PostgreSQL**: ``pg_stat_statements``, when the extension is installed.
  PostgreSQL normalises the text it keeps (a literal becomes ``$1``), so only
  statements that had no literals survive; the rest are counted and reported
  as needing the server log. That is a limit of the source, stated here
  rather than papered over.
* **Any engine, and SQLite**: a ``.sql`` file, one statement per ``;``.

What comes back is filtered three ways before anything is proved: it must be a
single read-only query (the same guard a model's output passes), it must parse
in the source dialect, and every table it names must be one of the tables the
caller asked about. A statement over the engine's own catalogue, or over a
table outside the migration, is not part of this workload.

Reading the record needs a privilege on the source (``SELECT`` on
``performance_schema``, ``VIEW SERVER STATE``, or ``pg_read_all_stats``).
Nothing is written to the source.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import sqlglot
from sqlglot import exp

from .corpus import Statement
from .safety import UnsafeSql, check_read_only

_SQLGLOT = {"postgres": "postgres", "mysql": "mysql", "tsql": "tsql", "sqlite": "sqlite"}

_HISTORY = {
    "mysql": (
        "SELECT QUERY_SAMPLE_TEXT, COUNT_STAR "
        "FROM performance_schema.events_statements_summary_by_digest "
        "WHERE QUERY_SAMPLE_TEXT IS NOT NULL AND DIGEST_TEXT LIKE 'SELECT%' "
        "ORDER BY COUNT_STAR DESC LIMIT 2000"
    ),
    "tsql": (
        "SELECT TOP 2000 SUBSTRING(t.text, (s.statement_start_offset / 2) + 1, "
        "((CASE s.statement_end_offset WHEN -1 THEN DATALENGTH(t.text) "
        "ELSE s.statement_end_offset END - s.statement_start_offset) / 2) + 1), "
        "s.execution_count "
        "FROM sys.dm_exec_query_stats AS s "
        "CROSS APPLY sys.dm_exec_sql_text(s.sql_handle) AS t "
        "ORDER BY s.execution_count DESC"
    ),
    "postgres": (
        "SELECT query, calls FROM pg_stat_statements "
        "WHERE query ILIKE 'select%' ORDER BY calls DESC LIMIT 2000"
    ),
}


_NEEDS = {
    "mysql": "It needs SELECT on performance_schema.",
    "tsql": "It needs VIEW SERVER STATE.",
    "postgres": "It needs the pg_stat_statements extension: add it to "
                "shared_preload_libraries, restart, and CREATE EXTENSION pg_stat_statements.",
}


@dataclass
class Captured:
    """What the source's own record held, and what was kept of it."""

    dialect: str
    origin: str
    #: (sql, executions), most executed first.
    kept: list[tuple[str, int]] = field(default_factory=list)
    seen: int = 0
    not_read_only: int = 0
    other_tables: int = 0
    normalised: int = 0
    unparsable: int = 0

    def summary(self) -> str:
        dropped = []
        if self.other_tables:
            dropped.append(f"{self.other_tables} over other tables")
        if self.not_read_only:
            dropped.append(f"{self.not_read_only} not a read-only query")
        if self.normalised:
            dropped.append(f"{self.normalised} with literals the engine replaced by placeholders")
        if self.unparsable:
            dropped.append(f"{self.unparsable} that did not parse")
        tail = f" (dropped: {', '.join(dropped)})" if dropped else ""
        return (f"{len(self.kept)} distinct statement(s) kept of {self.seen} "
                f"read from {self.origin}{tail}")

    def statements(self, schema: str) -> list[Statement]:
        return [
            Statement(self.dialect, f"{schema}.q{n:03d}_x{min(count, 99999)}", sql, schema=schema)
            for n, (sql, count) in enumerate(self.kept, start=1)
        ]


def tables_of(sql: str, dialect: str) -> set[str] | None:
    """The base tables a statement reads, lower-cased, or None if it will not parse."""
    try:
        tree = sqlglot.parse_one(sql, read=_SQLGLOT.get(dialect, dialect))
    except Exception:
        return None
    if tree is None:
        return None
    ctes = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    names = {t.name.lower() for t in tree.find_all(exp.Table) if t.name}
    qualified = [t for t in tree.find_all(exp.Table) if t.args.get("db") or t.args.get("catalog")]
    if qualified:
        # A schema-qualified name points somewhere specific on the source; the
        # proof runs in a namespace of its own and could not honour it.
        return {"<qualified>"}
    return names - ctes


def _filter(captured: Captured, rows: Sequence[tuple[Any, Any]], tables: Sequence[str],
            top: int) -> Captured:
    wanted = {t.lower() for t in tables}
    best: dict[str, int] = {}
    for text, count in rows:
        captured.seen += 1
        sql = " ".join(str(text or "").split()).rstrip(";").strip()
        if not sql:
            continue
        try:
            check_read_only(sql)
        except UnsafeSql:
            captured.not_read_only += 1
            continue
        if re.search(r"\$\d+|\?", re.sub(r"'(?:''|[^'])*'", "''", sql)):
            captured.normalised += 1
            continue
        used = tables_of(sql, captured.dialect)
        if used is None:
            captured.unparsable += 1
            continue
        if not used or not used <= wanted:
            captured.other_tables += 1
            continue
        best[sql] = best.get(sql, 0) + int(count or 0)
    captured.kept = sorted(best.items(), key=lambda kv: (-kv[1], kv[0]))[: max(1, top)]
    return captured


def from_engine(engine: Any, dialect: str, tables: Sequence[str], top: int = 50) -> Captured:
    """Read the source engine's own statement record."""
    query = _HISTORY.get(dialect)
    if query is None:
        raise ValueError(
            f"{dialect} keeps no statement history PortProof can read; pass a .sql file instead")
    conn = getattr(engine, "_conn", None)
    if conn is None:
        raise ValueError("this source engine exposes no connection to read history from")
    cur = conn.cursor()
    try:
        cur.execute(query)
        rows = [(r[0], r[1]) for r in cur.fetchall()]
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:  # pragma: no cover
            pass
        raise ValueError(
            f"could not read the {dialect} statement record ({str(exc).splitlines()[0][:120]}). "
            f"{_NEEDS[dialect]}"
        ) from exc
    finally:
        try:
            cur.close()
        except Exception:  # pragma: no cover
            pass
    origin = {
        "mysql": "performance_schema.events_statements_summary_by_digest",
        "tsql": "sys.dm_exec_query_stats",
        "postgres": "pg_stat_statements",
    }[dialect]
    return _filter(Captured(dialect=dialect, origin=origin), rows, tables, top)


def from_file(path: str | Path, dialect: str, tables: Sequence[str], top: int = 500) -> Captured:
    """Statements from a ``.sql`` file, one per ``;``. Repeats count as executions."""
    text = Path(path).read_text(encoding="utf-8")
    text = re.sub(r"--[^\n]*", "", text)
    parts = [p for p in (s.strip() for s in text.split(";")) if p]
    return _filter(Captured(dialect=dialect, origin=str(Path(path).name)),
                   [(p, 1) for p in parts], tables, top)
