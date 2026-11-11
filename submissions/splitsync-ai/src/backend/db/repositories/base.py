"""Base repository providing common Db2 database operations."""

import logging
from typing import Optional

try:
    from db.connection import execute_sql, fetch_one, fetch_all, commit, rollback
except ImportError:
    from backend.db.connection import execute_sql, fetch_one, fetch_all, commit, rollback

logger = logging.getLogger(__name__)


class BaseRepository:
    """Base class for all Db2 repositories with shared CRUD helpers."""

    table_name: str = ""

    def _insert(self, sql: str, params: tuple) -> None:
        """Insert a row using a prepared statement."""
        try:
            execute_sql(sql, tuple(params))
            commit()
        except Exception as exc:
            rollback()
            logger.error("Insert failed on %s: %s", self.table_name, exc)
            raise

    def _update(self, sql: str, params: tuple) -> None:
        """Update rows using a prepared statement."""
        try:
            execute_sql(sql, tuple(params))
            commit()
        except Exception as exc:
            rollback()
            logger.error("Update failed on %s: %s", self.table_name, exc)
            raise

    def _delete(self, sql: str, params: tuple) -> None:
        """Delete rows using a prepared statement."""
        try:
            execute_sql(sql, tuple(params))
            commit()
        except Exception as exc:
            rollback()
            logger.error("Delete failed on %s: %s", self.table_name, exc)
            raise

    def _fetch_one(self, sql: str, params: Optional[tuple] = None) -> Optional[dict]:
        """Fetch a single row."""
        param_tuple = tuple(params) if params is not None else None
        return fetch_one(sql, param_tuple)

    def _fetch_all(self, sql: str, params: Optional[tuple] = None) -> list[dict]:
        """Fetch all matching rows."""
        param_tuple = tuple(params) if params is not None else None
        return fetch_all(sql, param_tuple)

    def _execute_in_transaction(self, operations: list[tuple[str, tuple]]) -> None:
        """Execute multiple SQL statements in a single transaction."""
        try:
            for sql, params in operations:
                execute_sql(sql, tuple(params))
            commit()
        except Exception as exc:
            rollback()
            logger.error("Transaction failed on %s: %s", self.table_name, exc)
            raise
