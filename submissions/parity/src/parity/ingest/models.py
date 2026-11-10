"""Workload query record and tagging.

A WorkloadQuery is one SQL statement from a file, a log,
or ORM output, with tags that decide how Parity handles it.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from parity.engine.nondeterministic import find_nondeterministic_calls
from parity.engine.safety import assert_read_only

_TABLE_REF = re.compile(r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_.]*)", re.IGNORECASE)


def normalize_sql(sql: str) -> str:
    """Collapse whitespace for hashing. Keep case."""
    return " ".join(sql.strip().split())


def sql_hash(sql: str) -> str:
    """Return a stable hash for deduplication."""
    return hashlib.sha256(normalize_sql(sql).encode("utf-8")).hexdigest()


def extract_tables(sql: str) -> tuple[str, ...]:
    """Return sorted table names from FROM and JOIN clauses."""
    found = {match.group(1).split(".")[-1].lower() for match in _TABLE_REF.finditer(sql)}
    return tuple(sorted(found))


@dataclass(frozen=True)
class WorkloadQuery:
    """One ingested query with its tags."""

    source_sql: str
    origin: str
    query_id: str = ""
    tables: tuple[str, ...] = ()
    nondeterministic_calls: tuple[str, ...] = ()
    read_only: bool = True
    tags: tuple[str, ...] = ()
    created_at: str = ""

    @property
    def content_hash(self) -> str:
        """Stable hash of the normalized SQL."""
        return sql_hash(self.source_sql)


def tag_query(sql: str, origin: str) -> WorkloadQuery:
    """Build a tagged WorkloadQuery from raw SQL.

    Write queries are still recorded, but read_only is
    False so the runner can refuse them later.
    """
    text = sql.strip()
    if not text:
        raise ValueError("empty SQL")
    try:
        assert_read_only(text)
        read_only = True
    except ValueError:
        read_only = False
    calls = find_nondeterministic_calls(text)
    tables = extract_tables(text)
    tags: list[str] = []
    if read_only:
        tags.append("read_only")
    else:
        tags.append("write")
    if calls:
        tags.append("nondeterministic")
    if tables:
        tags.append("has_tables")
    now = datetime.now(UTC).isoformat()
    return WorkloadQuery(
        source_sql=text,
        origin=origin,
        query_id=sql_hash(text)[:12],
        tables=tables,
        nondeterministic_calls=calls,
        read_only=read_only,
        tags=tuple(tags),
        created_at=now,
    )
