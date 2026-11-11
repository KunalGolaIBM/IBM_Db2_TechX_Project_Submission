"""REAL audit adapter — persists audit rows into the Db2 ``APP_AUDIT`` table.

M2 completion notes:
- writes the **extended** APP_AUDIT schema (migration 001): actor type,
  session id, client request id, operation type, intent, question, generated
  SQL, status, latency and a **sanitized** METADATA CLOB,
- every metadata/detail payload passes through
  ``app.security.sanitize.sanitize_metadata`` immediately before insert —
  passwords/tokens/DSNs are redacted even if a caller passes raw text,
- driver errors are mapped (SQLSTATE classification) and surfaced without
  leaking connection strings; failed writes raise ``AdapterUnavailableError``
  (callers treat audit as best-effort and log — they never expose the
  underlying DB error to end users),
- parameterized qmark binding only; connections are short-lived.

Least-privilege: writes run as the application's Db2 account with
``GRANT SELECT, INSERT ON APP.APP_AUDIT TO <ro_user>`` (migration 003).

NEVER executed against a live database on the development machine —
offline unit tests use a fake ``ibm_db_dbi`` module.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import socket
import time
from datetime import datetime
from typing import Any

from app.adapters.base import AuditRecord, ProbeResult
from app.core.config import Settings
from app.core.errors import AdapterUnavailableError
from app.database.dsn import connect_args, sanitize
from app.security.sanitize import sanitize_metadata

logger = logging.getLogger(__name__)


class Db2AuditAdapter:
    """Audit persistence backed by the Db2 APP_AUDIT table."""

    probe_name = "audit"
    provider_id = "db2"
    mode = "real"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._closed = False

    # -- SQL ----------------------------------------------------------------
    @property
    def _insert_sql(self) -> str:
        return (
            f"INSERT INTO {self._settings.app_schema}.APP_AUDIT ("
            "ACTOR_TYPE, SESSION_ID, CLIENT_REQ_ID, OPERATION, INTENT, "
            "QUESTION, SQL_TEXT, STATUS, LATENCY_MS, METADATA) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )

    @property
    def _select_sql(self) -> str:
        # Db2 does not allow parameter markers in FETCH FIRST — cap in Python.
        return (
            f"SELECT AUDIT_ID, REQ_TS, OPERATION, INTENT, QUESTION, STATUS, "
            f"LATENCY_MS, CLIENT_REQ_ID, SESSION_ID, METADATA "
            f"FROM {self._settings.app_schema}.APP_AUDIT "
            "ORDER BY AUDIT_ID DESC "
            f"FETCH FIRST {max(1, min(self._list_limit, 500))} ROWS ONLY"
        )

    _list_limit = 50

    # -- probes -------------------------------------------------------------
    def ping(self) -> ProbeResult:
        if self._closed:
            return ProbeResult(
                name=self.probe_name,
                status="unavailable",
                mode=self.mode,
                latency_ms=0.0,
                detail="audit adapter closed",
            )
        start = time.perf_counter()

        def elapsed() -> float:
            return (time.perf_counter() - start) * 1000

        if importlib.util.find_spec("ibm_db_dbi") is None:
            return ProbeResult(
                name=self.probe_name,
                status="unavailable",
                mode=self.mode,
                latency_ms=elapsed(),
                detail="ibm_db driver missing — audit writes disabled "
                "(install requirements-integration.txt).",
            )
        timeout = max(self._settings.db2_connect_timeout_ms / 1000, 0.2)
        try:
            with socket.create_connection(
                (self._settings.db2_host, self._settings.db2_port), timeout=timeout
            ):
                pass
        except OSError as exc:
            return ProbeResult(
                name=self.probe_name,
                status="unavailable",
                mode=self.mode,
                latency_ms=elapsed(),
                detail=f"Db2 not reachable — audit writes disabled "
                f"({exc.strerror or exc}).",
            )
        return ProbeResult(
            name=self.probe_name,
            status="ok",
            mode=self.mode,
            latency_ms=elapsed(),
            detail=f"Audit writes enabled (APP_AUDIT @ {self._settings.db2_host})",
        )

    # -- writes / reads ------------------------------------------------------
    def _connect(self):
        try:
            import ibm_db_dbi
        except ImportError as exc:
            raise AdapterUnavailableError(
                "ibm_db driver is not installed — audit persistence unavailable "
                "(pip install -r requirements-integration.txt)."
            ) from exc
        dsn, user, password = connect_args(self._settings)
        try:
            return ibm_db_dbi.connect(dsn, user, password)
        except Exception as exc:
            raise AdapterUnavailableError(
                "Cannot connect to Db2 for audit write: "
                f"{sanitize(str(exc), self._settings)}"
            ) from exc

    @staticmethod
    def _metadata_json(entry: AuditRecord) -> str | None:
        """Build the sanitized METADATA payload (never secrets)."""
        payload: dict[str, Any] = {}
        if entry.detail:
            payload["detail"] = entry.detail
        if entry.operation and entry.operation != "chat":
            payload["operation"] = entry.operation
        if entry.metadata:  # caller-supplied extras, merged into one JSON doc
            try:
                extras = json.loads(entry.metadata)
            except ValueError:
                extras = None
            if isinstance(extras, dict):
                payload.update(extras)
            else:
                payload["extra"] = entry.metadata
        if not payload:
            return None
        return sanitize_metadata(json.dumps(payload, ensure_ascii=False, default=str))

    def record(self, entry: AuditRecord) -> int:
        if self._closed:
            raise AdapterUnavailableError("audit adapter closed")
        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                self._insert_sql,
                (
                    "copilot_user",
                    entry.session_id,
                    entry.request_id,
                    entry.operation or "chat",
                    entry.intent,
                    entry.question,
                    entry.sql_text,
                    entry.status,
                    entry.latency_ms,
                    self._metadata_json(entry),
                ),
            )
            conn.commit()
            new_id = getattr(cursor, "lastrowid", None)
            audit_id = int(new_id) if isinstance(new_id, int) else 0
            logger.debug(
                "audit row written id=%d status=%s operation=%s request_id=%s",
                audit_id,
                entry.status,
                entry.operation,
                entry.request_id or "-",
            )
            return audit_id
        except AdapterUnavailableError:
            raise
        except Exception as exc:
            from app.adapters.db.db2_db import classify_db_error

            info = classify_db_error(exc)
            raise AdapterUnavailableError(
                f"Audit write failed [{info.category}, SQLSTATE {info.sqlstate}]",
                detail={"hint": info.hint, "table": "APP_AUDIT"},
            ) from exc
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001 — close is best-effort
                pass

    def list_recent(self, limit: int = 50) -> list[AuditRecord]:
        if self._closed:
            raise AdapterUnavailableError("audit adapter closed")
        self._list_limit = max(1, min(limit, 500))
        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute(self._select_sql)
            entries: list[AuditRecord] = []
            for (
                audit_id,
                req_ts,
                operation,
                intent,
                question,
                status,
                latency_ms,
                client_req_id,
                session_id,
                metadata,
            ) in cursor.fetchall():
                ts = (
                    req_ts.isoformat()
                    if isinstance(req_ts, datetime)
                    else str(req_ts or "")
                )
                entries.append(
                    AuditRecord(
                        id=int(audit_id),
                        timestamp=ts,
                        operation=str(operation or "chat"),
                        intent=str(intent or ""),
                        question=str(question or ""),
                        status=str(status or ""),
                        latency_ms=int(latency_ms or 0),
                        request_id=str(client_req_id) if client_req_id else None,
                        session_id=str(session_id) if session_id else None,
                        detail=str(metadata) if metadata else None,
                    )
                )
            return entries
        except AdapterUnavailableError:
            raise
        except Exception as exc:
            from app.adapters.db.db2_db import classify_db_error

            info = classify_db_error(exc)
            raise AdapterUnavailableError(
                f"Audit read failed [{info.category}, SQLSTATE {info.sqlstate}]",
                detail={"hint": info.hint},
            ) from exc
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001 — close is best-effort
                pass

    def close(self) -> None:
        self._closed = True
