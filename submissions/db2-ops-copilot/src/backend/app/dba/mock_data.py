"""Deterministic mock data for every DBA tool and for mock EXPLAIN.

Mirrors database/migrations 001/002/004 (same tables, keys and indexes) so the
offline demo is consistent with what a live Db2 would show. The monitoring
numbers are SYNTHETIC and tell one coherent story for demos: ``DEMO_INCIDENTS``
is read by full table scans because queries filter on ``RESOLVED_AT``, which
has no index (the migration only indexes SERVER_ID and SEVERITY).

Nothing here is produced by Db2; every consumer labels it ``source="mock"``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

# Relative to "now" so the demo story never silently ages: statistics are
# fresh (2 days) for most tables and stale (70 days) for DEMO_INCIDENTS.
_NOW = datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None)
STATS_TS = (_NOW - timedelta(days=2)).isoformat()
STALE_TS = (_NOW - timedelta(days=70)).isoformat()

# (TABNAME, TYPE, CARD, NPAGES, FPAGES, OVERFLOW, STATS_TIME, TBSPACE)
TABLES: list[tuple[Any, ...]] = [
    ("APP_AUDIT", "T", 120, 3, 3, 0, STATS_TS, "USERSPACE1"),
    ("COPILOT_KB", "T", 5, 2, 2, 0, STATS_TS, "USERSPACE1"),
    ("DEMO_INCIDENTS", "T", 4, 1, 1, 0, STALE_TS, "USERSPACE1"),
    ("DEMO_SERVERS", "T", 4, 1, 1, 0, STATS_TS, "USERSPACE1"),
    ("DOCUMENT_METADATA", "T", -1, -1, -1, -1, None, "USERSPACE1"),
    ("QUERY_EXECUTIONS", "T", 40, 2, 2, 0, STATS_TS, "USERSPACE1"),
]

# table -> [(INDNAME, UNIQUERULE, INDEXTYPE, COLNAMES, NLEAF, NLEVELS, FULLKEYCARD)]
INDEXES: dict[str, list[tuple[Any, ...]]] = {
    "DEMO_SERVERS": [("SQL261030090000100", "P", "REG", "+SERVER_ID", 1, 1, 4)],
    "DEMO_INCIDENTS": [
        ("IDX_INCIDENTS_SERVER", "D", "REG", "+SERVER_ID", 1, 1, 3),
        ("IDX_INCIDENTS_SEVERITY", "D", "REG", "+SEVERITY", 1, 1, 4),
        ("SQL261030090000200", "P", "REG", "+INCIDENT_ID", 1, 1, 4),
    ],
    "APP_AUDIT": [
        ("IDX_AUDIT_INTENT", "D", "REG", "+INTENT", 1, 1, 4),
        ("IDX_AUDIT_TS", "D", "REG", "-REQ_TS", 1, 1, 120),
        ("SQL261030090000300", "P", "REG", "+AUDIT_ID", 1, 1, 120),
    ],
    "QUERY_EXECUTIONS": [
        ("IDX_QEXEC_TS", "D", "REG", "-REQ_TS", 1, 1, 40),
        ("SQL261030090000400", "P", "REG", "+EXECUTION_ID", 1, 1, 40),
    ],
    "DOCUMENT_METADATA": [
        ("IDX_DOCS_SOURCE", "D", "REG", "+SOURCE", 1, 1, 3),
        ("SQL261030090000500", "P", "REG", "+DOC_ID", 1, 1, 5),
    ],
}

# table -> [(CONSTNAME, TYPE, COLNAME, COLSEQ)]
CONSTRAINTS: dict[str, list[tuple[Any, ...]]] = {
    "DEMO_SERVERS": [("SQL261030090000101", "P", "SERVER_ID", 1)],
    "DEMO_INCIDENTS": [
        ("SQL261030090000201", "P", "INCIDENT_ID", 1),
        ("SQL261030090000202", "F", "SERVER_ID", 1),
    ],
    "APP_AUDIT": [("SQL261030090000301", "P", "AUDIT_ID", 1)],
    "QUERY_EXECUTIONS": [("SQL261030090000401", "P", "EXECUTION_ID", 1)],
    "DOCUMENT_METADATA": [("SQL261030090000501", "P", "DOC_ID", 1)],
}

# (TABNAME, TABLE_SCANS, ROWS_READ, ROWS_INSERTED, ROWS_UPDATED, ROWS_DELETED, OVERFLOW)
TABLE_ACTIVITY: list[tuple[Any, ...]] = [
    ("DEMO_INCIDENTS", 1840, 7360, 0, 0, 0, 0),
    ("APP_AUDIT", 12, 1440, 120, 0, 0, 0),
    ("QUERY_EXECUTIONS", 9, 360, 40, 0, 0, 0),
    ("DEMO_SERVERS", 31, 124, 0, 0, 0, 0),
    ("COPILOT_KB", 6, 30, 5, 0, 0, 0),
    ("DOCUMENT_METADATA", 2, 10, 5, 0, 0, 0),
]

# (TABNAME, INDNAME, INDEX_SCANS, INDEX_ONLY_SCANS, KEY_UPDATES) — least used first
INDEX_USAGE: list[tuple[Any, ...]] = [
    ("DEMO_INCIDENTS", "IDX_INCIDENTS_SEVERITY", 0, 0, 0),
    ("DOCUMENT_METADATA", "IDX_DOCS_SOURCE", 0, 0, 5),
    ("QUERY_EXECUTIONS", "IDX_QEXEC_TS", 3, 0, 40),
    ("DEMO_INCIDENTS", "IDX_INCIDENTS_SERVER", 17, 2, 0),
    ("APP_AUDIT", "IDX_AUDIT_TS", 112, 0, 120),
]

# (NUM_EXECUTIONS, TOTAL_ACT_TIME, AVG_ACT_TIME_MS, ROWS_READ, ROWS_RETURNED, STMT_TEXT)
SLOW_STATEMENTS: list[tuple[Any, ...]] = [
    (
        1840, 9200, 5, 7360, 920,
        "SELECT INCIDENT_ID, SERVER_ID, SEVERITY FROM APP.DEMO_INCIDENTS "
        "WHERE RESOLVED_AT IS NULL ORDER BY OPENED_AT DESC",
    ),
    (
        120, 840, 7, 1440, 120,
        "SELECT AUDIT_ID, REQ_TS, STATUS FROM APP.APP_AUDIT ORDER BY AUDIT_ID DESC "
        "FETCH FIRST 50 ROWS ONLY",
    ),
    (
        31, 124, 4, 124, 124,
        "SELECT SERVER_ID, HOSTNAME, UPTIME_PCT FROM APP.DEMO_SERVERS "
        "ORDER BY UPTIME_PCT DESC",
    ),
]

# (APPLICATION_HANDLE, APPLICATION_NAME, SESSION_AUTH_ID, CONNECTION_START_TIME,
#  ROWS_READ, ROWS_RETURNED, TOTAL_CPU_TIME, LOCK_WAIT_TIME, DEADLOCKS, LOCK_TIMEOUTS)
CONNECTIONS: list[tuple[Any, ...]] = [
    (101, "python", "DB2RO", "2026-11-10T08:55:12", 9200, 1180, 482000, 0, 0, 0),
    (87, "db2bp", "DB2INST1", "2026-11-10T08:20:41", 310, 42, 91000, 1200, 0, 1),
    (64, "db2jcc_application", "APPUSER", "2026-11-10T07:02:05", 1880, 260, 66000, 0, 0, 0),
]

# (APPLICATION_HANDLE, LOCK_OBJECT_TYPE, LOCK_MODE, LOCK_STATUS, LOCK_NAME)
LOCK_WAITS: list[tuple[Any, ...]] = [
    (87, "ROW", "X", "W", "0200000A0000000000000000052"),
]

# (BP_NAME, POOL_DATA_L_READS, POOL_DATA_P_READS, POOL_INDEX_L_READS, POOL_INDEX_P_READS)
BUFFERPOOLS: list[tuple[Any, ...]] = [
    ("IBMDEFAULTBP", 91400, 2110, 18200, 640),
]


def hit_ratio(row: tuple[Any, ...]) -> float | None:
    logical = row[1] + row[3]
    if logical <= 0:
        return None
    return round(1.0 - (row[2] + row[4]) / logical, 4)
