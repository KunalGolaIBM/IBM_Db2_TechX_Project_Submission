"""IBM Db2 persistence layer for ShipSafe AI.

The repository speaks DB-API 2.0. In production it uses `ibm_db_dbi` against a
real IBM Db2 server (autocommit off, explicit transactions); the `sqlite`
backend exists only so unit tests run without a database. There is no silent
fallback: if Db2 is selected and unreachable after retries, the error surfaces.

Every statement uses `?` parameter markers. The only identifiers ever placed in
SQL text are the validated schema name and integer row limits.
"""

import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence

from ..config import Db2Config
from ..models import Assessment, Finding, ToolRun
from .schema import DB2_INDEXES, DB2_TABLES, DB2_VIEWS, SQLITE_DDL

log = logging.getLogger("shipsafe.db2")

SEVERITY_ORDER_SQL = (
    "CASE SEVERITY WHEN 'critical' THEN 1 WHEN 'high' THEN 2 "
    "WHEN 'medium' THEN 3 WHEN 'low' THEN 4 ELSE 5 END"
)


def connect_db2(config: Db2Config, retries: int = 3, base_delay: float = 0.5):
    """Open an ibm_db_dbi connection with exponential backoff on transient failures."""
    import ibm_db_dbi

    last: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            conn = ibm_db_dbi.connect(config.connection_string(), "", "")
            conn.set_autocommit(False)
            return conn
        except Exception as exc:  # network / server not ready
            last = exc
            log.warning("db2 connect attempt %s/%s failed: %s", attempt, retries, _safe_err(exc))
            if attempt < retries:
                time.sleep(base_delay * (2 ** (attempt - 1)))
    raise ConnectionError(f"Could not connect to IBM Db2 at {config.host}:{config.port}/{config.database}: {_safe_err(last)}")


def _safe_err(exc: Optional[Exception]) -> str:
    """Error text with any PWD= value removed."""
    import re

    return re.sub(r"(?i)pwd=[^;]*", "PWD=***", str(exc))[:400]


