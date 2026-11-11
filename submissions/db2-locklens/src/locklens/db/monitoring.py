"""Reads live lock information from Db2's native monitoring table functions.

Verified against IBM's Db2 11.5 documentation:

* ``MON_GET_LOCKS(search_args, member)``                 - every lock in the current database
* ``MON_GET_APPL_LOCKWAIT(application_handle, member[, system_appls])`` - every lock wait
* ``MON_GET_CONNECTION(application_handle, member)``      - application name, auth id, state
* ``MON_FORMAT_LOCK_NAME(lockname)``                      - decodes a lock name (table, row ...)

Member ``-2`` means "all members". IBM advises naming result columns explicitly because the
MON routines gain columns between releases, so the select list is built from the columns this
server actually reports (discovered with a ``WHERE 1=0`` probe) intersected with the columns
LockLens knows how to use. Nothing is invented: a column that is absent simply stays unset
and the UI says so.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Sequence

from ..errors import Db2Error, Db2PermissionError, Db2QueryError
from ..models import (LockRecord, LockWaitRecord, Note, ResourceInfo, SessionInfo, Snapshot)
from .connection import Executor

log = logging.getLogger(__name__)

_HEX_RE = re.compile(r"^[0-9A-Fa-f]{2,64}$")

LOCKS_WANTED = ["MEMBER", "APPLICATION_HANDLE", "LOCK_NAME", "LOCK_OBJECT_TYPE", "LOCK_MODE",
                "LOCK_CURRENT_MODE", "LOCK_STATUS", "LOCK_COUNT"]
LOCKWAIT_WANTED = ["LOCK_WAIT_START_TIME", "LOCK_NAME", "LOCK_OBJECT_TYPE", "LOCK_MODE",
                   "LOCK_CURRENT_MODE", "LOCK_MODE_REQUESTED", "LOCK_STATUS",
                   "REQ_APPLICATION_HANDLE", "REQ_MEMBER", "HLD_APPLICATION_HANDLE",
                   "HLD_MEMBER"]
CONNECTION_WANTED = ["APPLICATION_HANDLE", "APPLICATION_NAME", "APPLICATION_ID",
                     "SYSTEM_AUTH_ID", "CLIENT_HOSTNAME", "WORKLOAD_OCCURRENCE_STATE"]

# Table-function call candidates, tried in order. IBM's 11.5 page lists a third parameter
# (system_appls) for MON_GET_APPL_LOCKWAIT while its examples use two arguments, so both
# forms are accepted; the first one this server resolves is used.
_LOCKS_FN = ["MON_GET_LOCKS(NULL, -2)"]
_LOCKWAIT_FN = ["MON_GET_APPL_LOCKWAIT(NULL, -2)", "MON_GET_APPL_LOCKWAIT(NULL, -2, NULL)"]
_CONNECTION_FN = ["MON_GET_CONNECTION(NULL, -2)"]


def _from(fn: str, alias: str = "T") -> str:
    return f"TABLE({fn}) AS {alias}"

# Seconds waited, computed on the server so client/server clock skew cannot distort it.
_WAIT_SECONDS_EXPR = (
    "CASE WHEN T.LOCK_WAIT_START_TIME IS NULL THEN NULL ELSE "
    "(DAYS(CURRENT TIMESTAMP) - DAYS(T.LOCK_WAIT_START_TIME)) * 86400 + "
    "(MIDNIGHT_SECONDS(CURRENT TIMESTAMP) - MIDNIGHT_SECONDS(T.LOCK_WAIT_START_TIME)) END "
    "AS WAIT_SECONDS"
)

GRANT_HINT = ("Grant EXECUTE on the MON_GET_* routines to this user (or use a user with "
              "DBADM, SQLADM, DATAACCESS or SYSMON authority). See IBM's documentation for "
              "your Db2 version.")


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex().upper()
    text = str(value).strip()
    return text or None


def build_select(wanted: Sequence[str], available: Sequence[str], *, from_clause: str,
                 extra: Sequence[str] = (), max_rows: int | None = None) -> str | None:
    """Build ``SELECT <known columns> FROM <table function>`` or None when nothing matches.

    ``LOCK_NAME`` is returned as ``LOCK_NAME_HEX`` (lock names are binary).
    """
    avail = {c.upper() for c in available}
    columns: list[str] = []
    for col in wanted:
        if col.upper() not in avail:
            continue
        if col == "LOCK_NAME":
            columns.append("HEX(T.LOCK_NAME) AS LOCK_NAME_HEX")
        elif col == "LOCK_WAIT_START_TIME":
            columns.append("CHAR(T.LOCK_WAIT_START_TIME) AS LOCK_WAIT_START_TIME")
        else:
            columns.append(f"T.{col}")
    columns.extend(extra)
    if not columns:
        return None
    sql = f"SELECT {', '.join(columns)} FROM {from_clause}"
    if max_rows is not None:
        sql += f" FETCH FIRST {int(max_rows)} ROWS ONLY"
    return sql


class MonitoringClient:
    """Collects a :class:`Snapshot`. One instance per connection; not thread-safe."""

    def __init__(self, executor: Executor, max_rows: int = 2000, max_resolved_locks: int = 25):
        self._db = executor
        self._max_rows = max_rows
        self._max_resolved = max_resolved_locks
        self._columns: dict[str, list[str]] = {}
        self._fn: dict[str, str] = {}

    # -- discovery ---------------------------------------------------------------------
    def _discover(self, key: str, candidates: Sequence[str]) -> tuple[list[str], str]:
        """Return (columns, FROM clause) for the first call form this server accepts."""
        if key not in self._columns:
            last: Db2Error | None = None
            for fn in candidates:
                try:
                    cols, _ = self._db.query_with_columns(f"SELECT * FROM {_from(fn)} WHERE 1=0")
                except Db2PermissionError:
                    raise
                except Db2QueryError as exc:
                    last = exc
                    continue
                self._columns[key], self._fn[key] = cols, fn
                break
            else:
                assert last is not None
                raise last
        return self._columns[key], _from(self._fn[key])

    def reset_discovery(self) -> None:
        self._columns.clear()
        self._fn.clear()

    # -- collection --------------------------------------------------------------------
    def collect(self, resolve_resources: bool = True) -> Snapshot:
        snap = Snapshot(captured_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        self._collect_locks(snap)
        self._collect_waits(snap)
        if snap.waits:
            self._collect_sessions(snap)
            if resolve_resources:
                self._collect_resources(snap)
        snap.available_columns = dict(self._columns)
        return snap

    def _fail(self, snap: Snapshot, what: str, exc: Db2Error) -> None:
        if isinstance(exc, Db2PermissionError):
            snap.notes.append(Note("error", f"Not authorized to read {what} "
                                            f"(SQL{exc.sqlcode}N). {GRANT_HINT}"))
        elif exc.sqlcode in (204, 440, 206, 104, 4302) or (exc.sqlcode or 0) in (-204, -440):
            snap.notes.append(Note("error", f"{what} is not available on this Db2 server "
                                            f"(SQL{exc.sqlcode}N). LockLens needs Db2 LUW 10.1+ "
                                            "monitoring table functions."))
        else:
            snap.notes.append(Note("error", f"Reading {what} failed: {exc}"))
        log.warning("Monitoring query failed for %s: %s", what, exc)

    def _collect_locks(self, snap: Snapshot) -> None:
        try:
            avail, from_clause = self._discover("MON_GET_LOCKS", _LOCKS_FN)
            sql = build_select(LOCKS_WANTED, avail, from_clause=from_clause, max_rows=self._max_rows)
            if sql is None:
                snap.locks_available = False
                snap.notes.append(Note("warning", "MON_GET_LOCKS returned no usable columns."))
                return
            rows = self._db.query(sql)
        except Db2Error as exc:
            snap.locks_available = False
            self._fail(snap, "MON_GET_LOCKS", exc)
            return
        missing = [c for c in ("APPLICATION_HANDLE", "LOCK_STATUS") if c not in avail]
        if missing:
            snap.notes.append(Note("warning", "MON_GET_LOCKS does not report "
                                              + ", ".join(missing) + " on this server; "
                                              "holder cross-checks are limited."))
        if len(rows) >= self._max_rows:
            snap.notes.append(Note("warning", f"Lock list truncated at {self._max_rows} rows "
                                              "(LOCKLENS_MAX_ROWS)."))
        snap.locks = [LockRecord(
            application_handle=_as_int(r.get("APPLICATION_HANDLE")),
            lock_name_hex=_as_str(r.get("LOCK_NAME_HEX")),
            lock_status=_as_str(r.get("LOCK_STATUS")),
            lock_object_type=_as_str(r.get("LOCK_OBJECT_TYPE")),
            lock_mode=_as_str(r.get("LOCK_MODE")),
            lock_current_mode=_as_str(r.get("LOCK_CURRENT_MODE")),
            lock_count=_as_int(r.get("LOCK_COUNT")),
            member=_as_int(r.get("MEMBER"))) for r in rows]

    def _collect_waits(self, snap: Snapshot) -> None:
        try:
            avail, from_clause = self._discover("MON_GET_APPL_LOCKWAIT", _LOCKWAIT_FN)
            extra = [_WAIT_SECONDS_EXPR] if "LOCK_WAIT_START_TIME" in {a.upper() for a in avail} else []
            sql = build_select(LOCKWAIT_WANTED, avail, from_clause=from_clause, extra=extra,
                               max_rows=self._max_rows)
            if sql is None:
                snap.waits_available = False
                snap.notes.append(Note("warning", "MON_GET_APPL_LOCKWAIT returned no usable columns."))
                return
            rows = self._db.query(sql)
        except Db2Error as exc:
            snap.waits_available = False
            self._fail(snap, "MON_GET_APPL_LOCKWAIT", exc)
            return
        if "HLD_APPLICATION_HANDLE" not in avail:
            snap.notes.append(Note("warning", "MON_GET_APPL_LOCKWAIT does not report the holding "
                                              "application on this server; holders will be shown "
                                              "as unknown unless MON_GET_LOCKS identifies them."))
        if "LOCK_WAIT_START_TIME" not in avail:
            snap.notes.append(Note("info", "Wait durations are unavailable (no "
                                           "LOCK_WAIT_START_TIME column)."))
        snap.waits = [LockWaitRecord(
            req_application_handle=_as_int(r.get("REQ_APPLICATION_HANDLE")),
            hld_application_handle=_as_int(r.get("HLD_APPLICATION_HANDLE")),
            lock_name_hex=_as_str(r.get("LOCK_NAME_HEX")),
            lock_object_type=_as_str(r.get("LOCK_OBJECT_TYPE")),
            lock_mode=_as_str(r.get("LOCK_MODE")),
            lock_mode_requested=_as_str(r.get("LOCK_MODE_REQUESTED")),
            lock_current_mode=_as_str(r.get("LOCK_CURRENT_MODE")),
            lock_status=_as_str(r.get("LOCK_STATUS")),
            lock_wait_start_time=_as_str(r.get("LOCK_WAIT_START_TIME")),
            wait_seconds=_as_int(r.get("WAIT_SECONDS")),
            req_member=_as_int(r.get("REQ_MEMBER")),
            hld_member=_as_int(r.get("HLD_MEMBER"))) for r in rows]

    def _collect_sessions(self, snap: Snapshot) -> None:
        """Optional enrichment: who are the applications involved, and what are they doing?"""
        involved = {h for w in snap.waits for h in (w.req_application_handle, w.hld_application_handle)
                    if h}
        involved |= {lk.application_handle for lk in snap.locks
                     if lk.application_handle and lk.lock_name_hex in
                     {w.lock_name_hex for w in snap.waits}}
        if not involved:
            return
        try:
            avail, from_clause = self._discover("MON_GET_CONNECTION", _CONNECTION_FN)
            sql = build_select(CONNECTION_WANTED, avail, from_clause=from_clause,
                               max_rows=self._max_rows)
            if sql is None or "APPLICATION_HANDLE" not in {a.upper() for a in avail}:
                return
            rows = self._db.query(sql)
        except Db2Error as exc:
            note = ("Application names, users and states are unavailable: not authorized to "
                    "read MON_GET_CONNECTION. " + GRANT_HINT) if isinstance(exc, Db2PermissionError) \
                else f"Application details unavailable: {exc}"
            snap.notes.append(Note("warning", note))
            return
        for r in rows:
            handle = _as_int(r.get("APPLICATION_HANDLE"))
            if handle is None or handle not in involved:
                continue
            snap.sessions[handle] = SessionInfo(
                application_handle=handle,
                application_name=_as_str(r.get("APPLICATION_NAME")),
                application_id=_as_str(r.get("APPLICATION_ID")),
                system_auth_id=_as_str(r.get("SYSTEM_AUTH_ID")),
                client_hostname=_as_str(r.get("CLIENT_HOSTNAME")),
                workload_state=_as_str(r.get("WORKLOAD_OCCURRENCE_STATE")))

    def _decode_lock_name(self, name_hex: str) -> list[dict[str, Any]]:
        """Decode one lock name. Form A passes the hex text (as IBM's example does); if that
        yields nothing or fails, form B joins on the binary LOCK_NAME column of the lock-wait
        table function. Permission errors propagate; other failures fall through to form B."""
        select = "SELECT SUBSTR(F.NAME, 1, 32) AS NAME, SUBSTR(F.VALUE, 1, 128) AS VALUE "
        try:
            rows = self._db.query(
                select + "FROM TABLE(MON_FORMAT_LOCK_NAME(CAST(? AS VARCHAR(64)))) AS F", (name_hex,))
            if rows:
                return rows
        except Db2PermissionError:
            raise
        except Db2QueryError as exc:
            log.info("MON_FORMAT_LOCK_NAME (hex form) failed: %s", exc)
        fn = self._fn.get("MON_GET_APPL_LOCKWAIT", _LOCKWAIT_FN[0])
        return self._db.query(
            select + f"FROM {_from(fn, 'L')}, TABLE(MON_FORMAT_LOCK_NAME(L.LOCK_NAME)) AS F "
            "WHERE HEX(L.LOCK_NAME) = ?", (name_hex,))

    def _collect_resources(self, snap: Snapshot) -> None:
        """Decode the lock names involved in waits into table / row details (best effort)."""
        names = []
        for w in snap.waits:
            if w.lock_name_hex and w.lock_name_hex not in names:
                names.append(w.lock_name_hex)
        names = [n for n in names if _HEX_RE.match(n)][: self._max_resolved]
        unresolved = 0
        permission_note: Note | None = None
        for name in names:
            try:
                rows = self._decode_lock_name(name)
            except Db2PermissionError:
                permission_note = Note("warning", "Table names for locks are unavailable: not "
                                                  "authorized to run MON_FORMAT_LOCK_NAME. "
                                                  + GRANT_HINT)
                break
            except Db2QueryError as exc:
                unresolved += 1
                log.info("MON_FORMAT_LOCK_NAME failed for a lock: %s", exc)
                continue
            kv = {str(r.get("NAME", "")).upper(): _as_str(r.get("VALUE")) for r in rows}
            if not kv:
                unresolved += 1
                continue
            snap.resources[name] = ResourceInfo(
                lock_name_hex=name, table_schema=kv.get("TABSCHEMA"),
                table_name=kv.get("TABNAME"), object_type=kv.get("LOCK_OBJECT_TYPE"),
                row_id=kv.get("ROWID"), tablespace=kv.get("TBSP_NAME"))
        if permission_note:
            snap.notes.append(permission_note)
        elif unresolved:
            snap.notes.append(Note("info", f"{unresolved} lock name(s) could not be decoded; "
                                           "the locked object is shown as unresolved."))
