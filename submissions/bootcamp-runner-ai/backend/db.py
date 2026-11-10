from __future__ import annotations

from collections.abc import Sequence
from typing import Any

try:
    import ibm_db
except ImportError:  # pragma: no cover - exercised in environments without Db2
    ibm_db = None


class DatabaseUnavailable(RuntimeError):
    """Raised when Db2 cannot be used; callers must expose offline behavior."""


class Db2Client:
    def __init__(self, dsn: str | None) -> None:
        self.dsn = dsn
        self.connection: Any = None

    def connect(self) -> None:
        if not self.dsn or ibm_db is None:
            raise DatabaseUnavailable("Db2 is not configured or ibm_db is unavailable")
        try:
            self.connection = ibm_db.connect(self.dsn, "", "")
        except Exception as exc:
            raise DatabaseUnavailable("Db2 connection failed") from exc

    def close(self) -> None:
        if self.connection is not None and ibm_db is not None:
            ibm_db.close(self.connection)
            self.connection = None

    def execute(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        if self.connection is None or ibm_db is None:
            raise DatabaseUnavailable("Db2 is offline")
        try:
            statement = ibm_db.prepare(self.connection, sql)
            for index, value in enumerate(params, start=1):
                ibm_db.bind_param(statement, index, value)
            ibm_db.execute(statement)
            rows: list[dict[str, Any]] = []
            result = ibm_db.fetch_assoc(statement)
            while result:
                rows.append(dict(result))
                result = ibm_db.fetch_assoc(statement)
            return rows
        except Exception as exc:
            raise DatabaseUnavailable("Db2 query failed") from exc