class Db2Repository:
    """Persistence adapter for assessments, findings, policies, tokens and audit events."""

    def __init__(
        self,
        config: Optional[Db2Config] = None,
        backend: str = "db2",
        sqlite_path: str = ":memory:",
        conn: Any = None,
        init_schema: bool = True,
        retries: int = 3,
    ):
        self.config = config or Db2Config.from_env()
        self.backend = backend
        if backend == "db2":
            self.conn = conn if conn is not None else connect_db2(self.config, retries=retries)
            self.schema = self.config.schema
            if not self.schema.replace("_", "").isalnum():
                raise ValueError(f"Invalid DB2_SCHEMA identifier: {self.schema!r}")
            self._execute(f"SET SCHEMA {self.schema}").close()
        elif backend == "sqlite":
            import sqlite3

            self.conn = conn if conn is not None else sqlite3.connect(sqlite_path, check_same_thread=False)
            self.schema = None
        else:
            raise ValueError(f"Unknown backend '{backend}'. Use 'db2' or 'sqlite'.")
        if init_schema:
            self.initialize_schema()

    @property
    def is_db2(self) -> bool:
        return self.backend == "db2"

    # ------------------------------------------------------------------ helpers
    def _execute(self, sql: str, params: Sequence[Any] = ()) -> Any:
        cur = self.conn.cursor()
        cur.execute(sql, tuple(params))
        return cur

    def _query(self, sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
        cur = self._execute(sql, params)
        cols = [d[0].upper() for d in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        cur.close()
        return rows

    def _limit(self, n: int, offset: int = 0) -> str:
        n, offset = int(n), int(offset)  # integers only, never user text
        if self.is_db2:
            return (f" OFFSET {offset} ROWS" if offset else "") + f" FETCH FIRST {n} ROWS ONLY"
        return f" LIMIT {n}" + (f" OFFSET {offset}" if offset else "")

    def _commit(self, commit: bool) -> None:
        if commit:
            self.conn.commit()

    def ping(self) -> float:
        """Round-trip a trivial query; returns latency in milliseconds."""
        t0 = time.perf_counter()
        sql = "SELECT 1 FROM SYSIBM.SYSDUMMY1" if self.is_db2 else "SELECT 1"
        self._execute(sql).close()
        return round((time.perf_counter() - t0) * 1000, 2)

    def rollback(self) -> None:
        try:
            self.conn.rollback()
        except Exception:
            pass

    def _table_exists(self, name: str) -> bool:
        return bool(self._query(
            "SELECT 1 AS X FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TABNAME = ?", (self.schema, name)))

    def _index_exists(self, name: str) -> bool:
        return bool(self._query(
            "SELECT 1 AS X FROM SYSCAT.INDEXES WHERE INDSCHEMA = ? AND INDNAME = ?", (self.schema, name)))

    # ------------------------------------------------------------------- schema
    def initialize_schema(self) -> List[str]:
        """Create tables, indexes and views idempotently. Returns created objects."""
        created: List[str] = []
        if not self.is_db2:
            self.conn.executescript(SQLITE_DDL)
            self.conn.commit()
            return created
        try:
            for name, ddl in DB2_TABLES.items():
                if not self._table_exists(name):
                    self._execute(ddl).close()
                    created.append(name)
            for name, ddl in DB2_INDEXES.items():
                if not self._index_exists(name):
                    self._execute(ddl).close()
                    created.append(name)
            for ddl in DB2_VIEWS.values():
                self._execute(ddl).close()
            self.conn.commit()
        except Exception:
            self.rollback()
            raise
        return created

    def check_connection(self) -> Dict[str, Any]:
        """Diagnostic probe used by `shipsafe doctor` and the readiness endpoint."""
        latency = self.ping()
        if not self.is_db2:
            return {"connected": True, "engine": "SQLite (unit-test backend)", "latency_ms": latency}
        row = self._query(
            "SELECT SERVICE_LEVEL, CURRENT SERVER AS DB_NAME, CURRENT SCHEMA AS SCHEMA_NAME "
            "FROM SYSIBMADM.ENV_INST_INFO"
        )[0]
        counts = self._query(
            "SELECT TYPE, COUNT(*) AS N FROM SYSCAT.TABLES WHERE TABSCHEMA = ? GROUP BY TYPE", (self.schema,))
        by_type = {str(r["TYPE"]).strip(): int(r["N"]) for r in counts}
        return {
            "connected": True,
            "engine": "IBM Db2",
            "version": str(row["SERVICE_LEVEL"]).strip(),
            "database": str(row["DB_NAME"]).strip(),
            "schema": str(row["SCHEMA_NAME"]).strip(),
            "host": self.config.host,
            "port": self.config.port,
            "tables_in_schema": by_type.get("T", 0),
            "views_in_schema": by_type.get("V", 0),
            "latency_ms": latency,
        }

    # ----------------------------------------------------------------- projects
    def save_project(self, project_id: str, repo_root_hash: str, name: str,
                     default_branch: str = "main", commit: bool = True) -> None:
        now = int(time.time() * 1000)
        if self.is_db2:
            sql = """
            MERGE INTO PROJECTS T
            USING (VALUES (CAST(? AS VARCHAR(96)), CAST(? AS VARCHAR(64)), CAST(? AS VARCHAR(128)),
                           CAST(? AS VARCHAR(64)), CAST(? AS BIGINT)))
                  AS S(PROJECT_ID, REPO_ROOT_HASH, NAME, DEFAULT_BRANCH, CREATED_AT)
            ON T.PROJECT_ID = S.PROJECT_ID
            WHEN MATCHED THEN UPDATE SET NAME = S.NAME, DEFAULT_BRANCH = S.DEFAULT_BRANCH
            WHEN NOT MATCHED THEN INSERT (PROJECT_ID, REPO_ROOT_HASH, NAME, DEFAULT_BRANCH, CREATED_AT)
                 VALUES (S.PROJECT_ID, S.REPO_ROOT_HASH, S.NAME, S.DEFAULT_BRANCH, S.CREATED_AT)
            """
        else:
            sql = """
            INSERT INTO PROJECTS (PROJECT_ID, REPO_ROOT_HASH, NAME, DEFAULT_BRANCH, CREATED_AT)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(PROJECT_ID) DO UPDATE SET NAME = excluded.NAME, DEFAULT_BRANCH = excluded.DEFAULT_BRANCH
            """
        self._execute(sql, (project_id, repo_root_hash, name, default_branch, now)).close()
        self._commit(commit)

    def save_dependencies(self, project_id: str, deps: List[Dict[str, str]], commit: bool = True) -> None:
        """Replace the dependency inventory (SBOM) for a project."""
        self._execute("DELETE FROM DEPENDENCIES WHERE PROJECT_ID = ?", (project_id,)).close()
        sql = ("INSERT INTO DEPENDENCIES (DEPENDENCY_ID, PROJECT_ID, PACKAGE_NAME, VERSION, MANIFEST_PATH, ECOSYSTEM) "
               "VALUES (?, ?, ?, ?, ?, ?)")
        cur = self.conn.cursor()
        for i, d in enumerate(deps):
            cur.execute(sql, (f"{project_id[:80]}_{i}", project_id, d["name"][:128], d["version"][:64],
                              d.get("manifest"), d.get("ecosystem", "pypi")))
        cur.close()
        self._commit(commit)

    # -------------------------------------------------------------- assessments
    def save_assessment(self, a: Assessment, commit: bool = True) -> None:
        sql = """
        INSERT INTO ASSESSMENTS (
            ASSESSMENT_ID, PROJECT_ID, COMMIT_SHA, BASE_SHA, PROFILE, STATUS, GATE_REASON,
            STARTED_AT, FINISHED_AT, FINDINGS_COUNT, CRITICAL_COUNT, HIGH_COUNT, MEDIUM_COUNT, LOW_COUNT
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        self._execute(sql, (
            a.assessment_id, a.project_id, a.commit_sha, a.base_sha, a.profile, a.status,
            a.gate_reason[:512], a.started_at, a.finished_at, a.findings_count,
            a.critical_count, a.high_count, a.medium_count, a.low_count,
        )).close()
        self._commit(commit)

    def save_tool_runs(self, tool_runs: List[ToolRun], commit: bool = True) -> None:
        sql = ("INSERT INTO TOOL_RUNS (TOOL_RUN_ID, ASSESSMENT_ID, TOOL_NAME, VERSION, EXIT_CODE, DURATION_MS, STATUS, MESSAGE) "
               "VALUES (?, ?, ?, ?, ?, ?, ?, ?)")
        cur = self.conn.cursor()
        for tr in tool_runs:
            cur.execute(sql, (tr.tool_run_id, tr.assessment_id, tr.tool_name, (tr.version or "-")[:64],
                              tr.exit_code, tr.duration_ms, tr.status, (tr.message or "")[:1024]))
        cur.close()
        self._commit(commit)

    def save_findings(self, findings: List[Finding], commit: bool = True) -> None:
        sql = """
        INSERT INTO FINDINGS (
            FINDING_ID, ASSESSMENT_ID, FINGERPRINT, SOURCE_TOOL, RULE_ID, CATEGORY, SEVERITY, CONFIDENCE,
            FILE_PATH, LINE_START, LINE_END, TITLE, DESCRIPTION, EVIDENCE_JSON, REMEDIATION, STATUS, REFERENCES_JSON
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        cur = self.conn.cursor()
        for f in findings:
            cur.execute(sql, (
                f.finding_id, f.assessment_id, f.fingerprint, f.source_tool[:64], f.rule_id[:64], f.category,
                f.severity, f.confidence, (f.file_path or None) and f.file_path[:512], f.line_start, f.line_end,
                f.title[:256], (f.description or "")[:2048], json.dumps(f.evidence), (f.remediation or "")[:2048],
                f.status, json.dumps(f.references),
            ))
        cur.close()
        self._commit(commit)

    def save_assessment_bundle(self, *, project: Dict[str, str], dependencies: List[Dict[str, str]],
                               assessment: Assessment, tool_runs: List[ToolRun], findings: List[Finding]) -> None:
        """Persist one complete assessment atomically: all rows commit together or none do."""
        try:
            self.save_project(project["project_id"], project["repo_root_hash"], project["name"],
                              project.get("default_branch", "main"), commit=False)
            self.save_dependencies(project["project_id"], dependencies, commit=False)
            self.save_assessment(assessment, commit=False)
            self.save_tool_runs(tool_runs, commit=False)
            self.save_findings(findings, commit=False)
            self.conn.commit()
        except Exception:
            self.rollback()
            raise

    # ------------------------------------------------------------------ queries
    def get_assessment(self, assessment_id: str) -> Optional[Dict[str, Any]]:
        rows = self._query(
            "SELECT A.*, P.NAME AS PROJECT_NAME FROM ASSESSMENTS A JOIN PROJECTS P ON P.PROJECT_ID = A.PROJECT_ID "
            "WHERE A.ASSESSMENT_ID = ?", (assessment_id,))
        return rows[0] if rows else None

    def list_assessments(self, limit: int = 25, offset: int = 0, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        sql = ("SELECT A.ASSESSMENT_ID, A.PROJECT_ID, P.NAME AS PROJECT_NAME, A.PROFILE, A.STATUS, A.GATE_REASON, "
               "A.STARTED_AT, A.FINISHED_AT, A.FINDINGS_COUNT, A.CRITICAL_COUNT, A.HIGH_COUNT, A.MEDIUM_COUNT, A.LOW_COUNT, "
               "A.COMMIT_SHA FROM ASSESSMENTS A JOIN PROJECTS P ON P.PROJECT_ID = A.PROJECT_ID")
        params: List[Any] = []
        if project_id:
            sql += " WHERE A.PROJECT_ID = ?"
            params.append(project_id)
        sql += " ORDER BY A.STARTED_AT DESC" + self._limit(limit, offset)
        return self._query(sql, params)

    @staticmethod
    def _decode_finding(r: Dict[str, Any]) -> Dict[str, Any]:
        r["EVIDENCE"] = json.loads(r.pop("EVIDENCE_JSON", None) or "{}")
        r["REFERENCES"] = json.loads(r.pop("REFERENCES_JSON", None) or "[]")
        return r

    def get_findings(self, assessment_id: str) -> List[Dict[str, Any]]:
        rows = self._query(
            f"SELECT * FROM FINDINGS WHERE ASSESSMENT_ID = ? ORDER BY {SEVERITY_ORDER_SQL}, FILE_PATH, LINE_START",
            (assessment_id,))
        return [self._decode_finding(r) for r in rows]

    def get_finding(self, finding_id: str) -> Optional[Dict[str, Any]]:
        rows = self._query("SELECT * FROM FINDINGS WHERE FINDING_ID = ?", (finding_id,))
        return self._decode_finding(rows[0]) if rows else None

    def get_tool_runs(self, assessment_id: str) -> List[Dict[str, Any]]:
        return self._query("SELECT * FROM TOOL_RUNS WHERE ASSESSMENT_ID = ? ORDER BY TOOL_NAME", (assessment_id,))

    def get_dependencies(self, project_id: str) -> List[Dict[str, Any]]:
        return self._query(
            "SELECT PACKAGE_NAME, VERSION, MANIFEST_PATH, ECOSYSTEM FROM DEPENDENCIES WHERE PROJECT_ID = ? "
            "ORDER BY PACKAGE_NAME", (project_id,))

    def get_assessment_history(self, limit: int = 10, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Recent assessments with the risk delta computed in Db2 (V_RISK_TREND)."""
        if self.is_db2:
            sql = ("SELECT PROJECT_ID, PROJECT_NAME, ASSESSMENT_ID, STATUS, STARTED_AT, CRITICAL_COUNT, HIGH_COUNT, "
                   "MEDIUM_COUNT, LOW_COUNT, RISK_SCORE, RISK_DELTA FROM V_RISK_TREND")
            where = " WHERE PROJECT_ID = ?"
        else:
            sql = ("SELECT A.PROJECT_ID, P.NAME AS PROJECT_NAME, A.ASSESSMENT_ID, A.STATUS, A.STARTED_AT, A.CRITICAL_COUNT, "
                   "A.HIGH_COUNT, A.MEDIUM_COUNT, A.LOW_COUNT, "
                   "(A.CRITICAL_COUNT*10 + A.HIGH_COUNT*5 + A.MEDIUM_COUNT*2 + A.LOW_COUNT) AS RISK_SCORE, "
                   "NULL AS RISK_DELTA FROM ASSESSMENTS A JOIN PROJECTS P ON P.PROJECT_ID = A.PROJECT_ID")
            where = " WHERE A.PROJECT_ID = ?"
        params: List[Any] = []
        if project_id:
            sql += where
            params.append(project_id)
        sql += " ORDER BY STARTED_AT DESC" + self._limit(limit)
        return self._query(sql, params)

    def project_posture(self) -> List[Dict[str, Any]]:
        """Latest assessment per project (Db2 view V_PROJECT_POSTURE)."""
        if self.is_db2:
            return self._query("SELECT * FROM V_PROJECT_POSTURE ORDER BY RISK_SCORE DESC, STARTED_AT DESC")
        return self._query(
            "SELECT A.PROJECT_ID, P.NAME AS PROJECT_NAME, A.ASSESSMENT_ID, A.STATUS, A.STARTED_AT, A.CRITICAL_COUNT, "
            "A.HIGH_COUNT, A.MEDIUM_COUNT, A.LOW_COUNT, "
            "(A.CRITICAL_COUNT*10 + A.HIGH_COUNT*5 + A.MEDIUM_COUNT*2 + A.LOW_COUNT) AS RISK_SCORE, NULL AS RISK_DELTA "
            "FROM ASSESSMENTS A JOIN PROJECTS P ON P.PROJECT_ID = A.PROJECT_ID "
            "WHERE A.STARTED_AT = (SELECT MAX(B.STARTED_AT) FROM ASSESSMENTS B WHERE B.PROJECT_ID = A.PROJECT_ID) "
            "ORDER BY RISK_SCORE DESC")

    def severity_breakdown(self) -> List[Dict[str, Any]]:
        """Findings by category and severity across all assessments."""
        return self._query(
            "SELECT CATEGORY, SEVERITY, COUNT(*) AS TOTAL, COUNT(DISTINCT FINGERPRINT) AS UNIQUE_ISSUES "
            f"FROM FINDINGS GROUP BY CATEGORY, SEVERITY ORDER BY CATEGORY, MIN({SEVERITY_ORDER_SQL})")

    def overview_stats(self) -> Dict[str, Any]:
        """Single-round-trip KPIs for the dashboard."""
        row = self._query(
            "SELECT (SELECT COUNT(*) FROM PROJECTS) AS PROJECTS, "
            "(SELECT COUNT(*) FROM ASSESSMENTS) AS ASSESSMENTS, "
            "(SELECT COUNT(*) FROM ASSESSMENTS WHERE STATUS = 'BLOCKED') AS BLOCKED_RUNS, "
            "(SELECT COUNT(*) FROM FINDINGS) AS FINDINGS, "
            "(SELECT COUNT(DISTINCT FINGERPRINT) FROM FINDINGS) AS UNIQUE_ISSUES, "
            "(SELECT COUNT(*) FROM KNOWLEDGE_DOCS) AS POLICY_DOCS"
            + (" FROM SYSIBM.SYSDUMMY1" if self.is_db2 else ""))[0]
        posture = self.project_posture()
        stats = {k.lower(): int(v or 0) for k, v in row.items()}
        stats["open_critical"] = sum(int(p["CRITICAL_COUNT"] or 0) for p in posture)
        stats["open_high"] = sum(int(p["HIGH_COUNT"] or 0) for p in posture)
        stats["projects_blocked"] = sum(1 for p in posture if p["STATUS"] == "BLOCKED")
        return stats

    def compare_assessments(self, previous_id: str, current_id: str) -> Dict[str, Any]:
        """Regression diff by stable fingerprint; persists the delta to ASSESSMENT_DIFFS."""
        prev = {f["FINGERPRINT"]: f for f in self.get_findings(previous_id)}
        curr = {f["FINGERPRINT"]: f for f in self.get_findings(current_id)}
        new_items = [curr[fp] for fp in curr.keys() - prev.keys()]
        resolved_items = [prev[fp] for fp in prev.keys() - curr.keys()]
        unchanged_items = [curr[fp] for fp in curr.keys() & prev.keys()]
        try:
            self._execute("DELETE FROM ASSESSMENT_DIFFS WHERE CURRENT_ID = ? AND PREVIOUS_ID = ?",
                          (current_id, previous_id)).close()
            sql = ("INSERT INTO ASSESSMENT_DIFFS (DIFF_ID, CURRENT_ID, PREVIOUS_ID, FINDING_FINGERPRINT, CHANGE_TYPE, TITLE, SEVERITY) "
                   "VALUES (?, ?, ?, ?, ?, ?, ?)")
            cur = self.conn.cursor()
            for change, items in (("new", new_items), ("resolved", resolved_items), ("unchanged", unchanged_items)):
                for it in items:
                    cur.execute(sql, (f"{current_id}:{previous_id}:{it['FINGERPRINT'][:16]}", current_id, previous_id,
                                      it["FINGERPRINT"], change, it["TITLE"], it["SEVERITY"]))
            cur.close()
            self.conn.commit()
        except Exception:
            self.rollback()
            raise
        return {
            "previous_id": previous_id, "current_id": current_id,
            "new_count": len(new_items), "resolved_count": len(resolved_items), "unchanged_count": len(unchanged_items),
            "new_findings": new_items, "resolved_findings": resolved_items, "unchanged_findings": unchanged_items,
        }

    # ---------------------------------------------------------------- knowledge
    def save_knowledge_doc(self, doc_id: str, title: str, source: str, category: str,
                           version: str, content: str, chunk_count: int) -> None:
        self._execute("DELETE FROM KNOWLEDGE_DOCS WHERE DOC_ID = ?", (doc_id,)).close()
        self._execute(
            "INSERT INTO KNOWLEDGE_DOCS (DOC_ID, TITLE, SOURCE, CATEGORY, VERSION, CONTENT, CHUNK_COUNT, INGESTED_AT) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (doc_id, title, source, category, version, content, chunk_count, int(time.time() * 1000)),
        ).close()
        self.conn.commit()

    def list_knowledge_docs(self) -> List[Dict[str, Any]]:
        return self._query(
            "SELECT DOC_ID, TITLE, CATEGORY, VERSION, SOURCE, CHUNK_COUNT, INGESTED_AT FROM KNOWLEDGE_DOCS ORDER BY DOC_ID")

    # -------------------------------------------------------------- api tokens
    def create_token(self, token_id: str, name: str, role: str, token_hash: str) -> None:
        self._execute(
            "INSERT INTO API_TOKENS (TOKEN_ID, NAME, ROLE, TOKEN_HASH, CREATED_AT, REVOKED) VALUES (?, ?, ?, ?, ?, 0)",
            (token_id, name[:64], role, token_hash, int(time.time() * 1000))).close()
        self.conn.commit()

    def find_token(self, token_hash: str) -> Optional[Dict[str, Any]]:
        rows = self._query(
            "SELECT TOKEN_ID, NAME, ROLE, REVOKED FROM API_TOKENS WHERE TOKEN_HASH = ?", (token_hash,))
        return rows[0] if rows else None

    def touch_token(self, token_id: str) -> None:
        self._execute("UPDATE API_TOKENS SET LAST_USED_AT = ? WHERE TOKEN_ID = ?",
                      (int(time.time() * 1000), token_id)).close()
        self.conn.commit()

    def list_tokens(self) -> List[Dict[str, Any]]:
        return self._query(
            "SELECT TOKEN_ID, NAME, ROLE, CREATED_AT, LAST_USED_AT, REVOKED FROM API_TOKENS ORDER BY CREATED_AT DESC")

    def revoke_token(self, token_id: str) -> bool:
        cur = self._execute("UPDATE API_TOKENS SET REVOKED = 1 WHERE TOKEN_ID = ?", (token_id,))
        changed = cur.rowcount
        cur.close()
        self.conn.commit()
        return bool(changed)

    def count_active_admins(self) -> int:
        return int(self._query(
            "SELECT COUNT(*) AS N FROM API_TOKENS WHERE ROLE = 'admin' AND REVOKED = 0")[0]["N"])

    # -------------------------------------------------------------------- audit
    def audit(self, actor: str, action: str, outcome: str, role: Optional[str] = None,
              target: Optional[str] = None, detail: Optional[str] = None, client_ip: Optional[str] = None) -> None:
        """Append-only audit event. Never raises: auditing must not break the request."""
        try:
            self._execute(
                "INSERT INTO AUDIT_LOG (EVENT_ID, TS, ACTOR, ROLE, ACTION, TARGET, OUTCOME, DETAIL, CLIENT_IP) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (uuid.uuid4().hex, int(time.time() * 1000), actor[:64], role, action[:64],
                 (target or "")[:512] or None, outcome[:16], (detail or "")[:1024] or None, client_ip),
            ).close()
            self.conn.commit()
        except Exception as exc:
            log.error("audit write failed: %s", _safe_err(exc))
            self.rollback()

    def list_audit(self, limit: int = 100, action: Optional[str] = None) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM AUDIT_LOG"
        params: List[Any] = []
        if action:
            sql += " WHERE ACTION = ?"
            params.append(action)
        sql += " ORDER BY TS DESC" + self._limit(limit)
        return self._query(sql, params)

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
