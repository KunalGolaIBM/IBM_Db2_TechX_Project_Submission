"""Tests for the Db2 migrations module."""

import pytest

from parity.migrations import MIGRATIONS, apply_migrations, migration_sql, pending_migrations


class FakeAdmin:
    """Minimal admin double with a table list."""

    def __init__(self, existing=()):
        self.existing = set(existing)
        self.created = []

    def table_exists(self, name):
        return name in self.existing

    def execute_ddl(self, sql):
        self.created.append(sql)
        for migration in MIGRATIONS:
            if migration.ddl == sql:
                self.existing.add(migration.table)


def test_migrations_are_ordered_and_unique():
    versions = [m.version for m in MIGRATIONS]
    tables = [m.table for m in MIGRATIONS]
    assert versions == sorted(versions)
    assert len(set(versions)) == len(versions)
    assert len(set(tables)) == len(tables)
    assert len(MIGRATIONS) == 4


def test_apply_creates_all_missing():
    admin = FakeAdmin()
    created = apply_migrations(admin)
    assert created == ("run", "comparison_result", "known_difference", "llm_cache")
    assert len(admin.created) == 4


def test_apply_is_idempotent():
    admin = FakeAdmin(existing=("run", "comparison_result", "known_difference", "llm_cache"))
    assert apply_migrations(admin) == ()
    assert admin.created == []


def test_apply_skips_existing():
    admin = FakeAdmin(existing=("run", "llm_cache"))
    created = apply_migrations(admin)
    assert created == ("comparison_result", "known_difference")


def test_pending_reflects_existing():
    admin = FakeAdmin(existing=("run",))
    pending = pending_migrations(admin)
    assert [m.table for m in pending] == [
        "comparison_result",
        "known_difference",
        "llm_cache",
    ]


def test_migration_sql_lookup():
    assert "CREATE TABLE run" in migration_sql("001")
    assert "VECTOR(384" in migration_sql("003")
    with pytest.raises(KeyError):
        migration_sql("999")
