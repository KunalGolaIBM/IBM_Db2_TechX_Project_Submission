"""Storage adapters for IBM Db2 and the local SQLite test backend.

Db2 values are always passed as parameter markers. SQL identifiers are fixed
constants in this module; user input is never interpolated into SQL identifiers.
"""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Iterator

from .config import get_settings, sqlite_path


DB2_SCHEMA = [
    """CREATE TABLE ESAI_EQUIPMENT (
        EQUIPMENT_ID VARCHAR(64) NOT NULL PRIMARY KEY,
        APPLIANCE_NAME VARCHAR(128) NOT NULL,
        CREATED_AT VARCHAR(35) NOT NULL
    )""",
    """CREATE TABLE ESAI_TELEMETRY (
        TELEMETRY_ID VARCHAR(36) NOT NULL PRIMARY KEY,
        EQUIPMENT_ID VARCHAR(64) NOT NULL,
        APPLIANCE_ID VARCHAR(64) NOT NULL,
        VRMS_V DOUBLE,
        IRMS_A DOUBLE,
        APPARENT_POWER_VA DOUBLE,
        RUNTIME_S DOUBLE,
        TEMPERATURE_C DOUBLE,
        VIBRATION_RMS DOUBLE,
        RELAY_STATE VARCHAR(12),
        SOURCE VARCHAR(32),
        RECORDED_AT VARCHAR(35) NOT NULL
    )""",
    """CREATE TABLE ESAI_EVENTS (
        EVENT_ID VARCHAR(36) NOT NULL PRIMARY KEY,
        EQUIPMENT_ID VARCHAR(64) NOT NULL,
        APPLIANCE_ID VARCHAR(64) NOT NULL,
        SEVERITY VARCHAR(12) NOT NULL,
        ANOMALY_SCORE DOUBLE,
        FEATURE_NAME VARCHAR(64),
        OBSERVED_VALUE DOUBLE,
        BASELINE_MEAN DOUBLE,
        BASELINE_STD DOUBLE,
        EXPLANATION VARCHAR(2048),
        RECOMMENDED_ACTION VARCHAR(2048),
        CREATED_AT VARCHAR(35) NOT NULL
    )""",
]

DB2_INDEXES = [
    "CREATE INDEX ESAI_TELEM_APP_TIME ON ESAI_TELEMETRY (APPLIANCE_ID, RECORDED_AT)",
    "CREATE INDEX ESAI_EVENT_APP_TIME ON ESAI_EVENTS (APPLIANCE_ID, CREATED_AT)",
]

