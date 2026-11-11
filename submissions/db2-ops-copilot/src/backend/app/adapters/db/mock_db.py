"""Mock database adapter — deterministic, offline, in-memory.

Used for development and automated tests. NOT the production implementation:
``ADAPTER_MODE=real`` selects :class:`app.adapters.db.db2_db.Db2DatabaseAdapter`.
"""

from __future__ import annotations

import dataclasses
import re
import threading
import time
from typing import Any, Sequence

from app.adapters.base import (
    AdminResult,
    DbaToolResult,
    ExecutionRecord,
    ExplainObject,
    ExplainOperator,
    ExplainResult,
    ProbeResult,
    QueryResult,
    SchemaColumn,
    SchemaSnapshot,
    SchemaTable,
)
from app.core.clock import utc_now_iso
from app.core.config import Settings
from app.dba import mock_data

_FETCH_RE = re.compile(r"FETCH\s+FIRST\s+(\d+)\s+ROW", re.IGNORECASE)
_TABLE_REF_RE = re.compile(r"\b(?:FROM|JOIN)\s+([A-Za-z_][\w$#@]*(?:\.[A-Za-z_][\w$#@]*)?)", re.IGNORECASE)
_TYPE_RE = re.compile(r"^([A-Z]+)(?:\((\d+)(?:,\s*(\d+))?\))?")


def _tables_in(sql: str) -> list[str]:
    """Unqualified table names referenced by FROM/JOIN, in order, de-duplicated."""
    seen: list[str] = []
    for ref in _TABLE_REF_RE.findall(sql):
        name = ref.split(".")[-1].upper()
        if name not in seen:
            seen.append(name)
    return seen


def _index_columns(colnames: str) -> list[str]:
    """'+A+B' / '-REQ_TS' -> ['A', 'B'] (Db2 COLNAMES format)."""
    return [c for c in re.split(r"[+\-]", colnames) if c]


def _split_type(data_type: str) -> tuple[str, int | None, int | None]:
    match = _TYPE_RE.match(data_type.upper())
    if not match:
        return data_type, None, None
    length = int(match.group(2)) if match.group(2) else None
    scale = int(match.group(3)) if match.group(3) else None
    return match.group(1), length, scale

_SERVER_ROWS: list[list[Any]] = [
    [1, "db2-prod-01", "prod", "platform", 99.95],
    [2, "db2-prod-02", "prod", "platform", 99.87],
    [3, "db2-stage-01", "staging", "data-eng", 98.40],
    [4, "db2-dev-01", "dev", "data-eng", 92.10],
]

_INCIDENT_ROWS: list[list[Any]] = [
    [101, 1, 2, "2026-10-28 09:15:00", "2026-10-28 11:02:00"],
    [102, 3, 3, "2026-10-29 14:40:00", None],
    [103, 4, 1, "2026-10-30 08:05:00", "2026-10-30 08:31:00"],
    [104, 2, 4, "2026-10-30 10:22:00", None],
]


