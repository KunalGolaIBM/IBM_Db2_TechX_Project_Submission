"""Loads named SQL statements from db/queries/*.sql.

Blocks start with '-- name: <name>'. The token {{IMPACT_CTES}} is replaced by
the shared recursive CTE fragment, so every impact query is ONE Db2 statement.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from app.core.config import BACKEND_DIR

QUERY_DIR = BACKEND_DIR / "db" / "queries"
_NAME = re.compile(r"^--\s*name:\s*(\w+)\s*$", re.MULTILINE)


def _strip_comments(sql: str) -> str:
    return "\n".join(l for l in sql.splitlines() if not l.strip().startswith("--")).strip()


@lru_cache
def load_queries() -> dict[str, str]:
    raw: dict[str, str] = {}
    for f in sorted(QUERY_DIR.glob("*.sql")):
        text = f.read_text(encoding="utf-8")
        marks = list(_NAME.finditer(text))
        for i, m in enumerate(marks):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
            raw[m.group(1)] = _strip_comments(text[m.end():end])
    ctes = raw.get("IMPACT_CTES", "")
    return {k: v.replace("{{IMPACT_CTES}}", ctes) for k, v in raw.items() if k != "IMPACT_CTES"}


def sql(name: str) -> str:
    try:
        return load_queries()[name]
    except KeyError as exc:
        raise KeyError(f"Unknown named query '{name}' (see db/queries/*.sql)") from exc
