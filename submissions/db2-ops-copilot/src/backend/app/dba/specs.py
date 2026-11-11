"""DBA tool specifications and parameter validation.

A *tool* is a FIXED, read-only SQL template over the Db2 catalog (``SYSCAT``)
or a monitoring table function (``MON_GET_*``). Tools are the only application
path allowed to touch those schemas: the free-form SQL gate denies them on
purpose, so an LLM can never write catalog/monitoring SQL itself.

Safety invariants (enforced by ``tests/test_dba_specs.py``):

* user-controlled values (schema, table) are ONLY ever bound as ``?`` markers;
* the single value that is interpolated, ``{limit}``, is a validated integer
  (Db2 does not allow parameter markers in ``FETCH FIRST``);
* every template is one ``SELECT``, has no ``;`` and the right marker count;
* system schemas (``SYS*``) cannot be requested as the target schema.

Column/function names follow the IBM Db2 LUW documentation for SYSCAT views
and MON_GET table functions. They have NOT been executed against a live Db2
by this project; see docs/DBA_TOOLS.md for the validation status.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from app.core.config import Settings
from app.core.errors import AppError

ToolKind = Literal["catalog", "monitoring"]

MAX_LIMIT = 100
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_$#@]{0,127}")
_RESERVED_SCHEMA_PREFIXES = ("SYS", "NULLID", "SQLJ")


class ToolParamError(AppError):
    code = "INVALID_TOOL_PARAMS"
    status_code = 422


@dataclass(frozen=True, slots=True)
class ToolParam:
    name: str  # "schema" | "table" | "limit"
    required: bool
    description: str


@dataclass(frozen=True, slots=True)
class ToolSpec:
    id: str
    kind: ToolKind
    title: str
    description: str
    sql: str
    bind: tuple[str, ...] = ()  # ordered names bound to the ``?`` markers
    params: tuple[ToolParam, ...] = field(default_factory=tuple)
    # Which privilege / setup the live Db2 account needs (surfaced in the UI).
    requires: str = "SELECT on SYSCAT catalog views (granted to PUBLIC by default)"

    @property
    def uses_limit(self) -> bool:
        return "{limit}" in self.sql

    def render(self, limit: int) -> str:
        """Substitute the validated integer limit (the only interpolation)."""
        if not isinstance(limit, int) or isinstance(limit, bool):
            raise ToolParamError("limit must be an integer")
        return self.sql.replace("{limit}", str(max(1, min(limit, MAX_LIMIT))))


_SCHEMA = ToolParam("schema", False, "Schema to inspect (default: the application schema).")
_TABLE = ToolParam("table", True, "Table name (unquoted identifier).")
_LIMIT = ToolParam("limit", False, f"Maximum rows to return (1-{MAX_LIMIT}).")

_MON_REQ = (
    "EXECUTE on the MON_GET_* function plus DATAACCESS, DBADM, SQLADM or WLMADM "
    "authority (see database/migrations/005_dba_tools.sql)"
)

TOOLS: tuple[ToolSpec, ...] = (
    # ------------------------------------------------------------- catalog
    ToolSpec(
        id="catalog.tables",
        kind="catalog",
        title="Tables and statistics",
        description="Tables/views of a schema with row count, page count and last RUNSTATS time.",
        sql=(
            "SELECT TABNAME, TYPE, CARD, NPAGES, STATS_TIME, TBSPACE "
            "FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TYPE IN ('T', 'V') "
            "ORDER BY TABNAME FETCH FIRST {limit} ROWS ONLY"
        ),
        bind=("schema",),
        params=(_SCHEMA, _LIMIT),
    ),
    ToolSpec(
        id="catalog.columns",
        kind="catalog",
        title="Columns of a table",
        description="Column names, types, nullability and primary-key position.",
        sql=(
            "SELECT COLNAME, COLNO, TYPENAME, LENGTH, SCALE, NULLS, KEYSEQ "
            "FROM SYSCAT.COLUMNS WHERE TABSCHEMA = ? AND TABNAME = ? "
            "ORDER BY COLNO FETCH FIRST {limit} ROWS ONLY"
        ),
        bind=("schema", "table"),
        params=(_SCHEMA, _TABLE, _LIMIT),
    ),
    ToolSpec(
        id="catalog.indexes",
        kind="catalog",
        title="Indexes of a table",
        description="Indexes with uniqueness, key columns, leaf pages and levels.",
        sql=(
            "SELECT INDNAME, UNIQUERULE, INDEXTYPE, COLNAMES, NLEAF, NLEVELS, "
            "FULLKEYCARD, STATS_TIME FROM SYSCAT.INDEXES "
            "WHERE TABSCHEMA = ? AND TABNAME = ? "
            "ORDER BY INDNAME FETCH FIRST {limit} ROWS ONLY"
        ),
        bind=("schema", "table"),
        params=(_SCHEMA, _TABLE, _LIMIT),
    ),
    ToolSpec(
        id="catalog.constraints",
        kind="catalog",
        title="Keys and constraints",
        description="Primary/unique/foreign/check constraints with their key columns.",
        sql=(
            "SELECT T.CONSTNAME, T.TYPE, K.COLNAME, K.COLSEQ "
            "FROM SYSCAT.TABCONST T LEFT JOIN SYSCAT.KEYCOLUSE K "
            "ON K.CONSTNAME = T.CONSTNAME AND K.TABSCHEMA = T.TABSCHEMA "
            "AND K.TABNAME = T.TABNAME "
            "WHERE T.TABSCHEMA = ? AND T.TABNAME = ? "
            "ORDER BY T.CONSTNAME, K.COLSEQ FETCH FIRST {limit} ROWS ONLY"
        ),
        bind=("schema", "table"),
        params=(_SCHEMA, _TABLE, _LIMIT),
    ),
    ToolSpec(
        id="catalog.stale_statistics",
        kind="catalog",
        title="Statistics freshness",
        description="Tables without collected statistics or with the oldest RUNSTATS.",
        sql=(
            "SELECT TABNAME, CARD, NPAGES, FPAGES, OVERFLOW, STATS_TIME, "
            "CASE WHEN CARD = -1 OR STATS_TIME IS NULL THEN 'NO_STATS' "
            "ELSE 'COLLECTED' END AS STATS_STATUS "
            "FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TYPE = 'T' "
            "ORDER BY STATS_TIME FETCH FIRST {limit} ROWS ONLY"
        ),
        bind=("schema",),
        params=(_SCHEMA, _LIMIT),
    ),
    # ----------------------------------------------------------- monitoring
    ToolSpec(
        id="monitor.table_activity",
        kind="monitoring",
        title="Hot tables (rows read)",
        description="Tables ranked by rows read, with scan counts (MON_GET_TABLE).",
        sql=(
            "SELECT TABSCHEMA, TABNAME, TABLE_SCANS, ROWS_READ, ROWS_INSERTED, "
            "ROWS_UPDATED, ROWS_DELETED, OVERFLOW_ACCESSES "
            "FROM TABLE(MON_GET_TABLE(CAST(? AS VARCHAR(128)), "
            "CAST(NULL AS VARCHAR(128)), -2)) AS T "
            "ORDER BY ROWS_READ DESC FETCH FIRST {limit} ROWS ONLY"
        ),
        bind=("schema",),
        params=(_SCHEMA, _LIMIT),
        requires=_MON_REQ,
    ),
    ToolSpec(
        id="monitor.index_usage",
        kind="monitoring",
        title="Index usage (least used first)",
        description="Index scan counts per index to spot unused indexes (MON_GET_INDEX).",
        sql=(
            "SELECT M.TABNAME, X.INDNAME, M.INDEX_SCANS, M.INDEX_ONLY_SCANS, "
            "M.KEY_UPDATES FROM TABLE(MON_GET_INDEX(CAST(? AS VARCHAR(128)), "
            "CAST(NULL AS VARCHAR(128)), -2)) AS M JOIN SYSCAT.INDEXES X "
            "ON X.TABSCHEMA = M.TABSCHEMA AND X.TABNAME = M.TABNAME "
            "AND X.IID = M.IID ORDER BY M.INDEX_SCANS "
            "FETCH FIRST {limit} ROWS ONLY"
        ),
        bind=("schema",),
        params=(_SCHEMA, _LIMIT),
        requires=_MON_REQ,
    ),
    ToolSpec(
        id="monitor.slow_statements",
        kind="monitoring",
        title="Costly dynamic statements",
        description="Package-cache statements ranked by total activity time (MON_GET_PKG_CACHE_STMT).",
        sql=(
            "SELECT NUM_EXECUTIONS, TOTAL_ACT_TIME, "
            "CASE WHEN NUM_EXECUTIONS > 0 THEN TOTAL_ACT_TIME / NUM_EXECUTIONS "
            "ELSE 0 END AS AVG_ACT_TIME_MS, ROWS_READ, ROWS_RETURNED, "
            "CAST(SUBSTR(STMT_TEXT, 1, 300) AS VARCHAR(300)) AS STMT_TEXT "
            "FROM TABLE(MON_GET_PKG_CACHE_STMT('D', NULL, NULL, -2)) AS T "
            "ORDER BY TOTAL_ACT_TIME DESC FETCH FIRST {limit} ROWS ONLY"
        ),
        params=(_LIMIT,),
        requires=_MON_REQ,
    ),
    ToolSpec(
        id="monitor.connections",
        kind="monitoring",
        title="Connections",
        description="Current connections with CPU, rows read and lock metrics (MON_GET_CONNECTION).",
        sql=(
            "SELECT APPLICATION_HANDLE, APPLICATION_NAME, SESSION_AUTH_ID, "
            "CONNECTION_START_TIME, ROWS_READ, ROWS_RETURNED, TOTAL_CPU_TIME, "
            "LOCK_WAIT_TIME, DEADLOCKS, LOCK_TIMEOUTS "
            "FROM TABLE(MON_GET_CONNECTION(CAST(NULL AS BIGINT), -2)) AS T "
            "ORDER BY TOTAL_CPU_TIME DESC FETCH FIRST {limit} ROWS ONLY"
        ),
        params=(_LIMIT,),
        requires=_MON_REQ,
    ),
    ToolSpec(
        id="monitor.lock_waits",
        kind="monitoring",
        title="Lock waits",
        description="Locks currently in WAIT or CONVERT state (MON_GET_LOCKS).",
        sql=(
            "SELECT APPLICATION_HANDLE, LOCK_OBJECT_TYPE, LOCK_MODE, "
            "LOCK_STATUS, LOCK_NAME FROM TABLE(MON_GET_LOCKS(NULL, -2)) AS T "
            "WHERE LOCK_STATUS IN ('W', 'C') "
            "ORDER BY APPLICATION_HANDLE FETCH FIRST {limit} ROWS ONLY"
        ),
        params=(_LIMIT,),
        requires=_MON_REQ,
    ),
    ToolSpec(
        id="monitor.bufferpool_hit_ratio",
        kind="monitoring",
        title="Buffer pool hit ratio",
        description="Logical vs physical reads and hit ratio per buffer pool (MON_GET_BUFFERPOOL).",
        sql=(
            "SELECT BP_NAME, POOL_DATA_L_READS, POOL_DATA_P_READS, "
            "POOL_INDEX_L_READS, POOL_INDEX_P_READS, "
            "CASE WHEN POOL_DATA_L_READS + POOL_INDEX_L_READS > 0 "
            "THEN 1.0 - DOUBLE(POOL_DATA_P_READS + POOL_INDEX_P_READS) / "
            "DOUBLE(POOL_DATA_L_READS + POOL_INDEX_L_READS) END AS HIT_RATIO "
            "FROM TABLE(MON_GET_BUFFERPOOL(NULL, -2)) AS T "
            "ORDER BY BP_NAME FETCH FIRST {limit} ROWS ONLY"
        ),
        params=(_LIMIT,),
        requires=_MON_REQ,
    ),
)

TOOLS_BY_ID: dict[str, ToolSpec] = {t.id: t for t in TOOLS}


@dataclass(frozen=True, slots=True)
class ResolvedParams:
    """Validated, normalized parameters for one tool run."""

    bound: tuple[Any, ...]  # values for the ``?`` markers, in order
    limit: int
    applied: dict[str, Any]  # echoed back to the caller (non-secret)


def _identifier(name: str, value: Any) -> str:
    if not isinstance(value, str) or not _IDENT_RE.fullmatch(value.strip()):
        raise ToolParamError(
            f"'{name}' must be a plain SQL identifier (letters, digits, _ $ # @).",
            detail={"param": name},
        )
    return value.strip().upper()


def normalize_identifier(name: str, value: Any) -> str:
    """Public: validate + upper-case a plain SQL identifier (raises ToolParamError)."""
    return _identifier(name, value)


def is_reserved_schema(schema: str) -> bool:
    return schema.upper().startswith(_RESERVED_SCHEMA_PREFIXES)


def resolve_params(
    spec: ToolSpec, supplied: dict[str, Any] | None, settings: Settings
) -> ResolvedParams:
    """Validate caller parameters against the tool's declared parameters."""
    supplied = dict(supplied or {})
    declared = {p.name: p for p in spec.params}

    unknown = sorted(set(supplied) - set(declared))
    if unknown:
        raise ToolParamError(
            f"Unknown parameter(s) for {spec.id}: {', '.join(unknown)}",
            detail={"unknown": unknown, "allowed": sorted(declared)},
        )

    applied: dict[str, Any] = {}

    if "schema" in declared:
        raw = supplied.get("schema")
        schema = settings.app_schema if raw in (None, "") else _identifier("schema", raw)
        if schema.startswith(_RESERVED_SCHEMA_PREFIXES):
            raise ToolParamError(
                "System schemas cannot be inspected through DBA tools.",
                detail={"param": "schema"},
            )
        applied["schema"] = schema

    if "table" in declared:
        raw = supplied.get("table")
        if raw in (None, ""):
            raise ToolParamError("'table' is required.", detail={"param": "table"})
        applied["table"] = _identifier("table", raw)

    limit = settings.dba_default_limit
    if "limit" in declared and supplied.get("limit") is not None:
        raw_limit = supplied["limit"]
        if isinstance(raw_limit, bool) or not isinstance(raw_limit, int):
            raise ToolParamError("'limit' must be an integer.", detail={"param": "limit"})
        if not 1 <= raw_limit <= MAX_LIMIT:
            raise ToolParamError(
                f"'limit' must be between 1 and {MAX_LIMIT}.", detail={"param": "limit"}
            )
        limit = raw_limit
    if spec.uses_limit:
        applied["limit"] = limit

    return ResolvedParams(
        bound=tuple(applied[name] for name in spec.bind),
        limit=limit,
        applied=applied,
    )