class MockDatabaseAdapter:
    """Simulated read-only Db2 session with canned demo data."""

    probe_name = "database"
    provider_id = "mock"
    mode = "mock"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()
        self._closed = False
        self._lock = threading.Lock()
        self._executions: list[ExecutionRecord] = []
        self.simulated_admin_statements: list[str] = []
        self._next_execution_id = 1
        self._execution_capacity = 500

    # -- lifecycle ------------------------------------------------------
    def ping(self) -> ProbeResult:
        if self._closed:
            return ProbeResult(
                name=self.probe_name,
                status="unavailable",
                mode=self.mode,
                latency_ms=0.0,
                detail="mock adapter closed",
            )
        return ProbeResult(
            name=self.probe_name,
            status="ok",
            mode=self.mode,
            latency_ms=0.0,
            detail="mock Db2 adapter ready (no real connection)",
        )

    # -- explain dry-run (advisory) ------------------------------------------
    def explain(self, sql: str, timeout_ms: int | None = None) -> bool:
        """Offline stand-in for Db2 EXPLAIN: the statement is well-formed by
        construction (it passed the gate), so the mock reports success."""
        if self._closed:
            return False
        return True

    def explain_plan(self, sql: str, timeout_ms: int | None = None) -> ExplainResult:
        """Synthetic, deterministic access plan (clearly labelled ``mock``).

        Heuristic: a table whose WHERE clause mentions an indexed column gets
        IXSCAN + FETCH, otherwise a TBSCAN — enough to demo the workflow
        offline. It is NOT Db2's optimizer output.
        """
        start = time.perf_counter()
        if self._closed:
            return ExplainResult(
                status="UNAVAILABLE",
                source="none",
                hint="mock adapter closed",
            )
        tables = _tables_in(sql)
        where = sql.upper().split(" WHERE ", 1)[1] if " WHERE " in sql.upper() else ""
        cards = {row[0]: row[2] for row in mock_data.TABLES}

        operators: list[ExplainOperator] = []
        objects: list[ExplainObject] = []
        scan_ops: list[ExplainOperator] = []
        next_id = 100
        for table in tables:
            card = max(int(cards.get(table, 10)), 1)
            indexed = next(
                (
                    ix
                    for ix in mock_data.INDEXES.get(table, [])
                    if any(col in where for col in _index_columns(ix[3]))
                ),
                None,
            )
            if indexed is not None:
                scan_ops.append(ExplainOperator(next_id, "IXSCAN", 6.5 + card * 0.001, 2.0, 7000.0))
                scan_ops.append(ExplainOperator(next_id + 1, "FETCH", 7.1 + card * 0.002, 3.0, 9000.0))
                objects.append(ExplainObject(self._settings.app_schema, indexed[0], "INDEX"))
                next_id += 2
            else:
                scan_ops.append(ExplainOperator(next_id, "TBSCAN", 6.8 + card * 0.01, 1.0, 8000.0 + card * 10))
                next_id += 1
            objects.append(ExplainObject(self._settings.app_schema, table, "TABLE"))

        top_cost = sum(op.total_cost or 0.0 for op in scan_ops)
        operators.append(ExplainOperator(1, "RETURN", round(top_cost + 0.1, 4), 0.0, 100.0))
        if " ORDER BY " in sql.upper():
            top_cost += 0.2
            operators.append(ExplainOperator(2, "SORT", round(top_cost, 4), 0.0, 500.0))
        if len(tables) > 1:
            top_cost += 1.5
            operators.append(ExplainOperator(3, "HSJOIN", round(top_cost, 4), 0.0, 2500.0))
        operators.extend(scan_ops)
        for op in scan_ops:
            op.total_cost = round(op.total_cost or 0.0, 4)

        return ExplainResult(
            status="OK",
            source="mock",
            total_cost=round(top_cost + 0.1, 4),
            operators=operators,
            objects=objects,
            warnings=["Synthetic plan produced by the offline mock adapter, not by the Db2 optimizer."],
            latency_ms=(time.perf_counter() - start) * 1000,
        )

    def execute_admin_statement(self, statement: str) -> AdminResult:
        """Simulate an approved maintenance action: NOTHING is executed."""
        if self._closed:
            raise RuntimeError("mock adapter closed")
        with self._lock:
            self.simulated_admin_statements.append(statement)
        return AdminResult(
            status="SIMULATED",
            simulated=True,
            detail="Mock mode: the statement was recorded but not executed against any database.",
        )

    # -- DBA tools (catalog + monitoring) ----------------------------------------
    def run_dba_tool(
        self,
        tool_id: str,
        sql: str,
        params: Sequence[Any],
        limit: int,
    ) -> DbaToolResult:
        """Offline equivalent of every DBA tool (``sql`` is ignored)."""
        if self._closed:
            raise RuntimeError("mock adapter closed")
        start = time.perf_counter()
        schema = str(params[0]) if params else self._settings.app_schema
        table = str(params[1]) if len(params) > 1 else None
        in_app = schema == self._settings.app_schema
        notes = ["Synthetic mock data — not read from a Db2 catalog or monitor."]

        if tool_id == "catalog.tables":
            cols = ["TABNAME", "TYPE", "CARD", "NPAGES", "STATS_TIME", "TBSPACE"]
            rows = [[r[0], r[1], r[2], r[3], r[6], r[7]] for r in mock_data.TABLES] if in_app else []
        elif tool_id == "catalog.columns":
            cols = ["COLNAME", "COLNO", "TYPENAME", "LENGTH", "SCALE", "NULLS", "KEYSEQ"]
            rows = []
            snapshot = self.fetch_schema()
            for t in snapshot.tables if in_app else []:
                if t.name == table:
                    for no, c in enumerate(t.columns):
                        base, length, scale = _split_type(c.data_type)
                        rows.append([c.name, no, base, length, scale, "Y" if c.nullable else "N", None])
        elif tool_id == "catalog.indexes":
            cols = ["INDNAME", "UNIQUERULE", "INDEXTYPE", "COLNAMES", "NLEAF", "NLEVELS", "FULLKEYCARD", "STATS_TIME"]
            rows = [list(r) + [mock_data.STATS_TS] for r in mock_data.INDEXES.get(table or "", [])] if in_app else []
            rows.sort(key=lambda r: r[0])
        elif tool_id == "catalog.constraints":
            cols = ["CONSTNAME", "TYPE", "COLNAME", "COLSEQ"]
            rows = [list(r) for r in mock_data.CONSTRAINTS.get(table or "", [])] if in_app else []
        elif tool_id == "catalog.stale_statistics":
            cols = ["TABNAME", "CARD", "NPAGES", "FPAGES", "OVERFLOW", "STATS_TIME", "STATS_STATUS"]
            rows = []
            for r in mock_data.TABLES if in_app else []:
                status = "NO_STATS" if r[2] == -1 or r[6] is None else "COLLECTED"
                rows.append([r[0], r[2], r[3], r[4], r[5], r[6], status])
            rows.sort(key=lambda r: (r[5] is not None, r[5] or ""))
        elif tool_id == "monitor.table_activity":
            cols = ["TABSCHEMA", "TABNAME", "TABLE_SCANS", "ROWS_READ", "ROWS_INSERTED", "ROWS_UPDATED", "ROWS_DELETED", "OVERFLOW_ACCESSES"]
            rows = [[schema, *r] for r in sorted(mock_data.TABLE_ACTIVITY, key=lambda r: -r[2])] if in_app else []
        elif tool_id == "monitor.index_usage":
            cols = ["TABNAME", "INDNAME", "INDEX_SCANS", "INDEX_ONLY_SCANS", "KEY_UPDATES"]
            rows = [list(r) for r in mock_data.INDEX_USAGE] if in_app else []
        elif tool_id == "monitor.slow_statements":
            cols = ["NUM_EXECUTIONS", "TOTAL_ACT_TIME", "AVG_ACT_TIME_MS", "ROWS_READ", "ROWS_RETURNED", "STMT_TEXT"]
            rows = [list(r) for r in mock_data.SLOW_STATEMENTS]
        elif tool_id == "monitor.connections":
            cols = ["APPLICATION_HANDLE", "APPLICATION_NAME", "SESSION_AUTH_ID", "CONNECTION_START_TIME", "ROWS_READ", "ROWS_RETURNED", "TOTAL_CPU_TIME", "LOCK_WAIT_TIME", "DEADLOCKS", "LOCK_TIMEOUTS"]
            rows = [list(r) for r in sorted(mock_data.CONNECTIONS, key=lambda r: -r[6])]
        elif tool_id == "monitor.lock_waits":
            cols = ["APPLICATION_HANDLE", "LOCK_OBJECT_TYPE", "LOCK_MODE", "LOCK_STATUS", "LOCK_NAME"]
            rows = [list(r) for r in mock_data.LOCK_WAITS]
        elif tool_id == "monitor.bufferpool_hit_ratio":
            cols = ["BP_NAME", "POOL_DATA_L_READS", "POOL_DATA_P_READS", "POOL_INDEX_L_READS", "POOL_INDEX_P_READS", "HIT_RATIO"]
            rows = [list(r) + [mock_data.hit_ratio(r)] for r in mock_data.BUFFERPOOLS]
        else:
            raise ValueError(f"unknown DBA tool: {tool_id}")

        truncated = len(rows) > limit
        return DbaToolResult(
            tool_id=tool_id,
            source="mock",
            columns=cols,
            rows=rows[:limit],
            truncated=truncated,
            latency_ms=(time.perf_counter() - start) * 1000,
            notes=notes,
        )

    # -- execution history (APP.QUERY_EXECUTIONS stand-in) ----------------
    def record_execution(self, record: ExecutionRecord) -> int:
        """Append an execution-history row (in-memory for the mock)."""
        if self._closed:
            raise RuntimeError("mock adapter closed")
        with self._lock:
            record.id = self._next_execution_id
            self._next_execution_id += 1
            if not record.timestamp:
                record.timestamp = utc_now_iso()
            # bounded history: keep the most recent rows only
            self._executions.append(dataclasses.replace(record))
            if len(self._executions) > self._execution_capacity:
                self._executions = self._executions[-self._execution_capacity :]
            return record.id

    def list_executions(self, limit: int = 20) -> list[ExecutionRecord]:
        with self._lock:
            snapshot = list(self._executions)
        snapshot.reverse()  # newest first
        return [dataclasses.replace(r) for r in snapshot[: max(limit, 0)]]

    def close(self) -> None:
        self._closed = True

    # -- queries --------------------------------------------------------
    def execute_readonly(
        self,
        sql: str,
        params: Sequence[Any] | None = None,
        timeout_ms: int | None = None,
    ) -> QueryResult:
        if self._closed:
            raise RuntimeError("mock adapter closed")
        start = time.perf_counter()
        upper = sql.upper()
        # Defense in depth: even the mock refuses anything that is not a read.
        first_word = sql.lstrip()[:6].upper()
        if not first_word.startswith(("SELECT", "WITH")):
            raise ValueError("mock database only executes SELECT/WITH statements")
        if params is not None and not isinstance(params, (list, tuple)):
            raise ValueError("params must be a positional sequence (qmark binding)")

        if "DEMO_INCIDENTS" in upper:
            columns = ["INCIDENT_ID", "SERVER_ID", "SEVERITY", "OPENED_AT", "RESOLVED_AT"]
            rows = [list(r) for r in _INCIDENT_ROWS]
        elif "DEMO_SERVERS" in upper:
            columns = ["SERVER_ID", "HOSTNAME", "ENVIRONMENT", "OWNER_TEAM", "UPTIME_PCT"]
            rows = [list(r) for r in _SERVER_ROWS]
        elif "COUNT(" in upper:
            columns = ["VALUE"]
            rows = [[len(_SERVER_ROWS)]]
        else:
            columns = ["RESULT"]
            rows = [["mock-row-1"], ["mock-row-2"]]

        # Apply FETCH FIRST n ROWS ONLY if present (mirrors Db2 behaviour).
        match = _FETCH_RE.search(sql)
        truncated = False
        if match:
            cap = int(match.group(1))
            if len(rows) > cap:
                rows = rows[:cap]
                truncated = True

        return QueryResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            truncated=truncated,
            latency_ms=(time.perf_counter() - start) * 1000,
        )

    def fetch_schema(self) -> SchemaSnapshot:
        """Mirror of database/migrations (001 + 004) for offline dev/tests."""
        return SchemaSnapshot(
            source="mock",
            tables=[
                SchemaTable(
                    name="DEMO_SERVERS",
                    schema_name="APP",
                    columns=[
                        SchemaColumn("SERVER_ID", "INTEGER", False),
                        SchemaColumn("HOSTNAME", "VARCHAR(64)"),
                        SchemaColumn("ENVIRONMENT", "VARCHAR(16)"),
                        SchemaColumn("OWNER_TEAM", "VARCHAR(32)"),
                        SchemaColumn("UPTIME_PCT", "DECIMAL(5,2)"),
                    ],
                ),
                SchemaTable(
                    name="DEMO_INCIDENTS",
                    schema_name="APP",
                    columns=[
                        SchemaColumn("INCIDENT_ID", "INTEGER", False),
                        SchemaColumn("SERVER_ID", "INTEGER"),
                        SchemaColumn("SEVERITY", "INTEGER"),
                        SchemaColumn("OPENED_AT", "TIMESTAMP"),
                        SchemaColumn("RESOLVED_AT", "TIMESTAMP"),
                    ],
                ),
                SchemaTable(
                    # DB2VS-managed layout — exact DDL from langchain-db2's
                    # _create_table (verified against package source).
                    name="COPILOT_KB",
                    schema_name="APP",
                    columns=[
                        SchemaColumn("ID", "CHAR(16)", False),
                        SchemaColumn("TEXT", "CLOB"),
                        SchemaColumn("METADATA", "BLOB"),
                        SchemaColumn("EMBEDDING", "VECTOR(768, FLOAT32)", False),
                    ],
                ),
                SchemaTable(
                    name="APP_AUDIT",
                    schema_name="APP",
                    columns=[
                        SchemaColumn("AUDIT_ID", "BIGINT", False),
                        SchemaColumn("REQ_TS", "TIMESTAMP"),
                        SchemaColumn("ACTOR_TYPE", "VARCHAR(32)"),
                        SchemaColumn("SESSION_ID", "VARCHAR(64)"),
                        SchemaColumn("CLIENT_REQ_ID", "VARCHAR(64)"),
                        SchemaColumn("OPERATION", "VARCHAR(32)"),
                        SchemaColumn("INTENT", "VARCHAR(16)"),
                        SchemaColumn("QUESTION", "CLOB"),
                        SchemaColumn("SQL_TEXT", "CLOB"),
                        SchemaColumn("STATUS", "VARCHAR(24)"),
                        SchemaColumn("LATENCY_MS", "INTEGER"),
                        SchemaColumn("METADATA", "CLOB"),
                    ],
                ),
                SchemaTable(
                    name="DOCUMENT_METADATA",
                    schema_name="APP",
                    columns=[
                        SchemaColumn("DOC_ID", "VARCHAR(64)", False),
                        SchemaColumn("SOURCE", "VARCHAR(255)"),
                        SchemaColumn("TITLE", "VARCHAR(255)"),
                        SchemaColumn("URI", "VARCHAR(1024)"),
                        SchemaColumn("CHUNK_INDEX", "INTEGER"),
                        SchemaColumn("CHUNK_COUNT", "INTEGER"),
                        SchemaColumn("CHAR_COUNT", "INTEGER"),
                        SchemaColumn("CONTENT_HASH", "VARCHAR(64)"),
                        SchemaColumn("METADATA", "CLOB"),
                        SchemaColumn("CREATED_AT", "TIMESTAMP"),
                        SchemaColumn("UPDATED_AT", "TIMESTAMP"),
                    ],
                ),
                SchemaTable(
                    name="QUERY_EXECUTIONS",
                    schema_name="APP",
                    columns=[
                        SchemaColumn("EXECUTION_ID", "BIGINT", False),
                        SchemaColumn("REQ_TS", "TIMESTAMP"),
                        SchemaColumn("CLIENT_REQ_ID", "VARCHAR(64)"),
                        SchemaColumn("SQL_TEXT", "CLOB"),
                        SchemaColumn("VALIDATION_STATUS", "VARCHAR(16)"),
                        SchemaColumn("EXPLAIN_STATUS", "VARCHAR(24)"),
                        SchemaColumn("EXECUTION_STATUS", "VARCHAR(24)"),
                        SchemaColumn("ROW_COUNT", "INTEGER"),
                        SchemaColumn("TRUNCATED", "CHAR(1)"),
                        SchemaColumn("LATENCY_MS", "INTEGER"),
                        SchemaColumn("SQLSTATE_CODE", "CHAR(5)"),
                        SchemaColumn("METADATA", "CLOB"),
                    ],
                ),
            ],
        )
