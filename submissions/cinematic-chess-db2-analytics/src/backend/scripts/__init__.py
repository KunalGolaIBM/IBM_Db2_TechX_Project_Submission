"""Shared helpers for explicit Db2 maintenance commands."""

from __future__ import annotations

import os
import re
from typing import Any

import ibm_db

from ..app.config import load_environment


_SCHEMA_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,127}$")


def db2_schema() -> str:
    load_environment()
    schema = os.getenv("DB2_SCHEMA", "CHESS").strip().upper()
    if not _SCHEMA_PATTERN.fullmatch(schema):
        raise ValueError("DB2_SCHEMA must be a valid unquoted Db2 identifier")
    return schema


def connect() -> Any:
    load_environment()
    dsn = os.getenv("DB2_DSN", "").strip()
    if not dsn:
        raise RuntimeError("DB2_DSN is required")
    connection = ibm_db.connect(
        dsn,
        os.getenv("DB2_USER", ""),
        os.getenv("DB2_PASSWORD", ""),
    )
    ibm_db.autocommit(connection, ibm_db.SQL_AUTOCOMMIT_OFF)
    return connection


def failure_label(action: str, connection: Any | None) -> str:
    """Return useful diagnostics without echoing a DSN, user, or password."""
    state = ibm_db.conn_error(connection) if connection is not None else None
    return f"{action} failed" + (f" (SQLSTATE {state})" if state else "")


def close_quietly(connection: Any | None) -> None:
    if connection is not None:
        try:
            ibm_db.close(connection)
        except Exception:
            pass