SQLITE_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS esai_equipment (
        equipment_id TEXT PRIMARY KEY,
        appliance_name TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS esai_telemetry (
        telemetry_id TEXT PRIMARY KEY,
        equipment_id TEXT NOT NULL,
        appliance_id TEXT NOT NULL,
        vrms_v REAL,
        irms_a REAL,
        apparent_power_va REAL,
        runtime_s REAL,
        temperature_c REAL,
        vibration_rms REAL,
        relay_state TEXT,
        source TEXT,
        recorded_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS esai_events (
        event_id TEXT PRIMARY KEY,
        equipment_id TEXT NOT NULL,
        appliance_id TEXT NOT NULL,
        severity TEXT NOT NULL,
        anomaly_score REAL,
        feature_name TEXT,
        observed_value REAL,
        baseline_mean REAL,
        baseline_std REAL,
        explanation TEXT,
        recommended_action TEXT,
        created_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS esai_telem_app_time ON esai_telemetry(appliance_id, recorded_at)",
    "CREATE INDEX IF NOT EXISTS esai_event_app_time ON esai_events(appliance_id, created_at)",
]

TELEMETRY_COLUMNS = (
    "telemetry_id", "equipment_id", "appliance_id", "vrms_v", "irms_a",
    "apparent_power_va", "runtime_s", "temperature_c", "vibration_rms",
    "relay_state", "source", "recorded_at",
)
EVENT_COLUMNS = (
    "event_id", "equipment_id", "appliance_id", "severity", "anomaly_score",
    "feature_name", "observed_value", "baseline_mean", "baseline_std",
    "explanation", "recommended_action", "created_at",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _bounded_limit(limit: int, maximum: int = 500) -> int:
    return max(1, min(int(limit), maximum))


def _record_values(row: dict[str, Any], columns: tuple[str, ...]) -> list[Any]:
    return [row.get(column) for column in columns]


class SQLiteStore:
    """Local backend for tests and an offline demo; not the hackathon Db2 proof."""

    backend = "sqlite"

    def __init__(self, path: str | None = None):
        self.path = path or sqlite_path()
        self.init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 15000")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self._connection() as conn:
            for statement in SQLITE_SCHEMA:
                conn.execute(statement)

    @staticmethod
    def _upsert_equipment(conn: sqlite3.Connection, equipment_id: str, appliance_name: str) -> None:
        conn.execute(
            "INSERT INTO esai_equipment (equipment_id, appliance_name, created_at) VALUES (?, ?, ?) "
            "ON CONFLICT(equipment_id) DO UPDATE SET appliance_name=excluded.appliance_name",
            (equipment_id, appliance_name, utc_now()),
        )

    def upsert_equipment(self, equipment_id: str, appliance_name: str) -> None:
        with self._connection() as conn:
            self._upsert_equipment(conn, equipment_id, appliance_name)

    def insert_telemetry(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = dict(payload)
        if not row.get("equipment_id") or not row.get("appliance_id"):
            raise ValueError("equipment_id and appliance_id are required")
        row.setdefault("telemetry_id", str(uuid.uuid4()))
        row["recorded_at"] = row.get("recorded_at") or utc_now()
        appliance_name = row.get("appliance_name") or row["appliance_id"]
        values = _record_values(row, TELEMETRY_COLUMNS)
        with self._connection() as conn:
            # Keep metadata upsert and telemetry insert in one transaction.
            self._upsert_equipment(conn, row["equipment_id"], appliance_name)
            placeholders = ",".join(["?"] * len(TELEMETRY_COLUMNS))
            conn.execute(
                f"INSERT INTO esai_telemetry ({','.join(TELEMETRY_COLUMNS)}) VALUES ({placeholders})",
                values,
            )
        return row

    def recent_telemetry(self, appliance_id: str, limit: int = 100) -> list[dict[str, Any]]:
        safe_limit = _bounded_limit(limit)
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM esai_telemetry WHERE appliance_id=? "
                "ORDER BY recorded_at DESC, telemetry_id DESC LIMIT ?",
                (appliance_id, safe_limit),
            ).fetchall()
        # Analytics expects chronological order.
        return [dict(row) for row in reversed(rows)]

    def insert_event(self, event: dict[str, Any]) -> dict[str, Any]:
        row = dict(event)
        row.setdefault("event_id", str(uuid.uuid4()))
        row.setdefault("created_at", utc_now())
        missing = [key for key in ("equipment_id", "appliance_id", "severity") if not row.get(key)]
        if missing:
            raise ValueError("Missing event fields: " + ", ".join(missing))
        values = _record_values(row, EVENT_COLUMNS)
        with self._connection() as conn:
            placeholders = ",".join(["?"] * len(EVENT_COLUMNS))
            conn.execute(
                f"INSERT INTO esai_events ({','.join(EVENT_COLUMNS)}) VALUES ({placeholders})",
                values,
            )
        return row

    def list_events(self, appliance_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        safe_limit = _bounded_limit(limit)
        with self._connection() as conn:
            if appliance_id:
                rows = conn.execute(
                    "SELECT * FROM esai_events WHERE appliance_id=? "
                    "ORDER BY created_at DESC, event_id DESC LIMIT ?",
                    (appliance_id, safe_limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM esai_events ORDER BY created_at DESC, event_id DESC LIMIT ?",
                    (safe_limit,),
                ).fetchall()
        return [dict(row) for row in rows]

    def counts(self) -> dict[str, int]:
        with self._connection() as conn:
            telemetry = conn.execute("SELECT COUNT(*) FROM esai_telemetry").fetchone()[0]
            events = conn.execute("SELECT COUNT(*) FROM esai_events").fetchone()[0]
        return {"telemetry_count": int(telemetry), "event_count": int(events)}


class Db2Store:
    """IBM Db2 for LUW adapter using the supported ibm_db_dbi DB-API layer."""

    backend = "db2"

    def __init__(self):
        settings = get_settings()
        settings.validate()
        try:
            import ibm_db_dbi
        except ImportError as exc:
            raise RuntimeError("Install the IBM Db2 Python driver with `pip install ibm-db`.") from exc
        self._driver = ibm_db_dbi
        self.connection_string = settings.db2_connection_string
        self.init_schema()

    def _connect(self):
        return self._driver.connect(self.connection_string, "", "")

    @contextmanager
    def _connection(self):
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            conn.close()

    @staticmethod
    def _is_object_exists_error(exc: Exception) -> bool:
        message = str(exc).lower()
        return "42710" in message or "already exists" in message or "sql0601n" in message

    def init_schema(self) -> None:
        with self._connection() as conn:
            cursor = conn.cursor()
            for statement in DB2_SCHEMA + DB2_INDEXES:
                object_name = statement.split("(", 1)[0].split()[-1]
                try:
                    cursor.execute(statement)
                except Exception as exc:
                    if not self._is_object_exists_error(exc):
                        raise RuntimeError(f"Db2 schema setup failed for {object_name}: {exc}") from exc

    @staticmethod
    def _upsert_equipment(cursor, equipment_id: str, appliance_name: str) -> None:
        cursor.execute(
            "SELECT EQUIPMENT_ID FROM ESAI_EQUIPMENT WHERE EQUIPMENT_ID=?",
            (equipment_id,),
        )
        if cursor.fetchone():
            cursor.execute(
                "UPDATE ESAI_EQUIPMENT SET APPLIANCE_NAME=? WHERE EQUIPMENT_ID=?",
                (appliance_name, equipment_id),
            )
        else:
            cursor.execute(
                "INSERT INTO ESAI_EQUIPMENT (EQUIPMENT_ID, APPLIANCE_NAME, CREATED_AT) VALUES (?, ?, ?)",
                (equipment_id, appliance_name, utc_now()),
            )

    def upsert_equipment(self, equipment_id: str, appliance_name: str) -> None:
        with self._connection() as conn:
            self._upsert_equipment(conn.cursor(), equipment_id, appliance_name)

    def insert_telemetry(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = dict(payload)
        if not row.get("equipment_id") or not row.get("appliance_id"):
            raise ValueError("equipment_id and appliance_id are required")
        row.setdefault("telemetry_id", str(uuid.uuid4()))
        row["recorded_at"] = row.get("recorded_at") or utc_now()
        values = _record_values(row, TELEMETRY_COLUMNS)
        with self._connection() as conn:
            cursor = conn.cursor()
            self._upsert_equipment(
                cursor, row["equipment_id"], row.get("appliance_name") or row["appliance_id"]
            )
            cursor.execute(
                """INSERT INTO ESAI_TELEMETRY
                (TELEMETRY_ID, EQUIPMENT_ID, APPLIANCE_ID, VRMS_V, IRMS_A, APPARENT_POWER_VA,
                 RUNTIME_S, TEMPERATURE_C, VIBRATION_RMS, RELAY_STATE, SOURCE, RECORDED_AT)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                values,
            )
        return row

    @staticmethod
    def _rows_as_dicts(cursor) -> list[dict[str, Any]]:
        names = [str(item[0]).lower() for item in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]

    def recent_telemetry(self, appliance_id: str, limit: int = 100) -> list[dict[str, Any]]:
        safe_limit = _bounded_limit(limit)
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT TELEMETRY_ID, EQUIPMENT_ID, APPLIANCE_ID, VRMS_V, IRMS_A, APPARENT_POWER_VA, "
                "RUNTIME_S, TEMPERATURE_C, VIBRATION_RMS, RELAY_STATE, SOURCE, RECORDED_AT "
                "FROM ESAI_TELEMETRY WHERE APPLIANCE_ID=? "
                f"ORDER BY RECORDED_AT DESC, TELEMETRY_ID DESC FETCH FIRST {safe_limit} ROWS ONLY",
                (appliance_id,),
            )
            return list(reversed(self._rows_as_dicts(cursor)))

    def insert_event(self, event: dict[str, Any]) -> dict[str, Any]:
        row = dict(event)
        row.setdefault("event_id", str(uuid.uuid4()))
        row.setdefault("created_at", utc_now())
        missing = [key for key in ("equipment_id", "appliance_id", "severity") if not row.get(key)]
        if missing:
            raise ValueError("Missing event fields: " + ", ".join(missing))
        with self._connection() as conn:
            conn.cursor().execute(
                """INSERT INTO ESAI_EVENTS
                (EVENT_ID, EQUIPMENT_ID, APPLIANCE_ID, SEVERITY, ANOMALY_SCORE, FEATURE_NAME,
                 OBSERVED_VALUE, BASELINE_MEAN, BASELINE_STD, EXPLANATION, RECOMMENDED_ACTION, CREATED_AT)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                _record_values(row, EVENT_COLUMNS),
            )
        return row

    def list_events(self, appliance_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        safe_limit = _bounded_limit(limit)
        sql = (
            "SELECT EVENT_ID, EQUIPMENT_ID, APPLIANCE_ID, SEVERITY, ANOMALY_SCORE, FEATURE_NAME, "
            "OBSERVED_VALUE, BASELINE_MEAN, BASELINE_STD, EXPLANATION, RECOMMENDED_ACTION, CREATED_AT "
            "FROM ESAI_EVENTS"
        )
        params: tuple[Any, ...] = ()
        if appliance_id:
            sql += " WHERE APPLIANCE_ID=?"
            params = (appliance_id,)
        sql += f" ORDER BY CREATED_AT DESC, EVENT_ID DESC FETCH FIRST {safe_limit} ROWS ONLY"
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return self._rows_as_dicts(cursor)

    def counts(self) -> dict[str, int]:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM ESAI_TELEMETRY")
            telemetry = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM ESAI_EVENTS")
            events = cursor.fetchone()[0]
        return {"telemetry_count": int(telemetry), "event_count": int(events)}


@lru_cache(maxsize=1)
def get_store():
    """Create one storage adapter per API process; avoid schema checks per request."""
    settings = get_settings()
    settings.validate()
    if settings.db_backend == "db2":
        return Db2Store()
    return SQLiteStore()
