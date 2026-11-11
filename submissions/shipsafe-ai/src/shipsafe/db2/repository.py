"""IBM Db2 persistence layer for ShipSafe AI.

The repository speaks DB-API 2.0. In production it uses `ibm_db_dbi` against a
real IBM Db2 server; the `sqlite` backend exists only so the unit tests can run
without a database. There is no silent fallback: if Db2 is selected and is not
reachable, the error is raised to the caller.

Every statement uses `?` parameter markers. No user-provided value is ever
formatted into SQL text.
"""

import json
import time
from typing import Any, Dict, List, Optional, Sequence

from ..config import Db2Config
from ..models import Assessment, Finding, ToolRun
from .schema import DB2_INDEXES, DB2_TABLES, DB2_VIEWS, SQLITE_DDL

SEVERITY_ORDER_SQL = (
    "CASE SEVERITY WHEN 'critical' THEN 1 WHEN 'high' THEN 2 "
    "WHEN 'medium' THEN 3 WHEN 'low' THEN 4 ELSE 5 END"
)


class Db2Repository:
    """Persistence adapter for assessments, findings and policy documents."""

    def __init__(
        self,
        config: Optional[Db2Config] = None,
        backend: str = "db2",
        sqlite_path: str = ":memory:",
    ):
        self.config = config or Db2Config.from_env()
        self.backend = backend
        if backend == "db2":
            import ibm_db_dbi  # imported lazily so tests don't need the driver

            self.conn = ibm_db_dbi.connect(self.config.connection_string(), "", "")
            self.schema = self.config.schema
        elif backend == "sqlite":
            import sqlite3

            self.conn = sqlite3.connect(sqlite_path, check_same_thread=False)
            self.schema = None
        else:
            raise ValueError(f"Unknown backend '{backend}'. Use 'db2' or 'sqlite'.")
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

    def _limit(self, n: int) -> str:
        n = int(n)  # integer only, never user text
        return f" FETCH FIRST {n} ROWS ONLY" if self.is_db2 else f" LIMIT {n}"

    def _table_exists(self, name: str) -> bool:
        rows = self._query(
            "SELECT 1 AS X FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TABNAME = ?",
            (self.schema, name),
        )
        return bool(rows)

    def _index_exists(self, name: str) -> bool:
        rows = self._query(
            "SELECT 1 AS X FROM SYSCAT.INDEXES WHERE INDSCHEMA = ? AND INDNAME = ?",
            (self.schema, name),
        )
        return bool(rows)

    # ------------------------------------------------------------------- schema
    def initialize_schema(self) -> List[str]:
        """Create tables, indexes and views idempotently. Returns created objects."""
        created: List[str] = []
        if not self.is_db2:
            self.conn.executescript(SQLITE_DDL)
            self.conn.commit()
            return created

        # Schema names cannot be parameter markers; validate as an identifier.
        if not self.schema.replace("_", "").isalnum():
            raise ValueError(f"Invalid DB2_SCHEMA identifier: {self.schema!r}")
        self._execute(f"SET SCHEMA {self.schema}").close()

        for name, ddl in DB2_TABLES.items():
            if not self._table_exists(name):
                self._execute(ddl).close()
                created.append(name)
        for name, ddl in DB2_INDEXES.items():
            if not self._index_exists(name):
                self._execute(ddl).close()
                created.append(name)
        for name, ddl in DB2_VIEWS.items():
            self._execute(ddl).close()
        self.conn.commit()
        return created

    def check_connection(self) -> Dict[str, Any]:
        """Diagnostic probe used by `shipsafe doctor`."""
        if not self.is_db2:
            return {"connected": True, "engine": "SQLite (unit-test backend)"}
        row = self._query(
            "SELECT SERVICE_LEVEL, CURRENT SERVER AS DB_NAME, CURRENT SCHEMA AS SCHEMA_NAME "
            "FROM SYSIBMADM.ENV_INST_INFO"
        )[0]
        tables = self._query(
            "SELECT COUNT(*) AS N FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TYPE = 'T'", (self.schema,)
        )[0]["N"]
        views = self._query(
            "SELECT COUNT(*) AS N FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TYPE = 'V'", (self.schema,)
        )[0]["N"]
        return {
            "connected": True,
            "engine": "IBM Db2",
            "version": row["SERVICE_LEVEL"],
            "database": str(row["DB_NAME"]).strip(),
            "schema": str(row["SCHEMA_NAME"]).strip(),
            "host": self.config.host,
            "port": self.config.port,
            "tables_in_schema": int(tables),
            "views_in_schema": int(views),
        }

    # ----------------------------------------------------------------- projects
    def save_project(self, project_id: str, repo_root_hash: str, name: str, default_branch: str = "main") -> None:
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
        self.conn.commit()

    def save_dependencies(self, project_id: str, deps: List[Dict[str, str]]) -> None:
        """Replace the dependency inventory (SBOM) for a project."""
        self._execute("DELETE FROM DEPENDENCIES WHERE PROJECT_ID = ?", (project_id,)).close()
        sql = (
            "INSERT INTO DEPENDENCIES (DEPENDENCY_ID, PROJECT_ID, PACKAGE_NAME, VERSION, MANIFEST_PATH, ECOSYSTEM) "
            "VALUES (?, ?, ?, ?, ?, ?)"
        )
        cur = self.conn.cursor()
        for i, d in enumerate(deps):
            cur.execute(sql, (
                f"{project_id[:80]}_{i}", project_id, d["name"], d["version"], d.get("manifest"), d.get("ecosystem", "pypi"),
            ))
        cur.close()
        self.conn.commit()

    # -------------------------------------------------------------- assessments
    def save_assessment(self, a: Assessment) -> None:
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
        self.conn.commit()

    def save_tool_runs(self, tool_runs: List[ToolRun]) -> None:
        sql = (
            "INSERT INTO TOOL_RUNS (TOOL_RUN_ID, ASSESSMENT_ID, TOOL_NAME, VERSION, EXIT_CODE, DURATION_MS, STATUS, MESSAGE) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        )
        cur = self.conn.cursor()
        for tr in tool_runs:
            cur.execute(sql, (
                tr.tool_run_id, tr.assessment_id, tr.tool_name, tr.version[:64],
                tr.exit_code, tr.duration_ms, tr.status, tr.message[:1024],
            ))
        cur.close()
        self.conn.commit()

    def save_findings(self, findings: List[Finding]) -> None:
        sql = """
        INSERT INTO FINDINGS (
            FINDING_ID, ASSESSMENT_ID, FINGERPRINT, SOURCE_TOOL, RULE_ID, CATEGORY, SEVERITY, CONFIDENCE,
            FILE_PATH, LINE_START, LINE_END, TITLE, DESCRIPTION, EVIDENCE_JSON, REMEDIATION, STATUS, REFERENCES_JSON
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        cur = self.conn.cursor()
        for f in findings:
            cur.execute(sql, (
                f.finding_id, f.assessment_id, f.fingerprint, f.source_tool, f.rule_id, f.category,
                f.severity, f.confidence, f.file_path, f.line_start, f.line_end, f.title[:256],
                (f.description or "")[:2048], json.dumps(f.evidence), (f.remediation or "")[:2048],
                f.status, json.dumps(f.references),
            ))
        cur.close()
        self.conn.commit()

    # ------------------------------------------------------------------ queries
    def get_assessment(self, assessment_id: str) -> Optional[Dict[str, Any]]:
        rows = self._query("SELECT * FROM ASSESSMENTS WHERE ASSESSMENT_ID = ?", (assessment_id,))
        return rows[0] if rows else None

    def get_findings(self, assessment_id: str) -> List[Dict[str, Any]]:
        rows = self._query(
            f"SELECT * FROM FINDINGS WHERE ASSESSMENT_ID = ? ORDER BY {SEVERITY_ORDER_SQL}, FILE_PATH, LINE_START",
            (assessment_id,),
        )
        for r in rows:
            r["EVIDENCE"] = json.loads(r.pop("EVIDENCE_JSON") or "{}")
            r["REFERENCES"] = json.loads(r.pop("REFERENCES_JSON") or "[]")
        return rows

    def get_finding(self, finding_id: str) -> Optional[Dict[str, Any]]:
        rows = self._query("SELECT * FROM FINDINGS WHERE FINDING_ID = ?", (finding_id,))
        if not rows:
            return None
        r = rows[0]
        r["EVIDENCE"] = json.loads(r.pop("EVIDENCE_JSON") or "{}")
        r["REFERENCES"] = json.loads(r.pop("REFERENCES_JSON") or "[]")
        return r

    def get_tool_runs(self, assessment_id: str) -> List[Dict[str, Any]]:
        return self._query(
            "SELECT * FROM TOOL_RUNS WHERE ASSESSMENT_ID = ? ORDER BY TOOL_NAME", (assessment_id,)
        )

    def get_assessment_history(self, limit: int = 10, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Recent assessments with the risk score delta computed in Db2 (V_RISK_TREND)."""
        if self.is_db2:
            sql = ("SELECT PROJECT_NAME, ASSESSMENT_ID, STATUS, STARTED_AT, CRITICAL_COUNT, HIGH_COUNT, "
                   "MEDIUM_COUNT, LOW_COUNT, RISK_SCORE, RISK_DELTA FROM V_RISK_TREND")
        else:
            sql = ("SELECT P.NAME AS PROJECT_NAME, A.ASSESSMENT_ID, A.STATUS, A.STARTED_AT, A.CRITICAL_COUNT, "
                   "A.HIGH_COUNT, A.MEDIUM_COUNT, A.LOW_COUNT, "
                   "(A.CRITICAL_COUNT*10 + A.HIGH_COUNT*5 + A.MEDIUM_COUNT*2 + A.LOW_COUNT) AS RISK_SCORE, "
                   "NULL AS RISK_DELTA FROM ASSESSMENTS A JOIN PROJECTS P ON P.PROJECT_ID = A.PROJECT_ID")
        params: List[Any] = []
        if project_id:
            sql += " WHERE PROJECT_ID = ?" if self.is_db2 else " WHERE A.PROJECT_ID = ?"
            params.append(project_id)
        sql += " ORDER BY STARTED_AT DESC" + self._limit(limit)
        return self._query(sql, params)

    def severity_breakdown(self) -> List[Dict[str, Any]]:
        """Aggregate open findings by category and severity across all assessments."""
        return self._query(
            "SELECT CATEGORY, SEVERITY, COUNT(*) AS TOTAL, COUNT(DISTINCT FINGERPRINT) AS UNIQUE_ISSUES "
            f"FROM FINDINGS GROUP BY CATEGORY, SEVERITY ORDER BY CATEGORY, MIN({SEVERITY_ORDER_SQL})"
        )

    def compare_assessments(self, previous_id: str, current_id: str) -> Dict[str, Any]:
        """Regression diff by stable fingerprint; persists the delta to ASSESSMENT_DIFFS."""
        prev = {f["FINGERPRINT"]: f for f in self.get_findings(previous_id)}
        curr = {f["FINGERPRINT"]: f for f in self.get_findings(current_id)}
        new_items = [curr[fp] for fp in curr.keys() - prev.keys()]
        resolved_items = [prev[fp] for fp in prev.keys() - curr.keys()]
        unchanged_items = [curr[fp] for fp in curr.keys() & prev.keys()]

        self._execute(
            "DELETE FROM ASSESSMENT_DIFFS WHERE CURRENT_ID = ? AND PREVIOUS_ID = ?", (current_id, previous_id)
        ).close()
        sql = (
            "INSERT INTO ASSESSMENT_DIFFS (DIFF_ID, CURRENT_ID, PREVIOUS_ID, FINDING_FINGERPRINT, CHANGE_TYPE, TITLE, SEVERITY) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)"
        )
        cur = self.conn.cursor()
        for change, items in (("new", new_items), ("resolved", resolved_items), ("unchanged", unchanged_items)):
            for it in items:
                diff_id = f"{current_id}:{previous_id}:{it['FINGERPRINT'][:16]}"
                cur.execute(sql, (diff_id, current_id, previous_id, it["FINGERPRINT"], change, it["TITLE"], it["SEVERITY"]))
        cur.close()
        self.conn.commit()

        return {
            "previous_id": previous_id,
            "current_id": current_id,
            "new_count": len(new_items),
            "resolved_count": len(resolved_items),
            "unchanged_count": len(unchanged_items),
            "new_findings": new_items,
            "resolved_findings": resolved_items,
            "unchanged_findings": unchanged_items,
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
            "SELECT DOC_ID, TITLE, CATEGORY, VERSION, SOURCE, CHUNK_COUNT FROM KNOWLEDGE_DOCS ORDER BY DOC_ID"
        )

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
