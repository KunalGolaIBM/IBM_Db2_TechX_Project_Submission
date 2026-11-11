"""Persistence of incidents in Db2 with de-duplication and automatic resolution.

De-duplication is enforced twice: by the application (look up the open incident for a finding's
``subject_key`` and update it) and by the database (a unique index over ``OPEN_KEY`` that is
NULL for resolved rows). A dashboard refresh therefore never creates a duplicate record; a new
row is created only when a previous incident for the same key has been resolved.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from importlib import resources
from typing import Any, Sequence

from ..db.connection import Executor
from ..errors import Db2Error, Db2QueryError
from ..models import Finding, Severity

log = logging.getLogger(__name__)

_SCHEMA_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,29}$")
_ALREADY_EXISTS = {601}           # SQL0601N: name already exists
_DUPLICATE_KEY = {803}            # SQL0803N: duplicate key in unique index
_STATUS = ("OPEN", "RESOLVED")
RESOLUTION_NOTE = "No longer observed in a successful monitoring snapshot"


@dataclass
class RecordResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    resolved: int = 0


def _trunc(text: str | None, n: int) -> str | None:
    if text is None:
        return None
    return text if len(text) <= n else text[: n - 1] + "…"


def load_schema_statements(schema: str) -> list[str]:
    """Return the DDL statements of ``schema.sql`` with the schema name substituted."""
    if not _SCHEMA_RE.match(schema):
        raise ValueError(f"Invalid schema name: {schema!r}")
    text = resources.files("locklens.db").joinpath("schema.sql").read_text(encoding="utf-8")
    text = text.replace("${SCHEMA}", schema)
    text = "\n".join(line for line in text.splitlines() if not line.strip().startswith("--"))
    return [s.strip() for s in text.split(";") if s.strip()]


class IncidentStore:
    def __init__(self, executor: Executor, schema: str = "LOCKLENS"):
        schema = schema.upper()
        if not _SCHEMA_RE.match(schema):
            raise ValueError(f"Invalid schema name: {schema!r}")
        self._db = executor
        self._schema = schema
        self._table = f"{schema}.LOCK_INCIDENTS"      # validated identifier, safe to interpolate

    # -- schema ------------------------------------------------------------------------
    def schema_ready(self) -> bool:
        rows = self._db.query(
            "SELECT COUNT(*) AS N FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TABNAME = 'LOCK_INCIDENTS'",
            (self._schema,))
        return bool(rows) and int(rows[0].get("N", 0)) > 0

    def init_schema(self) -> list[str]:
        """Create the schema, table and indexes. Returns a human-readable log of what happened."""
        log_lines: list[str] = []
        for stmt in load_schema_statements(self._schema):
            head = " ".join(stmt.split()[:4])
            try:
                self._db.execute(stmt)
                log_lines.append(f"OK       {head}")
            except Db2Error as exc:
                if exc.sqlcode in _ALREADY_EXISTS:
                    log_lines.append(f"EXISTS   {head}")
                else:
                    log_lines.append(f"FAILED   {head}: {exc}")
                    raise
        return log_lines

    # -- writing -----------------------------------------------------------------------
    def record(self, findings: Sequence[Finding], min_severity: Severity = Severity.WARNING
               ) -> RecordResult:
        result = RecordResult()
        for f in findings:
            if not f.persist or f.severity < min_severity or not f.subject_key:
                result.skipped += 1
                continue
            key = _trunc(f"{f.finding_type}|{f.subject_key}", 160)
            existing = self._db.query(
                f"SELECT INCIDENT_ID, SEVERITY, MAX_WAIT_SECONDS FROM {self._table} WHERE OPEN_KEY = ?",
                (key,))
            if existing:
                self._update(existing[0], f)
                result.updated += 1
                continue
            try:
                self._insert(key, f)
                result.created += 1
            except Db2QueryError as exc:
                if exc.sqlcode in _DUPLICATE_KEY:      # lost a race with another LockLens instance
                    again = self._db.query(
                        f"SELECT INCIDENT_ID, SEVERITY, MAX_WAIT_SECONDS FROM {self._table} "
                        "WHERE OPEN_KEY = ?", (key,))
                    if again:
                        self._update(again[0], f)
                        result.updated += 1
                        continue
                raise
        return result

    def _insert(self, key: str, f: Finding) -> None:
        self._db.execute(
            f"INSERT INTO {self._table} (INCIDENT_KEY, OPEN_KEY, STATUS, SEVERITY, CATEGORY, "
            "FINDING_TYPE, TITLE, BLOCKER_HANDLE, BLOCKER_INFO, WAITER_HANDLES, WAITER_INFO, "
            "LOCK_DETAILS, MAX_WAIT_SECONDS, EXPLANATION, RECOMMENDATION, EVIDENCE) "
            "VALUES (?, ?, 'OPEN', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (key, key, f.severity.name, f.category, f.finding_type, _trunc(f.title, 300),
             f.blocker_handle,
             _trunc(f"application handle {f.blocker_handle}" if f.blocker_handle is not None else None, 300),
             _trunc(",".join(map(str, f.waiter_handles)) or None, 300),
             _trunc(f"{len(f.waiter_handles)} waiting application(s)" if f.waiter_handles else None, 300),
             _trunc(f.lock_details or None, 500), f.max_wait_seconds, f.explanation,
             "\n".join(f"- {r}" for r in f.recommendations),
             json.dumps(f.evidence, ensure_ascii=False)))

    def _update(self, row: dict[str, Any], f: Finding) -> None:
        old = Severity.parse(row.get("SEVERITY", "INFO"))
        sev = max(old, f.severity)                                      # severity only escalates
        old_wait = row.get("MAX_WAIT_SECONDS")
        waits = [w for w in (old_wait, f.max_wait_seconds) if w is not None]
        self._db.execute(
            f"UPDATE {self._table} SET LAST_SEEN_AT = CURRENT TIMESTAMP, "
            "OBSERVATIONS = OBSERVATIONS + 1, SEVERITY = ?, MAX_WAIT_SECONDS = ?, "
            "WAITER_HANDLES = ?, EXPLANATION = ?, EVIDENCE = ? WHERE INCIDENT_ID = ?",
            (sev.name, max(int(w) for w in waits) if waits else None,
             _trunc(",".join(map(str, f.waiter_handles)) or None, 300), f.explanation,
             json.dumps(f.evidence, ensure_ascii=False), row["INCIDENT_ID"]))

    def resolve_absent(self, active_keys: set[str]) -> int:
        """Mark open incidents whose key was not seen in the latest *successful* snapshot."""
        open_rows = self._db.query(f"SELECT INCIDENT_ID, OPEN_KEY FROM {self._table} WHERE STATUS = 'OPEN'")
        resolved = 0
        for row in open_rows:
            if row.get("OPEN_KEY") in active_keys:
                continue
            self._db.execute(
                f"UPDATE {self._table} SET STATUS = 'RESOLVED', OPEN_KEY = NULL, "
                "RESOLVED_AT = CURRENT TIMESTAMP, RESOLUTION_NOTE = ? WHERE INCIDENT_ID = ?",
                (RESOLUTION_NOTE, row["INCIDENT_ID"]))
            resolved += 1
        return resolved

    @staticmethod
    def active_keys(findings: Sequence[Finding], min_severity: Severity) -> set[str]:
        return {_trunc(f"{f.finding_type}|{f.subject_key}", 160) or ""
                for f in findings if f.persist and f.severity >= min_severity and f.subject_key}

    # -- reading -----------------------------------------------------------------------
    def list_incidents(self, *, severity: str | None = None, category: str | None = None,
                       status: str | None = None, since: str | None = None, limit: int = 200
                       ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        if severity:
            Severity.parse(severity)
            where.append("SEVERITY = ?"); params.append(severity.upper())
        if category:
            where.append("CATEGORY = ?"); params.append(category)
        if status:
            if status.upper() not in _STATUS:
                raise ValueError(f"Unknown status: {status!r}")
            where.append("STATUS = ?"); params.append(status.upper())
        if since:
            if not re.match(r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2}:\d{2})?$", since):
                raise ValueError("since must be YYYY-MM-DD or YYYY-MM-DD HH:MM:SS")
            where.append("DETECTED_AT >= TIMESTAMP(CAST(? AS VARCHAR(26)))"); params.append(since)
        limit = max(1, min(int(limit), 1000))
        sql = (f"SELECT INCIDENT_ID, STATUS, SEVERITY, CATEGORY, FINDING_TYPE, TITLE, "
               "CHAR(DETECTED_AT) AS DETECTED_AT, CHAR(LAST_SEEN_AT) AS LAST_SEEN_AT, "
               "CHAR(RESOLVED_AT) AS RESOLVED_AT, OBSERVATIONS, BLOCKER_HANDLE, BLOCKER_INFO, "
               "WAITER_HANDLES, WAITER_INFO, LOCK_DETAILS, MAX_WAIT_SECONDS, RESOLUTION_NOTE, "
               f"EXPLANATION, RECOMMENDATION, EVIDENCE FROM {self._table}")
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += f" ORDER BY DETECTED_AT DESC FETCH FIRST {limit} ROWS ONLY"
        return self._db.query(sql, params)

    def count_open(self) -> int:
        rows = self._db.query(f"SELECT COUNT(*) AS N FROM {self._table} WHERE STATUS = 'OPEN'")
        return int(rows[0]["N"]) if rows else 0
