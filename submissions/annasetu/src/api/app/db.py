from collections.abc import Iterable
import importlib.util
import os
import re
from pathlib import Path
from typing import Any

# Python 3.8+ does not consult PATH when resolving extension DLLs. Keep a
# Windows DLL search handle open before loading ibm_db, including local venvs
# installed with pip's --target option.
_DLL_DIRECTORY_HANDLES = []
if os.name == "nt":
    _ibm_db_spec = importlib.util.find_spec("ibm_db")
    if _ibm_db_spec and _ibm_db_spec.origin:
        _clidriver_bin = Path(_ibm_db_spec.origin).parent / "clidriver" / "bin"
        if _clidriver_bin.is_dir():
            _DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(str(_clidriver_bin)))

import ibm_db_dbi

from .config import settings


class DatabaseConnectionError(RuntimeError):
    """Connection failure with driver DSN details removed."""


def connection_error_message(error: Exception) -> str:
    details = str(error)
    sqlstate = re.search(r"SQLSTATE=([A-Z0-9]+)", details)
    sqlcode = re.search(r"SQLCODE=(-?\d+)", details)
    codes = ", ".join(value for value in (
        f"SQLSTATE {sqlstate.group(1)}" if sqlstate else "",
        f"SQLCODE {sqlcode.group(1)}" if sqlcode else "",
    ) if value)
    suffix = f" ({codes})" if codes else ""
    return f"IBM Db2 connection failed{suffix}. Check the configured host, port, database, and credentials."


def connect():
    try:
        return ibm_db_dbi.connect(settings.db2_dsn, "", "")
    except Exception as exc:
        raise DatabaseConnectionError(connection_error_message(exc)) from None


def rows(sql: str, params: Iterable[Any] = (), conn=None) -> list[dict[str, Any]]:
    own = conn is None
    connection = conn or connect()
    cursor = connection.cursor()
    try:
        cursor.execute(sql, tuple(params))
        names = [item[0].lower() for item in cursor.description or []]
        return [dict(zip(names, row)) for row in cursor.fetchall()]
    finally:
        cursor.close()
        if own:
            connection.close()


def row(sql: str, params: Iterable[Any] = (), conn=None) -> dict[str, Any] | None:
    found = rows(sql, params, conn)
    return found[0] if found else None


def execute(sql: str, params: Iterable[Any] = (), conn=None) -> int:
    own = conn is None
    connection = conn or connect()
    cursor = connection.cursor()
    try:
        cursor.execute(sql, tuple(params))
        count = cursor.rowcount
        if own:
            connection.commit()
        return count
    except Exception:
        if own:
            connection.rollback()
        raise
    finally:
        cursor.close()
        if own:
            connection.close()


def jsonable(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    return value
