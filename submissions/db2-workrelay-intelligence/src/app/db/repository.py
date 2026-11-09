from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.db.connection import Db2ConnectionManager, db_manager
from app.models.incident import (
    ActionStatus,
    Incident,
    IncidentAction,
    IncidentEvent,
    IncidentSeverity,
    IncidentStatus,
)

logger = logging.getLogger("db2_repository")


def format_db2_timestamp(dt: datetime | None) -> str | None:
    """
    Format a datetime object into a standard Db2/ANSI SQL timestamp string.
    Normalizes timezone-aware timestamps to UTC and preserves microsecond precision:
    YYYY-MM-DD HH:MM:SS.ffffff
    """
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")


def parse_db_timestamp(val: Any) -> datetime | None:
    """
    Parse a database timestamp (string from SQLite or datetime from Db2) into a UTC datetime.
    """
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)
    if isinstance(val, str):
        dt = datetime.fromisoformat(val)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return None


class Db2IncidentRepository:
    """
    Enterprise Incident & Audit Repository for IBM Db2.
    Provides parameterized SQL operations, transaction isolation,
    safe row mapping across live Db2 and local fallback, and automatic mapping
    to Pydantic incident domain models.
    """

    def __init__(self, manager: Db2ConnectionManager | None = None) -> None:
        self.mgr = manager or db_manager

    def init_schema(self) -> None:
        """Initialize database schema according to the active mode."""
        if self.mgr.is_db2_active:
            self.init_schema_db2()
        else:
            self.init_schema_sqlite()

    def init_schema_db2(self) -> None:
        """Execute native IBM Db2 DDL schema from schema_db2.sql."""
        schema_file = Path(__file__).parent / "schema_db2.sql"
        if not schema_file.exists():
            raise FileNotFoundError(f"Db2 schema file not found at {schema_file}")

        sql_content = schema_file.read_text(encoding="utf-8")
        statements: list[str] = []
        current_stmt: list[str] = []

        for line in sql_content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("--"):
                continue
            current_stmt.append(line)
            if stripped.endswith(";"):
                stmt = "\n".join(current_stmt).rstrip(";").strip()
                if stmt:
                    statements.append(stmt)
                current_stmt = []

        with self.mgr.get_cursor() as cur:
            for stmt in statements:
                try:
                    cur.execute(stmt)
                except Exception as exc:
                    err_msg = str(exc).lower()
                    # Gracefully handle already existing table/index in Db2 (SQL0601N / -601)
                    if "sql0601n" in err_msg or "already exists" in err_msg or "-601" in err_msg:
                        logger.info("Db2 object already exists: %s", stmt.splitlines()[0])
                    else:
                        logger.warning("Db2 DDL statement error [%s]: %s", stmt.splitlines()[0], exc)

        logger.info("Native IBM Db2 schema initialized from schema_db2.sql.")

    def init_schema_sqlite(self) -> None:
        """Execute SQLite-compatible schema with IF NOT EXISTS for unit tests."""
        schema_sql = """
        CREATE TABLE IF NOT EXISTS incidents (
            id VARCHAR(32) NOT NULL PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            description TEXT NOT NULL,
            service VARCHAR(100) NOT NULL,
            severity VARCHAR(20) NOT NULL,
            status VARCHAR(30) NOT NULL,
            current_step VARCHAR(100) NOT NULL,
            workflow VARCHAR(100),
            resolution TEXT,
            escalation_reason TEXT,
            retry_count INT DEFAULT 0 NOT NULL,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
        );

        CREATE TABLE IF NOT EXISTS incident_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id VARCHAR(32) NOT NULL,
            event VARCHAR(100) NOT NULL,
            status VARCHAR(30) NOT NULL,
            step VARCHAR(100) NOT NULL,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
            FOREIGN KEY (incident_id) REFERENCES incidents (id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS incident_actions (
            action_id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id VARCHAR(32) NOT NULL,
            name VARCHAR(100) NOT NULL,
            description VARCHAR(255),
            status VARCHAR(30) NOT NULL,
            result TEXT,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (incident_id) REFERENCES incidents (id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS incident_knowledge_docs (
            doc_id VARCHAR(64) NOT NULL PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            category VARCHAR(100) NOT NULL,
            service VARCHAR(100) NOT NULL,
            content TEXT NOT NULL,
            resolution_steps TEXT NOT NULL,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents (status);
        CREATE INDEX IF NOT EXISTS idx_incidents_service ON incidents (service);
        CREATE INDEX IF NOT EXISTS idx_incidents_severity ON incidents (severity);
        CREATE INDEX IF NOT EXISTS idx_incidents_created ON incidents (created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_events_incident ON incident_events (incident_id, timestamp);
        CREATE INDEX IF NOT EXISTS idx_actions_incident ON incident_actions (incident_id);
        CREATE INDEX IF NOT EXISTS idx_docs_service ON incident_knowledge_docs (service);
        """
        with self.mgr.get_cursor() as cur:
            for statement in schema_sql.strip().split(";"):
                stmt = statement.strip()
                if stmt:
                    cur.execute(stmt)
        logger.info("SQLite mock repository schema initialized.")

    def create(self, incident: Incident) -> Incident:
        """Persist a new incident and record its creation audit event."""
        created_at_str = format_db2_timestamp(incident.created_at)
        updated_at_str = format_db2_timestamp(incident.updated_at)
        metadata_json = json.dumps(incident.metadata)

        query = """
        INSERT INTO incidents (
            id, title, description, service, severity, status,
            current_step, workflow, resolution, escalation_reason,
            retry_count, metadata, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            incident.id,
            incident.title,
            incident.description,
            incident.service,
            incident.severity.value,
            incident.status.value,
            incident.current_step,
            incident.workflow,
            incident.resolution,
            incident.escalation_reason,
            incident.retry_count,
            metadata_json,
            created_at_str,
            updated_at_str,
        )

        with self.mgr.get_cursor() as cur:
            cur.execute(query, params)

        if not incident.history:
            incident.record_event("INCIDENT_REGISTERED", step="incident_received", details={"service": incident.service})

        for evt in incident.history:
            self._insert_event(incident.id, evt)

        for act in incident.actions:
            self._insert_action(incident.id, act)

        return incident

    def get(self, incident_id: str) -> Incident | None:
        """Retrieve an incident by ID including its history and actions."""
        query = """
        SELECT id, title, description, service, severity, status,
               current_step, workflow, resolution, escalation_reason,
               retry_count, metadata, created_at, updated_at
        FROM incidents
        WHERE id = ?
        """
        with self.mgr.get_cursor() as cur:
            cur.execute(query, (incident_id,))
            raw_row = cur.fetchone()
            row = self.mgr.map_row(cur, raw_row)

        if not row:
            return None

        meta = json.loads(row["metadata"]) if row.get("metadata") else {}

        created_at = parse_db_timestamp(row.get("created_at")) or datetime.now(timezone.utc)
        updated_at = parse_db_timestamp(row.get("updated_at")) or datetime.now(timezone.utc)

        incident = Incident(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            service=row["service"],
            severity=IncidentSeverity(row["severity"]),
            status=IncidentStatus(row["status"]),
            current_step=row["current_step"],
            workflow=row.get("workflow"),
            resolution=row.get("resolution"),
            escalation_reason=row.get("escalation_reason"),
            retry_count=row.get("retry_count", 0),
            metadata=meta,
            created_at=created_at,
            updated_at=updated_at,
        )

        incident.history = self._get_events(incident_id)
        incident.actions = self._get_actions(incident_id)
        return incident

    def list(
        self,
        status: str | None = None,
        severity: str | None = None,
        service: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Incident], int]:
        """List incidents matching criteria with pagination."""
        where_clauses = []
        params: list[Any] = []

        if status and isinstance(status, str):
            where_clauses.append("status = ?")
            params.append(status.upper())
        if severity and isinstance(severity, str):
            where_clauses.append("severity = ?")
            params.append(severity.upper())
        if service and isinstance(service, str):
            where_clauses.append("service = ?")
            params.append(service)

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        count_sql = f"SELECT COUNT(*) as total FROM incidents {where_sql}"

        if self.mgr.is_db2_active:
            # Native IBM Db2 standard pagination syntax
            query_sql = f"""
            SELECT id, title, description, service, severity, status,
                   current_step, workflow, resolution, escalation_reason,
                   retry_count, metadata, created_at, updated_at
            FROM incidents
            {where_sql}
            ORDER BY created_at DESC
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
            """
            paging_params = tuple(params + [offset, limit])
        else:
            # SQLite pagination syntax
            query_sql = f"""
            SELECT id, title, description, service, severity, status,
                   current_step, workflow, resolution, escalation_reason,
                   retry_count, metadata, created_at, updated_at
            FROM incidents
            {where_sql}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """
            paging_params = tuple(params + [limit, offset])

        with self.mgr.get_cursor() as cur:
            cur.execute(count_sql, tuple(params))
            total_raw = cur.fetchone()
            total_mapped = self.mgr.map_row(cur, total_raw)
            total = total_mapped.get("total", 0) if total_mapped else 0

            cur.execute(query_sql, paging_params)
            raw_rows = cur.fetchall()
            rows = [self.mgr.map_row(cur, r) for r in raw_rows if r is not None]

        items = []
        for r in rows:
            meta = json.loads(r["metadata"]) if r.get("metadata") else {}
            c_at = parse_db_timestamp(r.get("created_at")) or datetime.now(timezone.utc)
            u_at = parse_db_timestamp(r.get("updated_at")) or datetime.now(timezone.utc)

            inc = Incident(
                id=r["id"],
                title=r["title"],
                description=r["description"],
                service=r["service"],
                severity=IncidentSeverity(r["severity"]),
                status=IncidentStatus(r["status"]),
                current_step=r["current_step"],
                workflow=r.get("workflow"),
                resolution=r.get("resolution"),
                escalation_reason=r.get("escalation_reason"),
                retry_count=r.get("retry_count", 0),
                metadata=meta,
                created_at=c_at,
                updated_at=u_at,
            )
            items.append(inc)

        return items, total

    def update(self, incident: Incident) -> Incident:
        """Update incident attributes and persist updated actions and history."""
        incident.updated_at = datetime.now(timezone.utc)
        updated_at_str = format_db2_timestamp(incident.updated_at)
        metadata_json = json.dumps(incident.metadata)

        query = """
        UPDATE incidents SET
            title = ?,
            description = ?,
            service = ?,
            severity = ?,
            status = ?,
            current_step = ?,
            workflow = ?,
            resolution = ?,
            escalation_reason = ?,
            retry_count = ?,
            metadata = ?,
            updated_at = ?
        WHERE id = ?
        """
        params = (
            incident.title,
            incident.description,
            incident.service,
            incident.severity.value,
            incident.status.value,
            incident.current_step,
            incident.workflow,
            incident.resolution,
            incident.escalation_reason,
            incident.retry_count,
            metadata_json,
            updated_at_str,
            incident.id,
        )

        with self.mgr.get_cursor() as cur:
            cur.execute(query, params)

        return incident

    def record_event(self, incident_id: str, event: IncidentEvent) -> None:
        """Persist a single lifecycle audit event into Db2."""
        self._insert_event(incident_id, event)

    def record_action(self, incident_id: str, action: IncidentAction) -> None:
        """Persist a single execution/diagnostic action into Db2."""
        self._insert_action(incident_id, action)

    def patch(
        self,
        incident_id: str,
        title: str | None = None,
        description: str | None = None,
        severity: IncidentSeverity | None = None,
        status: IncidentStatus | None = None,
        resolution: str | None = None,
        escalation_reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Incident | None:
        """Partially update an incident and write an audit event."""
        incident = self.get(incident_id)
        if incident is None:
            return None

        event_details: dict[str, Any] = {}
        if title is not None:
            incident.title = title
            event_details["title"] = title
        if description is not None:
            incident.description = description
            event_details["description"] = "updated"
        if severity is not None:
            incident.severity = severity
            event_details["severity"] = severity.value
        if status is not None:
            incident.status = status
            event_details["status"] = status.value
        if resolution is not None:
            incident.resolution = resolution
            event_details["resolution"] = resolution
        if escalation_reason is not None:
            incident.escalation_reason = escalation_reason
            event_details["escalation_reason"] = escalation_reason
        if metadata is not None:
            incident.metadata.update(metadata)
            event_details["metadata"] = "updated"

        evt = incident.record_event(
            "INCIDENT_PATCHED",
            step="incident_patched",
            details=event_details,
        )
        self.record_event(incident.id, evt)
        return self.update(incident)

    def _insert_event(self, incident_id: str, event: IncidentEvent) -> None:
        query = """
        INSERT INTO incident_events (incident_id, event, status, step, details, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        params = (
            incident_id,
            event.event,
            event.status.value,
            event.step,
            json.dumps(event.details),
            format_db2_timestamp(event.timestamp),
        )
        with self.mgr.get_cursor() as cur:
            cur.execute(query, params)

    def _get_events(self, incident_id: str) -> list[IncidentEvent]:
        query = """
        SELECT event, status, step, details, timestamp
        FROM incident_events
        WHERE incident_id = ?
        ORDER BY event_id ASC
        """
        with self.mgr.get_cursor() as cur:
            cur.execute(query, (incident_id,))
            raw_rows = cur.fetchall()
            rows = [self.mgr.map_row(cur, r) for r in raw_rows if r is not None]

        events = []
        for r in rows:
            details = json.loads(r["details"]) if r.get("details") else {}
            ts = parse_db_timestamp(r.get("timestamp")) or datetime.now(timezone.utc)
            events.append(
                IncidentEvent(
                    event=r["event"],
                    status=IncidentStatus(r["status"]),
                    step=r["step"],
                    details=details,
                    timestamp=ts,
                )
            )
        return events

    def _insert_action(self, incident_id: str, action: IncidentAction) -> None:
        query = """
        INSERT INTO incident_actions (incident_id, name, description, status, result, started_at, completed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        s_at = format_db2_timestamp(action.started_at)
        c_at = format_db2_timestamp(action.completed_at)
        params = (
            incident_id,
            action.name,
            action.description,
            action.status.value,
            action.result,
            s_at,
            c_at,
        )
        with self.mgr.get_cursor() as cur:
            cur.execute(query, params)

    def _get_actions(self, incident_id: str) -> list[IncidentAction]:
        query = """
        SELECT name, description, status, result, started_at, completed_at
        FROM incident_actions
        WHERE incident_id = ?
        ORDER BY action_id ASC
        """
        with self.mgr.get_cursor() as cur:
            cur.execute(query, (incident_id,))
            raw_rows = cur.fetchall()
            rows = [self.mgr.map_row(cur, r) for r in raw_rows if r is not None]

        actions = []
        for r in rows:
            s_at = parse_db_timestamp(r.get("started_at"))
            c_at = parse_db_timestamp(r.get("completed_at"))
            actions.append(
                IncidentAction(
                    name=r["name"],
                    description=r.get("description") or "",
                    status=ActionStatus(r["status"]),
                    result=r.get("result"),
                    started_at=s_at,
                    completed_at=c_at,
                )
            )
        return actions
