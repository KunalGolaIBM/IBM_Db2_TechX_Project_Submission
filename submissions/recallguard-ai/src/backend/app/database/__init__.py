"""Database bootstrap: picks IBM Db2 or the labelled dev-mode engine, runs migrations and seed."""
from __future__ import annotations

import logging
import threading
from pathlib import Path

from app.core.config import BACKEND_DIR, Settings, get_settings

from .base import Database, DatabaseError, IntegrityViolation, split_sql

log = logging.getLogger("recallguard.database")

MIGRATIONS_DIR = BACKEND_DIR / "db" / "migrations"
SEED_FILE = BACKEND_DIR / "db" / "seed" / "seed_data.sql"

_db: Database | None = None
_db_error: str | None = None
_lock = threading.Lock()

__all__ = ["Database", "DatabaseError", "IntegrityViolation", "get_db", "init_database", "db_status", "reset_database"]


def _build(settings: Settings) -> Database:
    if settings.db_mode == "db2":
        from .db2 import Db2Database

        return Db2Database(settings)
    from .devmode import DevModeDatabase

    log.warning("DB_MODE=dev — using the embedded DEV MODE engine. This is NOT IBM Db2.")
    return DevModeDatabase(settings.dev_db_path)


def run_migrations(db: Database) -> list[str]:
    if not db.table_exists("schema_migrations"):
        db.execute(
            "CREATE TABLE schema_migrations (version VARCHAR(80) NOT NULL, applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, "
            "CONSTRAINT pk_schema_migrations PRIMARY KEY (version))"
        )
    done = {r["version"] for r in db.query("SELECT version FROM schema_migrations")}
    applied = []
    for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if f.name in done:
            continue
        with db.transaction():
            for stmt in split_sql(f.read_text(encoding="utf-8")):
                db.execute(stmt)
            db.execute("INSERT INTO schema_migrations (version) VALUES (?)", (f.name,))
        applied.append(f.name)
        log.info("applied migration %s", f.name)
    return applied


def seed_if_empty(db: Database) -> bool:
    if db.scalar("SELECT COUNT(*) AS n FROM suppliers"):
        return False
    with db.transaction():
        for stmt in split_sql(SEED_FILE.read_text(encoding="utf-8")):
            db.execute(stmt)
    log.info("loaded seed data from %s", SEED_FILE.name)
    return True


def init_database(settings: Settings | None = None, bootstrap: bool = True) -> Database:
    """Create the global Database, apply migrations, seed, and bootstrap demo history."""
    global _db, _db_error
    settings = settings or get_settings()
    with _lock:
        if _db is not None:
            return _db
        try:
            db = _build(settings)
            if settings.auto_migrate:
                run_migrations(db)
            seeded = settings.auto_seed and seed_if_empty(db)
            _db, _db_error = db, None
        except DatabaseError as exc:
            _db_error = str(exc)
            log.error("database initialisation failed: %s", exc)
            raise
    if bootstrap and seeded:
        from app.services.bootstrap import bootstrap_history

        bootstrap_history(_db)
    return _db


def get_db() -> Database:
    if _db is None:
        return init_database()
    return _db


def db_status() -> dict:
    settings = get_settings()
    out = {"mode": settings.db_mode, "is_ibm_db2": settings.db_mode == "db2", "connected": False, "error": _db_error}
    if settings.db_mode == "db2":
        out["target"] = f"{settings.db2_host}:{settings.db2_port}/{settings.db2_database}"
    else:
        out["warning"] = "DEV MODE — embedded engine running the same SQL files. NOT IBM Db2. Set DB_MODE=db2 to use IBM Db2."
    if _db is not None:
        try:
            out.update(_db.ping())
            out["connected"] = True
            out["label"] = _db.label
            out["vector_supported"] = _db.supports_vector()
        except DatabaseError as exc:
            out["error"] = str(exc)
    return out


def reset_database() -> None:
    """Test helper: drop the global handle so the next get_db() re-initialises."""
    global _db
    with _lock:
        if _db is not None:
            _db.close()
        _db = None
