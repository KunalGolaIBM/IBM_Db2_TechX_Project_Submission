"""Orchestrates one persistent Db2 connection, monitoring, the LangChain pipeline and storage.

A single :class:`LockLensRuntime` is shared by the dashboard (all browser sessions) and the CLI.
All use is serialised with a lock because one ``ibm_db`` connection must not be used by several
threads at once. The connection is reused across refreshes; it is never reopened per UI redraw.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from ..config import Settings
from ..db.connection import Db2Connection, Executor
from ..db.monitoring import MonitoringClient
from ..errors import Db2ConnectionError, Db2Error
from ..models import DiagnosisResult, Note, Snapshot
from ..pipeline.diagnostic_chain import run_diagnostics
from .incident_service import IncidentStore, RecordResult

log = logging.getLogger(__name__)


@dataclass
class ConnectionStatus:
    ok: bool
    message: str
    kind: str = ""
    server: str = ""


@dataclass
class CycleResult:
    snapshot: Snapshot | None = None
    diagnosis: DiagnosisResult | None = None
    recorded: RecordResult | None = None
    notes: list[Note] = field(default_factory=list)
    error: str | None = None
    connection_kind: str = ""
    refreshed_at: float = 0.0


class LockLensRuntime:
    def __init__(self, settings: Settings, executor: Executor | None = None,
                 connection_factory: Callable[[Settings], Any] = Db2Connection):
        self.settings = settings
        self._conn = None if executor is not None else connection_factory(settings)
        self._exec: Executor = executor if executor is not None else self._conn  # type: ignore[assignment]
        self._monitor = MonitoringClient(self._exec, settings.max_rows)
        self._store = IncidentStore(self._exec, settings.schema)
        self._lock = threading.RLock()
        self._last: CycleResult | None = None
        self._schema_ok: tuple[bool, float] | None = None

    # -- connection --------------------------------------------------------------------
    def test_connection(self) -> ConnectionStatus:
        with self._lock:
            try:
                if self._conn is not None:
                    self._conn.connect()
                    if not self._conn.ping():
                        return ConnectionStatus(False, "Connected, but a test query failed.", "unknown")
                server = ""
                try:
                    rows = self._exec.query("SELECT SERVICE_LEVEL FROM SYSIBMADM.ENV_INST_INFO")
                    server = str(rows[0].get("SERVICE_LEVEL", "")) if rows else ""
                except Db2Error:
                    log.debug("Could not read server level")
                return ConnectionStatus(True, "Connection to Db2 succeeded.", server=server)
            except Db2ConnectionError as exc:
                return ConnectionStatus(False, str(exc), exc.kind)
            except Db2Error as exc:
                return ConnectionStatus(False, str(exc), "unknown")

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
            self._schema_ok = None

    # -- incident store ----------------------------------------------------------------
    @property
    def store(self) -> IncidentStore:
        return self._store

    def schema_ready(self, max_age: float = 30.0) -> bool:
        with self._lock:
            if self._schema_ok and time.monotonic() - self._schema_ok[1] < max_age and self._schema_ok[0]:
                return True
            try:
                ok = self._store.schema_ready()
            except Db2Error:
                ok = False
            self._schema_ok = (ok, time.monotonic())
            return ok

    def init_schema(self) -> list[str]:
        with self._lock:
            lines = self._store.init_schema()
            self._schema_ok = None
            return lines

    def list_incidents(self, **filters: Any) -> list[dict[str, Any]]:
        with self._lock:
            return self._store.list_incidents(**filters)

    def count_open_incidents(self) -> int | None:
        with self._lock:
            if not self.schema_ready():
                return None
            try:
                return self._store.count_open()
            except Db2Error:
                return None

    # -- monitoring cycle --------------------------------------------------------------
    def refresh(self, *, min_age: float = 0.0, use_llm: bool = False,
                record: bool | None = None) -> CycleResult:
        """Collect a snapshot, run the pipeline and (optionally) store incidents.

        ``min_age`` reuses the previous result if it is younger than that many seconds, so
        navigating between dashboard pages does not hammer the database.
        """
        with self._lock:
            now = time.monotonic()
            if (self._last and not self._last.error and not use_llm
                    and min_age > 0 and now - self._last.refreshed_at < min_age):
                return self._last
            result = CycleResult(refreshed_at=now)
            try:
                if self._conn is not None:
                    self._conn.connect()
                snap = self._monitor.collect()
                if not snap.locks_available and not snap.waits_available and self._conn is not None \
                        and not self._conn.is_alive():
                    self._conn.connect()                       # one reconnect attempt
                    self._monitor.reset_discovery()
                    snap = self._monitor.collect()
            except Db2ConnectionError as exc:
                result.error, result.connection_kind = str(exc), exc.kind
                self._last = result
                return result
            except Db2Error as exc:
                result.error = str(exc)
                self._last = result
                return result

            result.snapshot = snap
            result.diagnosis = run_diagnostics(snap, self.settings, use_llm=use_llm)

            do_record = self.settings.auto_record if record is None else record
            if do_record:
                result.recorded = self._record(result, snap)
            self._last = result
            return result

    def _record(self, result: CycleResult, snap: Snapshot) -> RecordResult | None:
        if not self.schema_ready():
            result.notes.append(Note("info", "Incident history is not initialised yet. Use "
                                             "Settings -> Initialise incident tables."))
            return None
        try:
            minimum = self.settings.record_min_severity
            findings = result.diagnosis.findings  # type: ignore[union-attr]
            rec = self._store.record(findings, minimum)
            if snap.locks_available and snap.waits_available:    # only trust a complete snapshot
                rec.resolved = self._store.resolve_absent(self._store.active_keys(findings, minimum))
            return rec
        except Db2Error as exc:
            result.notes.append(Note("error", f"Recording incidents failed: {exc}"))
            return None

    @property
    def last(self) -> CycleResult | None:
        return self._last
