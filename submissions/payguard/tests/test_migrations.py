"""Version gates must parse the release, not the '2' in the product name."""
from contextlib import nullcontext

import pytest

from migrations import migrate


class MigrationRepo:
    def __init__(self, release):
        self.release, self.meta, self.executed = release, {}, []

    def _try(self, sql, ignore=()):
        self.executed.append(sql)

    def query(self, sql):
        return [{"service_level": self.release}]

    def transaction(self):
        return nullcontext()

    def execute(self, sql):
        self.executed.append(sql)

    def get_meta(self, key):
        return self.meta.get(key)

    def set_meta(self, key, value):
        self.meta[key] = value


@pytest.mark.parametrize("release,applied", [("DB2 v12.1.2.0", 0), ("DB2 v12.1.5.0", 1), ("DB2 v13.1.0.0", 1)])
def test_version_gate_and_idempotence(tmp_path, release, applied):
    path = tmp_path / "003_vector.sql"
    path.write_text("-- min-db2: 12.1.5\nCREATE VECTOR INDEX X ON T(V);", encoding="utf-8")
    repo = MigrationRepo(release)
    assert len(migrate(repo, 768, tmp_path)) == applied
    assert migrate(repo, 768, tmp_path) == []


def test_changed_applied_migration_is_rejected(tmp_path):
    path = tmp_path / "001_test.sql"
    path.write_text("CREATE TABLE X (V INT);", encoding="utf-8")
    repo = MigrationRepo("DB2 v12.1.5.0")
    migrate(repo, 768, tmp_path)
    path.write_text("CREATE TABLE Y (V INT);", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        migrate(repo, 768, tmp_path)


def test_invalid_dimension_rejected():
    with pytest.raises(ValueError):
        migrate(MigrationRepo("DB2 v12.1.5.0"), 0)


def test_unsupported_optional_index_is_deferred_without_marking_applied(tmp_path):
    (tmp_path / "003_vector.sql").write_text(
        "-- min-db2: 12.1.5\n-- optional-capability: vector_indexes\nCREATE VECTOR INDEX X ON T(V);", encoding="utf-8")
    repo = MigrationRepo("DB2 v12.1.5.0")
    original = repo._try
    def fail(sql, ignore=()):
        if sql.startswith("CREATE VECTOR"):
            raise RuntimeError("SQLSTATE=54008")
        original(sql, ignore)
    repo._try = fail
    assert migrate(repo, 768, tmp_path) == []
    assert "deferred" in repo.meta["capability:vector_indexes"]
    assert not any(key.startswith("migration:") for key in repo.meta)
