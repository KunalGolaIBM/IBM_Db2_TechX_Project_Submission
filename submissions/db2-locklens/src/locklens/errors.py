"""Exception types used across LockLens."""

from __future__ import annotations


class LockLensError(Exception):
    """Base class for all LockLens errors."""


class ConfigError(LockLensError):
    """Configuration is missing or invalid. ``problems`` lists every issue found."""

    def __init__(self, problems: list[str]):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


class Db2Error(LockLensError):
    """A Db2 operation failed. Carries the parsed SQLCODE/SQLSTATE when known."""

    def __init__(self, message: str, sqlcode: int | None = None, sqlstate: str | None = None):
        self.sqlcode = sqlcode
        self.sqlstate = sqlstate
        super().__init__(message)


class Db2ConnectionError(Db2Error):
    """Connecting to Db2 failed. ``kind`` is a stable classification for the UI."""

    KINDS = ("invalid_credentials", "database_not_found", "unreachable", "timeout",
             "driver_missing", "unknown")

    def __init__(self, message: str, kind: str = "unknown", sqlcode: int | None = None,
                 sqlstate: str | None = None):
        self.kind = kind
        super().__init__(message, sqlcode, sqlstate)


class Db2QueryError(Db2Error):
    """A statement failed after the connection was established."""


class Db2PermissionError(Db2QueryError):
    """The connected user is not authorized to run the statement (SQL0551N and friends)."""
