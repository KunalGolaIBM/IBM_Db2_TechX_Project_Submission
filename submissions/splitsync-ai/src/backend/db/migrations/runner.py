"""Database migration runner for IBM Db2."""

import logging
import os
import sys
from pathlib import Path
from typing import Optional

if sys.platform == "win32":
    potential_paths = [
        os.path.join(sys.prefix, "Lib", "site-packages", "clidriver", "bin"),
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", ".venv", "Lib", "site-packages", "clidriver", "bin"),
    ]
    for p in potential_paths:
        abs_p = os.path.abspath(p)
        if os.path.isdir(abs_p):
            try:
                os.add_dll_directory(abs_p)
                os.environ["PATH"] = abs_p + os.pathsep + os.environ.get("PATH", "")
            except Exception:
                pass

try:
    import ibm_db  # type: ignore
except ImportError:
    ibm_db = None  # type: ignore

try:
    from db.connection import get_connection
except ImportError:
    from backend.db.connection import get_connection

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent


def ensure_migration_history_table(conn) -> None:
    """Ensure the MIGRATION_HISTORY table exists in Db2."""
    check_sql = (
        "SELECT COUNT(*) FROM SYSCAT.TABLES "
        "WHERE TABNAME = 'MIGRATION_HISTORY' AND TABSCHEMA = CURRENT SCHEMA"
    )
    stmt = ibm_db.exec_immediate(conn, check_sql)
    row = ibm_db.fetch_tuple(stmt)
    if row and row[0] == 0:
        logger.info("MIGRATION_HISTORY table not found; creating it...")
        create_sql = (
            "CREATE TABLE MIGRATION_HISTORY ("
            "    MIGRATION_ID VARCHAR(255) NOT NULL PRIMARY KEY,"
            "    APPLIED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        ibm_db.exec_immediate(conn, create_sql)
        ibm_db.commit(conn)
        logger.info("MIGRATION_HISTORY table created successfully.")


def get_applied_migrations(conn) -> set[str]:
    """Fetch set of migration IDs that have already been applied."""
    ensure_migration_history_table(conn)
    query_sql = "SELECT MIGRATION_ID FROM MIGRATION_HISTORY ORDER BY MIGRATION_ID ASC"
    stmt = ibm_db.exec_immediate(conn, query_sql)
    applied: set[str] = set()
    row = ibm_db.fetch_assoc(stmt)
    while row:
        migration_id = row.get("MIGRATION_ID") or row.get("migration_id")
        if migration_id:
            applied.add(str(migration_id).strip())
        row = ibm_db.fetch_assoc(stmt)
    return applied


def split_sql_statements(sql_text: str) -> list[str]:
    """Split a SQL script into executable statements, stripping line comments and empty blocks."""
    statements: list[str] = []
    raw_statements = sql_text.split(";")
    for raw in raw_statements:
        lines: list[str] = []
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.startswith("--"):
                continue
            lines.append(line)
        cleaned = "\n".join(lines).strip()
        if cleaned:
            statements.append(cleaned)
    return statements


def record_migration(conn, migration_id: str) -> None:
    """Record an applied migration into MIGRATION_HISTORY."""
    sql = "INSERT INTO MIGRATION_HISTORY (MIGRATION_ID, APPLIED_AT) VALUES (?, CURRENT_TIMESTAMP)"
    stmt = ibm_db.prepare(conn, sql)
    ibm_db.execute(stmt, (migration_id,))


def run_migrations(migrations_dir: Optional[Path] = None) -> list[str]:
    """Run all pending SQL migrations in alphabetical order.

    Returns:
        List of applied migration IDs in this run.
    """
    if ibm_db is None:
        logger.warning("ibm_db driver is not installed; skipping migrations.")
        return []

    target_dir = migrations_dir or MIGRATIONS_DIR
    if not target_dir.exists():
        logger.warning("Migrations directory %s does not exist.", target_dir)
        return []

    sql_files = sorted(target_dir.glob("*.sql"))
    if not sql_files:
        logger.info("No migration SQL files found in %s.", target_dir)
        return []

    conn = get_connection()
    applied = get_applied_migrations(conn)

    applied_in_this_run: list[str] = []

    for sql_file in sql_files:
        migration_id = sql_file.name
        if migration_id in applied:
            logger.debug("Migration %s already applied, skipping.", migration_id)
            continue

        logger.info("Applying migration: %s", migration_id)
        content = sql_file.read_text(encoding="utf-8")
        statements = split_sql_statements(content)

        try:
            for index, stmt in enumerate(statements, start=1):
                logger.debug("Executing statement %d/%d for %s", index, len(statements), migration_id)
                ibm_db.exec_immediate(conn, stmt)

            record_migration(conn, migration_id)
            ibm_db.commit(conn)
            applied_in_this_run.append(migration_id)
            logger.info("Successfully applied migration: %s", migration_id)
        except Exception as exc:
            ibm_db.rollback(conn)
            logger.error("Failed to apply migration %s: %s", migration_id, exc)
            raise RuntimeError(f"Migration {migration_id} failed: {exc}") from exc

    return applied_in_this_run


def get_migration_status() -> list[dict]:
    """Retrieve full history of applied migrations."""
    if ibm_db is None:
        return []

    try:
        conn = get_connection()
        ensure_migration_history_table(conn)
        stmt = ibm_db.exec_immediate(
            conn,
            "SELECT MIGRATION_ID, APPLIED_AT FROM MIGRATION_HISTORY ORDER BY MIGRATION_ID ASC"
        )
        status_list: list[dict] = []
        row = ibm_db.fetch_assoc(stmt)
        while row:
            migration_id = row.get("MIGRATION_ID") or row.get("migration_id")
            applied_at = row.get("APPLIED_AT") or row.get("applied_at")
            status_list.append({
                "migration_id": str(migration_id) if migration_id else "",
                "applied_at": str(applied_at) if applied_at else "",
            })
            row = ibm_db.fetch_assoc(stmt)
        return status_list
    except Exception as exc:
        logger.error("Error retrieving migration status: %s", exc)
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    try:
        applied_list = run_migrations()
        print(f"Applied {len(applied_list)} migration(s): {applied_list}")
    except Exception as error:
        print(f"Migration error: {error}")
        exit(1)
