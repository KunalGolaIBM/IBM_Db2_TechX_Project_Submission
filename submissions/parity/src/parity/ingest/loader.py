"""Load SQL from files and text.

Supports .sql files in one directory and one query
per line in .txt files. Statements split on semicolons
outside of simple cases. This is a v1 loader. Complex
stored procedures are recorded as one block and marked
for human review in a later branch.
"""

from __future__ import annotations

from pathlib import Path

from parity.ingest.models import WorkloadQuery, tag_query


def split_statements(text: str) -> list[str]:
    """Split SQL text on semicolons. Drop empty parts."""
    parts = [part.strip() for part in text.split(";")]
    return [part for part in parts if part]


def load_sql_text(text: str, origin: str) -> list[WorkloadQuery]:
    """Tag every statement in one SQL text block.

    Windows tools often write a byte order mark, which
    breaks the first word check in the safety guard. A
    leading mark is cut before tagging.
    """
    text = text.lstrip("\ufeff")
    return [tag_query(stmt, origin) for stmt in split_statements(text)]


def load_sql_file(path: Path) -> list[WorkloadQuery]:
    """Load and tag every statement in one .sql file."""
    if not path.is_file():
        raise ValueError(f"file not found: {path}")
    text = path.read_text(encoding="utf-8-sig")
    return load_sql_text(text, origin=str(path))


def load_sql_dir(directory: Path) -> list[WorkloadQuery]:
    """Load every .sql file in one directory, sorted by name."""
    if not directory.is_dir():
        raise ValueError(f"directory not found: {directory}")
    queries: list[WorkloadQuery] = []
    for path in sorted(directory.glob("*.sql")):
        queries.extend(load_sql_file(path))
    return queries


def deduplicate(queries: list[WorkloadQuery]) -> list[WorkloadQuery]:
    """Drop repeats by content hash. Keep first seen order."""
    seen: set[str] = set()
    unique: list[WorkloadQuery] = []
    for query in queries:
        key = query.content_hash
        if key not in seen:
            seen.add(key)
            unique.append(query)
    return unique
