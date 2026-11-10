"""Database executor interface.

The engine talks to databases through this small interface.
Real Postgres and Db2 executors will plug in here in a later
branch. Tests use InMemoryExecutor so the engine can be
tested with no database at all.
"""

from __future__ import annotations

from typing import Protocol

from parity.engine.result import ResultSet


class DatabaseExecutor(Protocol):
    """Run one read query and return its result set."""

    def execute(self, sql: str, timeout_seconds: float = 30.0) -> ResultSet:
        """Execute SQL and return the result. Raise on error."""
        ...


class InMemoryExecutor:
    """Executor that returns preset results. For tests only."""

    def __init__(self, results: dict[str, ResultSet]) -> None:
        self._results = dict(results)
        self.calls: list[str] = []

    def execute(self, sql: str, timeout_seconds: float = 30.0) -> ResultSet:
        """Return the preset result for exact SQL text."""
        self.calls.append(sql)
        key = sql.strip()
        if key not in self._results:
            raise KeyError(f"no preset result for SQL: {sql[:80]}")
        return self._results[key]
