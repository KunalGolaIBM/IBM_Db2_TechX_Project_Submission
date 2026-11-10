"""Versioned Db2 migrations for the system of record.

Every table Parity owns lives here as one ordered list.
`apply_migrations` creates only the tables that are
missing, so a rerun is safe. The SQL files in
`migrations/` carry the same DDL for review.
"""

from __future__ import annotations

from dataclasses import dataclass

from parity.gateway.cache import LLM_CACHE_DDL
from parity.history.store import COMPARISON_RESULT_DDL, RUN_TABLE_DDL
from parity.kb.store import KNOWN_DIFFERENCE_DDL


@dataclass(frozen=True)
class Migration:
    """One versioned migration."""

    version: str
    table: str
    ddl: str


MIGRATIONS: tuple[Migration, ...] = (
    Migration(version="001", table="run", ddl=RUN_TABLE_DDL),
    Migration(version="002", table="comparison_result", ddl=COMPARISON_RESULT_DDL),
    Migration(version="003", table="known_difference", ddl=KNOWN_DIFFERENCE_DDL),
    Migration(version="004", table="llm_cache", ddl=LLM_CACHE_DDL),
)


def apply_migrations(admin) -> tuple[str, ...]:
    """Create every missing table. Return created table names."""
    created: list[str] = []
    for migration in MIGRATIONS:
        if not admin.table_exists(migration.table):
            admin.execute_ddl(migration.ddl)
            created.append(migration.table)
    return tuple(created)


def pending_migrations(admin) -> tuple[Migration, ...]:
    """Return migrations whose table is missing."""
    return tuple(m for m in MIGRATIONS if not admin.table_exists(m.table))


def migration_sql(version: str) -> str:
    """Return the DDL text for one version."""
    for migration in MIGRATIONS:
        if migration.version == version:
            return migration.ddl
    raise KeyError(f"unknown migration version: {version}")
